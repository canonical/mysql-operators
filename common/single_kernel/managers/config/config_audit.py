# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import enum

from ...workload.systems.paths import BasePaths


class AuditFormat(enum.StrEnum):
    """Percona audit plugin formats.

    https://docs.percona.com/percona-server/8.4/audit-log-plugin.html?h=audit#audit_log_format
    """

    CSV = "CSV"
    JSON = "JSON"


class AuditPolicy(enum.StrEnum):
    """Percona audit plugin policies.

    https://docs.percona.com/percona-server/8.4/audit-log-plugin.html?h=audit#audit_log_policy
    """

    ALL = "ALL"
    LOGINS = "LOGINS"
    QUERIES = "QUERIES"


class AuditStrategy(enum.StrEnum):
    """Percona audit plugin policies.

    https://docs.percona.com/percona-server/8.4/audit-log-plugin.html?h=audit#audit_log_strategy
    """

    ASYNC = "ASYNCHRONOUS"
    PERF = "PERFORMANCE"
    SEMI = "SEMISYNCHRONOUS"
    SYNC = "SYNCHRONOUS"


class AuditConfigHelper:
    """Class to deal with the MySQL server audit plugin config."""

    static_keys = {
        "loose-audit_log_filter.format",
        "loose-audit_log_filter.strategy",
    }

    def __init__(self, paths: BasePaths):
        """Initialize the class attributes."""
        self._paths = paths

    def get_config(self, fmt: AuditFormat, policy: AuditPolicy, strategy: AuditStrategy) -> dict:
        """Return the Percona audit plugin config."""
        return {
            "loose-audit_log_filter.file": self._paths.mysql_logs / "audit.log",
            "loose-audit_log_filter.format": fmt.value,
            "loose-audit_log_filter.policy": policy.value,
            "loose-audit_log_filter.strategy": strategy.value,
        }
