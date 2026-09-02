# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import configparser
import logging
from io import StringIO

from ...state import ConfigState
from ...workload import BaseSystem
from .config_audit import AuditConfigHelper, AuditFormat, AuditPolicy, AuditStrategy
from .config_cluster import ClusterConfigHelper, MemoryProfile
from .config_password import PasswordConfigHelper

logger = logging.getLogger(__name__)


class ConfigManager:
    """Class to deal with the MySQL server config."""

    static_keys = {
        "admin_address",
        "report_host",
        "log_error",
    }

    def __init__(self, state: ConfigState, system: BaseSystem):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._audit_enabled = True
        self._audit_helper = AuditConfigHelper(system.paths)
        self._cluster_helper = ClusterConfigHelper(system.paths)
        self._password_helper = PasswordConfigHelper()

    def build_server_config(
        self,
        audit_format: AuditFormat,
        audit_policy: AuditPolicy,
        audit_strategy: AuditStrategy,
        binlog_retention_days: int,
        instance_address: str,
        memory_profile: MemoryProfile,
        memory_limit: int | None = None,
        max_connections: int | None = None,
    ) -> dict:
        """Builds the MySQL server config."""
        memory = self._system.runtime.get_memory()
        if memory_limit:
            memory = min(memory, memory_limit)

        cluster_config = self._cluster_helper.get_config(memory_profile, memory, max_connections)
        password_config = self._password_helper.get_config()

        config = {
            "activate_all_roles_on_login": "ON",
            "binlog_expire_logs_seconds": binlog_retention_days * 24 * 60 * 60,
            "datadir": self._system.paths.mysql_data,
            "bind_address": "0.0.0.0",
            "admin_address": instance_address,
            "report_host": instance_address,
            "general_log": "OFF",
            "general_log_file": self._system.paths.mysql_logs / "general.log",
            "log_bin": self._system.paths.mysql_logs / "binlog",
            "log_bin_index": self._system.paths.mysql_logs / "binlog.index",
            "log_error": self._system.paths.mysql_logs / "error.log",
            "log_error_services": "log_filter_internal;log_sink_internal",
            "slow_query_log_file": self._system.paths.mysql_logs / "slow.log",
            "max_connect_errors": 10000,
            **cluster_config,
            **password_config,
        }

        if self._audit_enabled:
            audit_config = self._audit_helper.get_config(audit_format, audit_policy, audit_strategy)
            config.update(audit_config)

        return config

    def write_server_config(self, config: dict) -> None:
        """Writes the MySQL server config."""
        parser = configparser.ConfigParser(interpolation=None)
        parser["mysqld"] = config

        with StringIO() as string:
            parser.write(string)
            self._system.paths.mysql_config_custom.write_text(string.getvalue())

    def compute_diff(self, config_1: dict, config_2: dict) -> set[str]:
        """Computes the set of different keys between the two configurations."""
        similar_keys = config_1.keys() & config_2.keys()
        distinct_keys = config_1.keys() ^ config_2.keys()

        for key in similar_keys:
            if config_1[key] != config_2[key]:
                distinct_keys.add(key)

        return distinct_keys

    def check_static_key(self, keys: set[str]) -> bool:
        """Return whether any static key is present."""
        all_static_keys = (
            self.static_keys
            | self._audit_helper.static_keys
            | self._cluster_helper.static_keys
            | self._password_helper.static_keys
        )

        return bool(keys & all_static_keys)

    def filter_static_keys(self, keys: set[str]) -> set[str]:
        """Return the set of filtered our static keys."""
        all_static_keys = (
            self.static_keys
            | self._audit_helper.static_keys
            | self._cluster_helper.static_keys
            | self._password_helper.static_keys
        )

        return set(keys - all_static_keys)

    def toggle_audit_plugin(self, enable: bool) -> None:
        """Toggle the audit plugin."""
        self._audit_enabled = enable
