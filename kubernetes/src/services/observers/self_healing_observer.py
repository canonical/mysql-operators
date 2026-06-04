# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Custom event for self-healing the mysql cluster."""

import logging
import typing

from ops.framework import EventBase, Object

from constants import CONTAINER_NAME

if typing.TYPE_CHECKING:
    from charm import MySQLOperatorCharm

logger = logging.getLogger(__name__)


class SelfHealingMySQLEvent(EventBase):
    """A custom event to self-heal the mysql cluster."""


class SelfHealingMySQLObserver(Object):
    """Encapsulates the self-healing of mysql cluster."""

    def __init__(self, charm: "MySQLOperatorCharm"):
        super().__init__(charm, "self-healing-mysql")
        self.charm = charm
        self.framework.observe(self.charm.on.heal_mysql_cluster, self._heal_mysql_cluster)

    def _heal_mysql_cluster(self, _) -> None:
        """Self-heal the mysql cluster."""
        if (
            self.charm.peers is None
            or not self.charm._mysql.is_mysqld_running()
            or not self.charm.unit_initialized()
        ):
            # skip when not initialized, during an upgrade, or when mysqld is not running
            return

        if self.charm.refresh is None:
            logger.warning("Refresh could be in progress")
            return
        if self.charm.refresh and self.charm.refresh.in_progress:
            logger.debug("Refresh in progress")
            return

        container = self.charm.unit.get_container(CONTAINER_NAME)
        if not container.can_connect():
            logger.info("Cannot connect to pebble in the mysql container")
            return

        self.charm._on_update_status(None)
        self.charm.update_endpoints()
