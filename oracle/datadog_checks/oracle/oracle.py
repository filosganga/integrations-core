# (C) Datadog, Inc. 2018-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import itertools
import threading
from contextlib import closing

import oracledb
from six import PY2

from datadog_checks.base import AgentCheck, ConfigurationError
from datadog_checks.base.utils.db import QueryManager

from . import queries

try:
    import jaydebeapi as jdb
    import jpype

    JDBC_IMPORT_ERROR = None
except ImportError as e:
    jdb = None
    jpype = None
    JDBC_IMPORT_ERROR = e


EVENT_TYPE = SOURCE_TYPE_NAME = 'oracle'
MAX_CUSTOM_RESULTS = 100

PROTOCOL_TCP = 'TCP'
PROTOCOL_TCPS = 'TCPS'
VALID_PROTOCOLS = [PROTOCOL_TCP, PROTOCOL_TCPS]
VALID_TRUSTSTORE_TYPES = ['JKS', 'SSO', 'PKCS12']

# When using JDBC connection and multiple instances of the check
# It causes the following error
# Native Library .../_jpype.cpython-38-x86_64-linux-gnu.so already loaded in another classloader
# To prevent it we're adding a lock over jpype operations
jdbc_lock = threading.Lock()


class Oracle(AgentCheck):
    __NAMESPACE__ = 'oracle'

    ORACLE_DRIVER_CLASS = "oracle.jdbc.OracleDriver"
    JDBC_CONNECTION_STRING = "jdbc:oracle:thin:@//{}/{}"
    JDBC_CONNECTION_STRING_TCPS = "jdbc:oracle:thin:@{}"

    SERVICE_CHECK_NAME = 'can_connect'
    SERVICE_CHECK_CAN_QUERY = "can_query"

    def __init__(self, name, init_config, instances):
        if PY2:
            raise ConfigurationError(
                "This version of the integration is only available when using py3. "
                "Check https://docs.datadoghq.com/agent/guide/agent-v6-python-3 "
                "for more information."
            )
        super(Oracle, self).__init__(name, init_config, instances)
        self._server = self.instance.get('server')
        self._user = self.instance.get('username') or self.instance.get('user')
        self._password = self.instance.get('password')
        self._service = self.instance.get('service_name')
        self._protocol = self.instance.get("protocol", PROTOCOL_TCP)
        self._jdbc_driver = self.instance.get('jdbc_driver_path')
        self._jdbc_truststore_path = self.instance.get('jdbc_truststore_path')
        self._jdbc_truststore_type = self.instance.get('jdbc_truststore_type')
        self._jdbc_truststore_password = self.instance.get('jdbc_truststore_password', '')
        self._tags = self.instance.get('tags') or []
        self._service_check_tags = ['server:{}'.format(self._server)]
        self._service_check_tags.extend(self._tags)

        self._cached_connection = None

        manager_queries = []
        if not self.instance.get('only_custom_queries', False):
            manager_queries.extend([queries.ProcessMetrics, queries.SystemMetrics, queries.TableSpaceMetrics])

        self._fix_custom_queries()

        self._query_manager = QueryManager(
            self,
            self.execute_query_raw,
            queries=manager_queries,
            error_handler=self.handle_query_error,
            tags=self._tags,
        )

        self.check_initializations.append(self._query_manager.compile_queries)
        self.check_initializations.append(self.can_use_jdbc)

        self._query_errors = 0
        self._connection_errors = 0

    def _fix_custom_queries(self):
        """
        For backward compatibility reasons, if a custom query specifies a
        `metric_prefix`, change the submission name to contain it.
        """
        custom_queries = self.instance.get('custom_queries', [])
        global_custom_queries = self.init_config.get('global_custom_queries', [])
        for query in itertools.chain(custom_queries, global_custom_queries):
            prefix = query.get('metric_prefix')
            if prefix and prefix != self.__NAMESPACE__:
                if prefix.startswith(self.__NAMESPACE__ + '.'):
                    prefix = prefix[len(self.__NAMESPACE__) + 1 :]
                for column in query.get('columns', []):
                    if column.get('type') != 'tag' and column.get('name'):
                        column['name'] = '{}.{}'.format(prefix, column['name'])

    def execute_query_raw(self, query):
        with closing(self._connection.cursor()) as cursor:
            cursor.execute(query)
            # JDBC doesn't support iter protocol
            return cursor.fetchall()

    def handle_query_error(self, error):
        self._query_errors += 1
        if self._cached_connection is None:
            self.log.debug("Couldn't close the connection after a query failure because there was no connection")
            return error

        try:
            self._cached_connection.close()
        except Exception as e:
            self.log.warning("Couldn't close the connection after a query failure: %s", str(e))
        self._cached_connection = None

        return error

    def check(self, _):
        if self.instance.get('user'):
            self._log_deprecation('_config_renamed', 'user', 'username')

        self._query_errors = 0
        self._connection_errors = 0

        self._query_manager.execute()

        if self._query_errors:
            self.service_check(self.SERVICE_CHECK_CAN_QUERY, self.CRITICAL, tags=self._service_check_tags)
        else:
            self.service_check(self.SERVICE_CHECK_CAN_QUERY, self.OK, tags=self._service_check_tags)

        if self._connection_errors:
            self.service_check(self.SERVICE_CHECK_NAME, self.CRITICAL, tags=self._service_check_tags)
        else:
            self.service_check(self.SERVICE_CHECK_NAME, self.OK, tags=self._service_check_tags)

    @property
    def _connection(self):
        if self._cached_connection is None:
            if self.can_use_jdbc():
                try:
                    self._cached_connection = self._jdbc_connect()
                except Exception as e:
                    self.log.error("The JDBC connection failed with the following error: %s", str(e))
                    self._connection_errors += 1
            else:
                self._cached_connection = self._oracle_connect()
        return self._cached_connection

    def can_use_jdbc(self):
        if self._jdbc_driver:
            if JDBC_IMPORT_ERROR is not None:
                self.log.error(
                    "The integration is unable to import JDBC libraries. Please double check your "
                    "installation and refer to the Datadog documentation for more information."
                )
                raise JDBC_IMPORT_ERROR
            else:
                return True
        else:
            return False

    def _oracle_connect(self):
        dsn = self._get_dsn()
        self.log.debug("Connecting to Oracle with DSN: %s", dsn)
        try:
            connection = oracledb.connect(user=self._user, password=self._password, dsn=dsn)
            self.log.debug("Connected to Oracle DB using Python Oracle")
            return connection
        except oracledb.DatabaseError as e:
            self._connection_errors += 1
            self.log.error("Failed to connect to Oracle DB, error: %s", str(e))
            raise

            
            
    def _get_dsn(self):
        host = self._server
        port = 1521
        try:
            if ':' in self._server:
                host, port = self._server.split(':')
                port = int(port)
        except Exception:
            self._connection_errors += 1
            raise ConfigurationError('server needs to be in the <HOST>:<PORT> format, "%s"" provided' % self._server)

        if self._protocol == PROTOCOL_TCPS:
            dsn = '(DESCRIPTION=(ADDRESS=(PROTOCOL={})(HOST={})(PORT={}))(CONNECT_DATA=(SERVICE_NAME={})))'.format(
                self._protocol, host, port, self._service
            )
            return dsn
        else:
            return oracledb.makedsn(host, port, service_name=self._service)

    def _jdbc_connect(self):
        jdbc_connect_properties = {'user': self._user, 'password': self._password}

        if self._protocol == PROTOCOL_TCPS:
            connect_string = self.JDBC_CONNECTION_STRING_TCPS.format(self._get_dsn())
            jdbc_connect_properties['javax.net.ssl.trustStoreType'] = self._jdbc_truststore_type
            jdbc_connect_properties['javax.net.ssl.trustStorePassword'] = self._jdbc_truststore_password
            jdbc_connect_properties['javax.net.ssl.trustStore'] = self._jdbc_truststore_path
        else:
            connect_string = self.JDBC_CONNECTION_STRING.format(self._server, self._service)

        self.log.debug("Connecting via JDBC with connection string: %s", connect_string)
        try:
            with jdbc_lock:
                if jpype.isJVMStarted() and not jpype.isThreadAttachedToJVM():
                    jpype.attachThreadToJVM()
                    jpype.java.lang.Thread.currentThread().setContextClassLoader(
                        jpype.java.lang.ClassLoader.getSystemClassLoader()
                    )
                connection = jdb.connect(
                    self.ORACLE_DRIVER_CLASS, connect_string, jdbc_connect_properties, self._jdbc_driver
                )
            self.log.debug("Connected to Oracle DB using JDBC connector")
            return connection
        except Exception as e:
            self._connection_errors += 1
            if "Class {} not found".format(self.ORACLE_DRIVER_CLASS) in str(e):
                msg = """Cannot run the Oracle check until either the Oracle instant client or the JDBC Driver
                is available.
                For the Oracle instant client, see:
                http://www.oracle.com/technetwork/database/features/instant-client/index.html
                You will also need to ensure the `LD_LIBRARY_PATH` is also updated so the libs are reachable.

                For the JDBC Driver, see:
                http://www.oracle.com/technetwork/database/application-development/jdbc/downloads/index.html
                You will also need to ensure the jar is either listed in your $CLASSPATH or in the yaml
                configuration file of the check.
                """
                self.log.error(msg)
            raise
