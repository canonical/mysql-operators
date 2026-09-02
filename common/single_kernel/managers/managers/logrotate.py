# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients
from ..models import TextLogs

logger = logging.getLogger(__name__)


class LogrotateManager:
    """Class to deal with the log-rotate operations."""

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def get_synced_flag(self) -> bool | None:
        """Get the synchronization flag."""
        return self._state.unit.get_logrotate_sync_flag()

    def set_synced_flag(self, flag: bool) -> None:
        """Set the synchronization flag."""
        return self._state.unit.set_logrotate_sync_flag(flag)

    def delete_synced_flag(self) -> None:
        """Delete the synchronization flag."""
        return self._state.unit.delete_logrotate_sync_flag()

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

        self._clients.instance.flush_native_logs(TextLogs)
        self._clients.instance.flush_audit_log() if audit_log_enabled else None
