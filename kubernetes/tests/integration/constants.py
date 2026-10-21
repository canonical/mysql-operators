# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

CONTAINER_NAME = "mysql"

DATABASE_PASSWORD_LEN = 24
DATABASE_PASSWORD_MAX = 130

MYSQL_ARCHIVE_DIR = "/var/lib/mysql/archive"
MYSQL_DATA_DIR = "/var/lib/mysql/data"
MYSQL_LOGS_DIR = "/var/lib/mysql/logs"
MYSQL_TEMP_DIR = "/var/lib/mysql/temp"

TLS_CLIENT_RELATION = "client-certificates"
TLS_PEER_RELATION = "peer-certificates"

BACKUPS_USERNAME = "charmed-backup"
OPERATOR_USERNAME = "charmed-operator"
REPLICATION_USERNAME = "charmed-replication"
