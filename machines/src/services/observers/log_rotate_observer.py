# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Custom event for flushing mysql logs."""

import logging
import os
import typing

from mysql_shell import LogType
from ops.framework import EventBase, Object

if typing.TYPE_CHECKING:
    from charm import MySQLOperatorCharm

logger = logging.getLogger(__name__)


class RotateMySQLLogsEvent(EventBase):
    """A custom event to rotate the mysql logs."""


class RotateMySQLLogsObserver(Object):
    """Encapsulates the handling of MySQL logs."""

    def __init__(self, charm: "MySQLOperatorCharm"):
        super().__init__(charm, "mysql-logs")

        self.charm = charm

        self.framework.observe(self.charm.on.rotate_mysql_logs, self._rotate_mysql_logs)

    def _rotate_mysql_logs(self, _) -> None:
        """Rotate the mysql logs (via LOGS_TYPE env var)."""
        if (
            not self.charm.peers
            or not self.charm.unit_initialized()
            or not self.charm._mysql.is_mysqld_running()
        ):
            # skip when not initialized
            return

        if self.charm.refresh is None:
            logger.warning("Refresh could be in progress")
            return
        if self.charm.refresh and self.charm.refresh.in_progress:
            logger.debug("Refresh in progress")
            return

        logs_type = os.environ.get("LOGS_TYPE", "")
        if logs_type == "AUDIT":
            self.charm._mysql.flush_mysql_audit_log()
            return

        try:
            logs_type = LogType(logs_type)
        except KeyError:
            logger.debug(f"Invalid flush of logs type: {logs_type}")
            return

        self.charm._mysql.flush_mysql_logs(logs_type)
        logger.debug(f"Flushed {logs_type} logs")
