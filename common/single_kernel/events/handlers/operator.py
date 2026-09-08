# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import typing

from ops.charm import (
    ActionEvent,
    RelationChangedEvent,
    RelationCreatedEvent,
    RelationJoinedEvent,
)
from ops.framework import Object

from ...core import (
    RELATION_DATABASE,
    RELATION_PEERS,
    USERNAME_MONITOR,
    USERNAME_TO_PASSWORD_KEY,
)
from ...managers import OperatorManager
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class OperatorEventHandler(Object):
    """Class to deal with the operator events."""

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: OperatorManager):
        """Initialize the class attributes."""
        super().__init__(charm, "operator")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager

        self.framework.observe(self.on.get_cluster_status_action, self._on_get_cluster_status)
        self.framework.observe(self.on.get_password_action, self._on_get_password)
        self.framework.observe(self.on.set_password_action, self._on_set_password)
        self.framework.observe(self.on.promote_to_primary_action, self._on_promote_to_primary)
        self.framework.observe(self.on.recreate_cluster_action, self._on_recreate_cluster)

        self.framework.observe(
            self.on[RELATION_PEERS].relation_created,
            self._on_relation_created,
        )
        self.framework.observe(
            self.on[RELATION_PEERS].relation_joined,
            self._on_relation_joined,
        )
        self.framework.observe(
            self.on[RELATION_PEERS].relation_changed,
            self._on_relation_changed,
        )

    def _collect_peer_addresses(self) -> list[str]:
        """Resolve a healthy peer address."""
        peer_addresses = []

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return peer_addresses

        for unit in peers_relation.units:
            peer_address = self._charm.get_unit_address(unit)
            peer_addresses.append(peer_address)

        return peer_addresses

    def _promote_instance(self, event: ActionEvent, force: bool) -> None:
        """Promote the MySQL instance to be cluster primary."""
        logger.info("Setting instance as cluster primary")

        try:
            self._manager.promote_instance(self._charm.get_unit_address(self._charm.unit), force)
        except RuntimeError as e:
            logger.error(f"Failed to promote instance: {e}")
            event.fail(f"Failed to promote instance: {e}")
            raise

        event.set_results({"message": "Instance is now primary"})

    def _promote_cluster(self, event: ActionEvent, force: bool) -> None:
        """Promote the MySQL cluster to be cluster-set primary."""
        if not self._charm.unit.is_leader():
            event.fail("The action can only be run on the leader unit")
            return

        if self._manager.is_cluster_set_primary:
            event.fail("The action can only be run on a replica cluster")
            return

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            event.fail("The action can only be run when the peer relation exists")
            return

        logger.info("Setting cluster as cluster-set primary")

        try:
            self._manager.promote_cluster(self._charm.cluster_name, force)
        except RuntimeError as e:
            logger.error(f"Failed to promote cluster: {e}")
            event.fail(f"Failed to promote cluster: {e}")
            raise

        event.set_results({"message": "Cluster is now primary"})

    def _update_database_endpoints(self, relation_id: int) -> None:
        """Update the endpoints for the database-provider consumers.

        This is a work-around to quickly react upon topology changes when
        there is no good detection mechanism. It targets the situation when
        there are scale-up / scale-down operations on a `database` related application,
        and only the leader can update certain fields.
        """
        if not self._charm.unit.is_leader():
            return

        database_relations = self._charm.model.relations.get(RELATION_DATABASE, [])
        if not database_relations:
            logger.debug(f"Skipping service update: missing {RELATION_DATABASE} relation")
            return

        if self._charm.refreshing:
            logger.debug(f"Skipping service update: charm is refreshing")
            return

        logger.info("Updating database endpoints")
        self._charm.update_app_labels()
        self._charm.database.update_database_endpoints(relation_id)

    def _update_password(self, key: str, val: str) -> None:
        """Update the application password."""
        content = self._charm.secret_store.get_content(secret_label=self._charm.secret_label)
        content.update({key: val})

        self._charm.secret_store.set_content(content, secret_label=self._charm.secret_label)

    def _on_get_cluster_status(self, event: ActionEvent) -> None:
        """Event handler for the get-cluster-status action."""
        cluster_set = event.params.get("cluster-set", False)

        try:
            if cluster_set:
                status = self._manager.fetch_cluster_set_status()
            else:
                status = self._manager.fetch_cluster_status()
        except RuntimeError as e:
            logger.error(f"Failed to fetch status: {e}")
            event.fail(f"Failed to fetch status: {e}")
            return

        event.set_results({"status": json.dumps(status, indent=2)})

    def _on_get_password(self, event: ActionEvent) -> None:
        """Event handler for the get-password action."""
        username = event.params.get("username", "")

        password_key = USERNAME_TO_PASSWORD_KEY.get(username)
        if not password_key:
            event.fail(f"The action cannot be run for user {username}")
            return

        try:
            password = self._charm.secret_store.get_value(
                secret_label=self._charm.secret_label,
                secret_key=password_key,
            )
        except ValueError as e:
            event.fail(f"Failed to fetch password for user {username}: {e}")
            return

        event.set_results({
            "username": username,
            "password": password,
        })

    def _on_set_password(self, event: ActionEvent) -> None:
        """Event handler for the set-password action."""
        username = event.params.get("username", "")
        password = event.params.get("password", "")

        password_key = USERNAME_TO_PASSWORD_KEY.get(username)
        if not password_key:
            event.fail(f"The action cannot be run for user {username}")
            return

        if not self._charm.unit.is_leader():
            event.fail("The action can only be run on the leader unit")
            return

        password = password or self._manager.create_system_password()

        try:
            self._manager.update_cluster_user(username, password)
            self._update_password(password_key, password)
        except (RuntimeError, ValueError) as e:
            event.fail(f"Failed to update password for user {username}: {e}")
            return

        if username == USERNAME_MONITOR:
            self._charm.service_exporter.stop()
            self._charm.service_exporter.start()

    def _on_promote_to_primary(self, event: ActionEvent) -> None:
        """Event handler for the promote-to-primary action."""
        scope = event.params.get("scope", "")
        force = event.params.get("force", False)

        match scope:
            case "cluster":
                self._promote_cluster(event, force)
            case "unit":
                self._promote_instance(event, force)
            case _:
                event.fail(f"The action cannot be run for scope {scope}")
                return

    def _on_recreate_cluster(self, event: ActionEvent) -> None:
        """Event handler for the recreate-cluster action."""
        if not self._charm.unit.is_leader():
            event.fail("The action can only be run on the leader unit")
            return

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            event.fail("The action can only be run when the peer relation exists")
            return

        instance_label = self._charm.get_unit_label(self._charm.unit)
        cluster_set_name = self._charm.config.cluster_set_name

        logger.info("Recreating cluster")

        try:
            self._manager.recreate_cluster(instance_label, cluster_set_name)
            self._charm.unit.status = self._helpers.build_unit_status()
            self._charm.app.status = self._helpers.build_app_status()
        except RuntimeError as e:
            event.fail(f"Failed to recreate cluster: {e}")
            return

    def _on_relation_created(self, _: RelationCreatedEvent) -> None:
        """Event handler for the relation-created event."""
        self._charm.set_unit_address(self._charm.unit, RELATION_PEERS)

    def _on_relation_joined(self, _: RelationJoinedEvent) -> None:
        """Event handler for the relation-joined event."""
        if not self._charm.get_unit_address(self._charm.unit, RELATION_PEERS):
            self._charm.set_unit_address(self._charm.unit, RELATION_PEERS)

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event handler for the relation-changed event."""
        self._update_database_endpoints(event.relation.id)

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.debug(f"Deferring cluster joining: missing {RELATION_PEERS} relation")
            event.defer()
            return

        if self._manager.get_instance_state() != "waiting":
            return

        instance_label = self._charm.get_unit_label(self._charm.unit)
        instance_host = self._charm.get_unit_address(self._charm.unit)

        if self._manager.check_instance_join_cluster(instance_label, self._charm.cluster_name):
            self._manager.join_instance(
                instance_label=instance_label,
                instance_host=instance_host,
                addresses=self._collect_peer_addresses(),
            )

        logger.info(f"Succeeded to join instance {instance_label} to the cluster")
        self._manager.update_state()
