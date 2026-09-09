# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

RELATION_BACKUPS = "s3-parameters"
RELATION_DATABASE = "database"
RELATION_LOGS_K8S = "logging"
RELATION_LOGS_VM = "cos-agent"
RELATION_PEERS = "database-peers"
RELATION_OPS = "rolling-ops"
RELATION_RPL_OFFERER = "replication-offer"
RELATION_RPL_CONSUMER = "replication"
RELATION_TLS_CLIENT = "client-certificates"
RELATION_TLS_PEER = "peer-certificates"
RELATION_TRACING = "tracing"

ROLENAME_DBA = "charmed_dba"
ROLENAME_DDL = "charmed_ddl"
ROLENAME_DML = "charmed_dml"
ROLENAME_READ = "charmed_read"
ROLENAME_MONITOR = "charmed_stats"
ROLENAME_BACKUPS = "charmed_backup"
ROLENAME_ROUTER = "charmed_router"

USERNAME_BACKUPS = "charmed-backup"
USERNAME_MONITOR = "charmed-stats"
USERNAME_OPERATOR = "charmed-operator"
USERNAME_REPLICATION = "charmed-replication"

PASSWORD_KEY_BACKUPS = "backups-password"
PASSWORD_KEY_MONITOR = "monitoring-password"
PASSWORD_KEY_OPERATOR = "operator-password"
PASSWORD_KEY_REPLICATION = "replication-password"

USERNAME_TO_PASSWORD_KEY = {
    USERNAME_BACKUPS: PASSWORD_KEY_BACKUPS,
    USERNAME_MONITOR: PASSWORD_KEY_MONITOR,
    USERNAME_OPERATOR: PASSWORD_KEY_OPERATOR,
    USERNAME_REPLICATION: PASSWORD_KEY_REPLICATION,
}
