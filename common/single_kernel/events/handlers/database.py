# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import RelationBrokenEvent, RelationDepartedEvent
from ops.framework import Object
from ops.model import ActiveStatus, BlockedStatus

from ...core import RELATION_DATABASE, ROLENAME_ROUTER
from ...libs import DatabaseProviderEventHandlers, DatabaseRequestedEvent
from ...managers import DatabaseManager
from ..helpers import Helpers

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class DatabaseEventHandler(Object):
    """Class to deal with the database provider events."""

    def __init__(self, charm: Operator, manager: DatabaseManager, helpers: Helpers):
        """Initialize the class attributes."""
        super().__init__(charm, "database")
        self._charm = charm
        self._manager = manager
        self._helpers = helpers

        self._provider_events = DatabaseProviderEventHandlers(
            charm=charm,
            relation_data=self._manager._state._relation_data,
        )

        self.framework.observe(
            self._provider_events.on.database_requested,
            self._on_database_requested,
        )
        self.framework.observe(
            self._charm.on[RELATION_DATABASE].relation_broken,
            self._on_database_relation_broken,
        )
        self.framework.observe(
            self._charm.on[RELATION_DATABASE].relation_departed,
            self._on_database_relation_departed,
        )

    @staticmethod
    def _build_relation_username(relation_id: int, suffix: str = "") -> str:
        """Build a username for the requested database.

        The username must be unique and smaller than 26 characters
        """
        return f"relation-{relation_id}{suffix}"[:26]

    def _on_database_requested(self, event: DatabaseRequestedEvent) -> None:
        """Event handler for the database-requested event."""
        if not self._charm.initialized:
            logger.debug("Deferring database creation: charm not initialized")
            event.defer()
            return

        if not self._manager.is_cluster_primary:
            logger.debug("Skipping database creation: instance is not primary")
            return

        extra_roles = event.extra_user_roles or ""
        extra_roles = extra_roles.split(",")

        database = event.database
        if not database:
            logger.error("Failed to fetch requested database name")
            return

        model_id = self._charm.model.uuid.replace("-", "")
        username = self._build_relation_username(event.relation.id, f"_{model_id}")

        try:
            if ROLENAME_ROUTER not in extra_roles:
                self._manager.create_database(database)

            self._manager.create_database_user(database, username, extra_roles)
            self._manager.set_version()
        except RuntimeError as e:
            logger.error(f"Failed to create the requested database: {e}")
            self._charm.set_unit_status(BlockedStatus("Failed to create scoped user"))
            return

        # TODO: Get cluster endpoints
        # self.database.set_endpoints(relation_id, f"{primary_endpoint}:3306")
        # self.database.set_read_only_endpoints(relation_id, f"{replicas_endpoint}:3306")

        logger.info(f"Created user for app {event.app.name}")
        self._charm.set_unit_status(ActiveStatus())

    def _on_database_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Event handler for the relation-broken event."""
        if self._manager.get_removing_flag():
            logger.debug("Skipping database user removal: instance is tearing down")
            return

        if not self._manager.is_cluster_primary:
            logger.debug("Skipping database user removal: instance is not primary")
            return

        model_id = self._charm.model.uuid.replace("-", "")
        username = self._build_relation_username(event.relation.id, f"_{model_id}")

        try:
            self._manager.delete_users(username)
        except RuntimeError as e:
            logger.error(f"Failed to delete users from {event.app.name} app: {e}")

    def _on_database_relation_departed(self, event: RelationDepartedEvent) -> None:
        """Event handler for the relation-departed event."""
        if event.departing_unit.name == self._charm.unit.name:
            self._manager.set_removing_flag()

        if not self._manager.is_cluster_primary:
            logger.debug("Skipping router removal: instance is not primary")
            return

        router_user = self._build_relation_username(event.relation.id)
        router_name = event.departing_unit.name

        try:
            self._manager.remove_router(router_user, router_name)
        except RuntimeError as e:
            logger.error(f"Failed to remove router from {event.app.name} app: {e}")
