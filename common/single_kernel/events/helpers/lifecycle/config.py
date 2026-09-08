# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ....managers import ConfigManager
from ....managers.managers.config import AuditFormat

if typing.TYPE_CHECKING:
    from ....charm import Operator

logger = logging.getLogger(__name__)


class ConfigHelper:
    """Class to deal with the database config."""

    def __init__(self, charm: Operator, manager: ConfigManager):
        """Initialize the class attributes."""
        self._charm = charm
        self._manager = manager

    def check_restart(self, diff: set[str]) -> bool:
        """Check whether instance restart is required given a key difference."""
        return self._manager.check_static_key(diff)

    def update_config(self) -> set[str]:
        """Update the instance configuration, returning the keys difference."""
        logger.info("Updating instance configuration")

        config_old = self._manager.read_server_config()
        config_new = self._manager.build_server_config(
            audit_format=AuditFormat.JSON,
            audit_policy=self._charm.config.logs_audit_policy,
            audit_strategy=self._charm.config.plugin_audit_strategy,
            binlog_retention_days=self._charm.config.binlog_retention_days,
            instance_address=self._charm.get_unit_address(self._charm.unit),
            memory_profile=self._charm.config.profile,
            memory_limit=self._charm.config.profile_limit_memory,
            max_connections=self._charm.config.max_connections,
        )

        ___________ = self._manager.write_server_config(config_new)
        config_diff = self._manager.compute_diff(config_old, config_new)

        for key in self._manager.filter_static_keys(config_diff):
            self._manager.update_dynamic_var(
                key=key.removeprefix("loose-"),
                val=config_new[key],
            )

        return config_diff
