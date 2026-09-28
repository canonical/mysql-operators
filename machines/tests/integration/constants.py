# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

DATABASE_PASSWORD_LEN = 24
DATABASE_PASSWORD_MAX = 130

MYSQL_ARCH_DIR = "/var/snap/charmed-mysql/common/var/lib/mysql/archive"
MYSQL_DATA_DIR = "/var/snap/charmed-mysql/common/var/lib/mysql/data"
MYSQL_LOGS_DIR = "/var/snap/charmed-mysql/common/var/lib/mysql/logs"
MYSQL_TEMP_DIR = "/var/snap/charmed-mysql/common/var/lib/mysql/temp"

TLS_CLIENT_RELATION = "client-certificates"
TLS_PEER_RELATION = "peer-certificates"

BACKUPS_USERNAME = "charmed-backup"
OPERATOR_USERNAME = "charmed-operator"
REPLICATION_USERNAME = "charmed-replication"
