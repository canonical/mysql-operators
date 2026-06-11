# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Custom event for self-healing the mysql cluster."""

import logging
import typing

from ops.framework import EventBase, Object

if typing.TYPE_CHECKING:
    from charm import MySQLOperatorCharm

logger = logging.getLogger(__name__)


class SelfHealingMySQLEvent(EventBase):
    """A custom event to self-heal the mysql cluster."""


class SelfHealingMySQLObserver(Object):
    """Encapsulates the self-healing of mysql cluster."""

    def __init__(self, charm: "MySQLOperatorCharm"):
        super().__init__(charm, "self-healing-observer")
        self.charm = charm
        self.framework.observe(self.charm.on.heal_mysql_cluster, self._heal_mysql_cluster)

    def _heal_mysql_cluster(self, _) -> None:
        """Self-heal the mysql cluster."""
        if (
            self.charm.peers is None
            or not self.charm._mysql.is_mysqld_running()
            or not self.charm.unit_initialized()
            or not self.charm.upgrade.idle
        ):
            # skip when not initialized, during an upgrade, or when mysqld is not running
            return

        self.charm._on_update_status(None)
        self.charm.update_endpoints()
