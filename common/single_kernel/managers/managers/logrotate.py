# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models.statement import LogType

from ...state import LogrotateState
from ...workload import BaseSystem
from ..clients import MySQLClusterClient, MySQLInstanceClient

logger = logging.getLogger(__name__)


class LogrotateManager:
    """Class to deal with the log-rotate operations."""

    text_logs = [
        LogType.ERROR,
        LogType.GENERAL,
        LogType.SLOW,
    ]

    def __init__(
        self,
        state: LogrotateState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    def get_synced_flag(self) -> bool | None:
        """Get the synchronization flag."""
        self._state.get_sync_flag()

    def set_synced_flag(self, flag: bool) -> None:
        """Set the synchronization flag."""
        self._state.set_sync_flag(flag)

    def delete_synced_flag(self) -> None:
        """Delete the synchronization flag."""
        self._state.delete_sync_flag()

    def rotate_logs(self, audit_log_enabled: bool) -> None:
        """Rotates the MySQL text logs."""
        try:
            self._system.shell.execute_sync([
                f"logrotate",
                f"--force",
                f"{self._system.paths.logrotate_config}",
            ])
        except RuntimeError as e:
            logger.warning(f"Failed to run logrotate: {e}")
            return

        try:
            self._instance_client.flush_native_logs(self.text_logs)
            self._instance_client.flush_audit_log() if audit_log_enabled else None
        except ExecutionError as e:
            raise RuntimeError(f"Failed to rotate MySQL logs: {e}")
