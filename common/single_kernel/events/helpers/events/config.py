# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from typing import Any

from ....managers import ConfigManager
from ....managers.managers.config import AuditFormat

if typing.TYPE_CHECKING:
    from ....charm import BaseCharm

logger = logging.getLogger(__name__)


class ConfigHelper:
    """Class to deal with the database config."""

    def __init__(self, charm: BaseCharm, manager: ConfigManager):
        """Initialize the class attributes."""
        self._charm = charm
        self._manager = manager

    def calculate_buffer_pool(self) -> int:
        """Calculate the instance buffer pool configuration."""
        return self._manager.calculate_buffer_pool()

    def check_restart(self, config_old: dict[str, Any], config_new: dict[str, Any]) -> bool:
        """Check whether the instance needs to be restarted."""
        config_diff = self._manager.compute_diff(config_old, config_new)
        static_diff = self._manager.check_static_key(config_diff)

        return static_diff

    def apply_config(self, config_old: dict[str, Any], config_new: dict[str, Any]) -> None:
        """Apply the instance configuration."""
        config_diff = self._manager.compute_diff(config_old, config_new)

        for key in config_diff:
            self._manager.update_dynamic_var(
                key=key.removeprefix("loose-"),
                val=config_new[key],
            )

    def load_config(self) -> dict[str, Any]:
        """Load the instance configuration."""
        return self._manager.read_server_config()

    def save_config(self) -> dict[str, Any]:
        """Save the instance configuration, returning the new configuration."""
        logger.info("Saving instance configuration")

        config = self._manager.build_server_config(
            audit_format=AuditFormat.JSON,
            audit_policy=self._charm.config.logs_audit_policy,
            audit_strategy=self._charm.config.plugin_audit_strategy,
            binlog_retention_days=self._charm.config.binlog_retention_days,
            instance_address=self._charm.get_unit_address(self._charm.unit),
            memory_profile=self._charm.config.profile,
            memory_limit=self._charm.config.profile_limit_memory,
            max_connections=self._charm.config.max_connections,
        )

        self._manager.write_server_config(config)
        return config
