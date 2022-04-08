# (C) Datadog, Inc. 2021-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# This file is autogenerated.
# To change this file you should edit assets/configuration/spec.yaml and then run the following commands:
#     ddev -x validate config -s <INTEGRATION_NAME>
#     ddev -x validate models -s <INTEGRATION_NAME>

from datadog_checks.base.utils.models.fields import get_default_field_value


def shared_service(field, value):
    return get_default_field_value(field, value)


def instance_auto_discover_channels(field, value):
    return True


def instance_auto_discover_queues(field, value):
    return False


def instance_channel_status_mapping(field, value):
    return get_default_field_value(field, value)


def instance_channels(field, value):
    return get_default_field_value(field, value)


def instance_collect_statistics_metrics(field, value):
    return False


def instance_connection_name(field, value):
    return get_default_field_value(field, value)


def instance_convert_endianness(field, value):
    return False


def instance_disable_generic_tags(field, value):
    return False


def instance_empty_default_hostname(field, value):
    return False


def instance_host(field, value):
    return 'localhost'


def instance_metric_patterns(field, value):
    return get_default_field_value(field, value)


def instance_min_collection_interval(field, value):
    return 15


def instance_mqcd_version(field, value):
    return 6


def instance_override_hostname(field, value):
    return False


def instance_password(field, value):
    return get_default_field_value(field, value)


def instance_port(field, value):
    return 1414


def instance_queue_manager_timezone(field, value):
    return 'Etc/UTC'


def instance_queue_patterns(field, value):
    return get_default_field_value(field, value)


def instance_queue_regex(field, value):
    return get_default_field_value(field, value)


def instance_queue_tag_re(field, value):
    return get_default_field_value(field, value)


def instance_queues(field, value):
    return get_default_field_value(field, value)


def instance_service(field, value):
    return get_default_field_value(field, value)


def instance_ssl_auth(field, value):
    return False


def instance_ssl_certificate_label(field, value):
    return get_default_field_value(field, value)


def instance_ssl_cipher_spec(field, value):
    return 'TLS_RSA_WITH_AES_256_CBC_SHA'


def instance_ssl_key_repository_location(field, value):
    return '/var/mqm/ssl-db/client/KeyringClient'


def instance_tags(field, value):
    return get_default_field_value(field, value)


def instance_timeout(field, value):
    return 5


def instance_try_basic_auth(field, value):
    return True


def instance_username(field, value):
    return get_default_field_value(field, value)