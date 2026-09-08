# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import (
    RelationBrokenEvent,
    RelationCreatedEvent,
    RelationDepartedEvent,
    RelationJoinedEvent,
)
from ops.framework import Object
from ops.model import ActiveStatus, BlockedStatus

from ...core import RELATION_DATABASE, ROLENAME_ROUTER
from ...libs import DatabaseProvides, DatabaseRequestedEvent
from ...managers import DatabaseManager
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class DatabaseEventHandler(Object):
    """Class to deal with the database provider events."""

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: DatabaseManager):
        """Initialize the class attributes."""
        super().__init__(charm, "database")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager

        self._provider = DatabaseProvides(
            charm=charm,
            relation_name=RELATION_DATABASE,
        )

        self.framework.observe(
            self._provider.on.database_requested,
            self._on_database_requested,
        )
        self.framework.observe(
            self._charm.on[RELATION_DATABASE].relation_created,
            self._on_relation_created,
        )
        self.framework.observe(
            self._charm.on[RELATION_DATABASE].relation_joined,
            self._on_relation_joined,
        )
        self.framework.observe(
            self._charm.on[RELATION_DATABASE].relation_broken,
            self._on_relation_broken,
        )
        self.framework.observe(
            self._charm.on[RELATION_DATABASE].relation_departed,
            self._on_relation_departed,
        )

    def _build_database_relation_username(self, relation_id: int) -> str:
        """Build a username for the requested database."""
        model_id = self._charm.model.uuid.replace("-", "")
        username = f"relation-{relation_id}_{model_id}"

        return username[:26]

    def _set_database(self, relation_id: int, database: str) -> None:
        """Create + set the requested database."""
        try:
            self._manager.create_database(database)
            self._provider.set_database(relation_id, database)
        except RuntimeError as e:
            logger.error(f"Failed to create the database: {e}")
            raise

    def _set_database_user(self, relation_id: int, database: str, extra_roles: list[str]) -> None:
        """Create + set the requested database user."""
        username = self._build_database_relation_username(relation_id)
        password = self._provider.fetch_my_relation_field(relation_id, "password")

        try:
            password = self._manager.create_database_user(database, username, password, extra_roles)
            ________ = self._provider.set_credentials(relation_id, username, password)
        except RuntimeError as e:
            logger.error(f"Failed to create the database user: {e}")
            raise

    def _set_database_version(self, relation_id: int) -> None:
        """Create + set the requested database version."""
        try:
            version = self._manager.fetch_version()
            _______ = self._provider.set_version(relation_id, version)
        except RuntimeError as e:
            logger.error(f"Failed to fetch database version: {e}")
            raise

    def _on_database_requested(self, event: DatabaseRequestedEvent) -> None:
        """Event handler for the database-requested event."""
        if not self._helpers.initialized:
            logger.debug("Deferring database creation: charm not initialized")
            event.defer()
            return

        if not self._manager.is_cluster_primary:
            logger.debug("Skipping database creation: instance is not primary")
            return

        database = event.database
        if not database:
            logger.error("Failed to fetch requested database name")
            return

        relation_id = event.relation.id
        extra_roles = event.extra_user_roles or ""
        extra_roles = extra_roles.split(",")

        try:
            if ROLENAME_ROUTER not in extra_roles:
                self._set_database(relation_id, database)
            self._set_database_user(relation_id, database, extra_roles)
            self._set_database_version(relation_id)
        except RuntimeError:
            self._charm.unit.status = BlockedStatus("Failed to create database")

        self.update_database_endpoints(relation_id)
        self._charm.unit.status = ActiveStatus()

    def _on_relation_created(self, _: RelationCreatedEvent) -> None:
        """Event handler for the relation-created event."""
        self._charm.set_unit_address(self._charm.unit, RELATION_DATABASE)

    def _on_relation_joined(self, _: RelationJoinedEvent) -> None:
        """Event handler for the relation-joined event."""
        if not self._charm.get_unit_address(self._charm.unit, RELATION_DATABASE):
            self._charm.set_unit_address(self._charm.unit, RELATION_DATABASE)

    def _on_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Event handler for the relation-broken event."""
        if self._manager.get_removing_flag():
            logger.debug("Skipping database user removal: instance is tearing down")
            return

        if not self._manager.is_cluster_primary:
            logger.debug("Skipping database user removal: instance is not primary")
            return

        username = self._build_database_relation_username(event.relation.id)

        try:
            self._manager.delete_users(username)
        except RuntimeError as e:
            logger.error(f"Failed to delete users from {event.app.name} app: {e}")

    def _on_relation_departed(self, event: RelationDepartedEvent) -> None:
        """Event handler for the relation-departed event."""
        if event.departing_unit.name == self._charm.unit.name:
            self._manager.set_removing_flag()

        if not self._manager.is_cluster_primary:
            logger.debug("Skipping router removal: instance is not primary")
            return

        router_user = f"relation-{event.relation.id}"
        router_name = f"{event.departing_unit.name}"

        try:
            self._manager.remove_router(router_user, router_name)
        except RuntimeError as e:
            logger.error(f"Failed to remove router from {event.app.name} app: {e}")

    def update_database_endpoints(self, relation_id: int) -> None:
        """Create + set the requested database endpoints."""
        endpoints = self._charm.build_database_endpoints()
        rw_endpoints = ",".join(endpoints["primary"])
        ro_endpoints = ",".join(endpoints["replicas"])

        self._provider.set_endpoints(relation_id, rw_endpoints)
        self._provider.set_read_only_endpoints(relation_id, ro_endpoints)
