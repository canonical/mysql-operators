# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

DEFAULT_PASSWORD_LENGTH = 24
MAX_PASSWORD_LENGTH = 130
PEER = "database-peers"
CONTAINER_NAME = "mysql"
MYSQLD_SERVICE = "mysqld"
MYSQL_LOG_SERVICE = "mysql"
MYSQLD_LOCATION = f"/usr/sbin/{MYSQLD_SERVICE}"
REPLICATION_USERNAME = "charmed-replication"
OPERATOR_USERNAME = "charmed-operator"
MONITORING_USERNAME = "charmed-stats"
BACKUPS_USERNAME = "charmed-backup"
DB_RELATION_NAME = "database"
OPERATOR_PASSWORD_KEY = "operator-password"  # noqa: S105
REPLICATION_PASSWORD_KEY = "replication-password"  # noqa: S105
MONITORING_PASSWORD_KEY = "monitoring-password"  # noqa: S105
BACKUPS_PASSWORD_KEY = "backups-password"  # noqa: S105
CONTAINER_RESTARTS = "unit-container-restarts"
UNIT_ENDPOINTS_KEY = "unit-endpoints"
TLS_RELATION = "certificates"
TLS_SSL_CA_FILE = "custom-ca.pem"
TLS_SSL_KEY_FILE = "custom-server-key.pem"
TLS_SSL_CERT_FILE = "custom-server-cert.pem"
MYSQL_CLI_LOCATION = "/usr/bin/mysql"
MYSQLSH_LOCATION = "/usr/bin/mysqlsh"
MYSQL_ARCHIVE_DIR = "/var/lib/mysql/archive"  # Corresponds to the archive storage mount
MYSQL_DATA_DIR = "/var/lib/mysql/data"  # Corresponds to the data storage mount
MYSQL_LOGS_DIR = "/var/lib/mysql/logs"  # Corresponds to the logs storage mount
MYSQL_TEMP_DIR = "/var/lib/mysql/temp"  # Corresponds to the temp storage mount
MYSQLD_SOCK_FILE = "/var/run/mysqld/mysqld.sock"
MYSQLD_CONFIG_FILE = "/etc/mysql/mysql.conf.d/z-custom.cnf"
MYSQLD_INIT_CONFIG_FILE = "/etc/mysql/mysql.conf.d/z-custom-init-file.cnf"
MYSQL_LOG_ERROR = f"{MYSQL_LOGS_DIR}/error.log"
MYSQL_LOG_FILES = [
    MYSQL_LOG_ERROR,
    f"{MYSQL_LOGS_DIR}/audit.log",
    f"{MYSQL_LOGS_DIR}/general.log",
]
MYSQL_SYSTEM_USER = "mysql"
MYSQL_SYSTEM_GROUP = "mysql"
CHARMED_MYSQL_XTRABACKUP_LOCATION = "xtrabackup"
CHARMED_MYSQL_XBCLOUD_LOCATION = "xbcloud"
CHARMED_MYSQL_XBSTREAM_LOCATION = "xbstream"
CHARMED_MYSQL_PITR_HELPER = "mysql-pitr-helper"
XTRABACKUP_PLUGIN_DIR = "/usr/lib64/xtrabackup/plugin"
MYSQLD_DEFAULTS_CONFIG_FILE = "/etc/mysql/my.cnf"
MYSQLD_EXPORTER_PORT = "9104"
MYSQLD_EXPORTER_SERVICE = "mysqld_exporter"
MYSQL_BINLOGS_COLLECTOR_SERVICE = "mysql-pitr-helper-collector"
GR_MAX_MEMBERS = 9
# TODO: should be changed when adopting cos-agent
COS_AGENT_RELATION_NAME = "metrics-endpoint"
COS_LOGGING_RELATION_NAME = "logging"
LOG_ROTATE_CONFIG_FILE = "/etc/logrotate.d/flush_mysql_logs"
