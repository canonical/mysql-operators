# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops import BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.charm import (
    ActionEvent,
    RelationBrokenEvent,
    RelationChangedEvent,
    RelationCreatedEvent,
    SecretChangedEvent,
)
from ops.framework import Object

from ...core import (
    PASSWORD_KEY_OPERATOR,
    RELATION_REPL_CONSUMER,
    RELATION_REPL_OFFERER,
    USERNAME_OPERATOR,
    USERNAME_TO_PASSWORD_KEY,
)
from ...managers import (
    ReplicationConsumerManager,
    ReplicationOffererManager,
    ReplicationStatus,
)
from ...state import ReplicationAppState
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class ReplicationEventHandler(Object):
    """Class to deal with the operator replication events."""

    def __init__(
        self,
        charm: BaseCharm,
        helpers: EventHelpers,
        manager_consumer: ReplicationConsumerManager,
        manager_offerer: ReplicationOffererManager,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "replication")
        self._charm = charm
        self._helpers = helpers
        self._manager_consumer = manager_consumer
        self._manager_offerer = manager_offerer

        self.framework.observe(
            self._charm.on.create_replication_action,
            self._on_create_replication,
        )

        # Events emitted by the offerer and observed by the consumer
        self.framework.observe(
            self._charm.on[RELATION_REPL_OFFERER].relation_created,
            self._on_offer_relation_created,
        )
        self.framework.observe(
            self._charm.on[RELATION_REPL_OFFERER].relation_changed,
            self._on_offer_relation_changed,
        )
        self.framework.observe(
            self._charm.on[RELATION_REPL_OFFERER].relation_broken,
            self._on_offer_relation_broken,
        )

        # Events emitted by the consumer and observed by the offerer
        self.framework.observe(
            self._charm.on[RELATION_REPL_CONSUMER].relation_created,
            self._on_consumer_relation_created,
        )
        self.framework.observe(
            self._charm.on[RELATION_REPL_CONSUMER].relation_changed,
            self._on_consumer_relation_changed,
        )
        self.framework.observe(
            self._charm.on[RELATION_REPL_CONSUMER].relation_broken,
            self._on_consumer_relation_broken,
        )

        # Events emitted / observed by both sides
        self.framework.observe(
            self._charm.on.secret_changed,
            self._on_secret_changed,
        )

    @property
    def idle(self) -> bool:
        """Return whether the replication functionality is idle."""
        if not self._charm.unit.is_leader():
            return True

        units = len(self._charm.units)

        if self._charm.model.get_relation(RELATION_REPL_OFFERER):
            return self._manager_offerer.build_status() in (
                ReplicationStatus.READY,
                ReplicationStatus.UNINITIALIZED,
            )
        if self._charm.model.get_relation(RELATION_REPL_CONSUMER):
            return self._manager_consumer.build_status(units) in (
                ReplicationStatus.READY,
                ReplicationStatus.UNINITIALIZED,
            )

        return True

    def _fetch_passwords(self) -> dict[str, str]:
        """Fetch the application passwords."""
        secret = self._manager_consumer.get_secret_id()
        content = self._charm.secret_store.get_content(secret_id=secret)

        return content

    def _sync_passwords(self, passwords: dict[str, str]) -> None:
        """Sync the application passwords."""
        for username, password_key in USERNAME_TO_PASSWORD_KEY.items():
            logger.debug(f"Updating password for user: {username}")
            self._manager_consumer.update_cluster_user(username, passwords[password_key])

        self._charm.secret_store.set_content(passwords, secret_label=self._charm.secret_label)

    def _handle_consumer_syncing(self, event: RelationChangedEvent) -> None:
        """Event handler for the replication-consumer changed with SYNC status."""
        logger.info("Replication consumer is syncing credentials")
        instance_label = self._charm.get_unit_label(self._charm.unit)
        instance_units = self._charm.units

        if self._manager_consumer.is_returning_cluster():
            self._manager_consumer.create_cluster(instance_label)
            event.defer()
            return

        if not self._manager_consumer.is_initialized_cluster(len(instance_units)):
            logger.debug("Deferring sync credentials: wait for all units to join the cluster")
            event.defer()
            return

        try:
            passwords = self._fetch_passwords()
        except ValueError:
            logger.debug("Deferring sync credentials: secret not shared")
            event.defer()
            return

        try:
            self._manager_consumer.check_cluster_version()
        except RuntimeError:
            logger.error(f"Skipping sync credentials: cluster version mismatch")
            self._charm.set_unit_status(BlockedStatus("Cluster version mismatch"))
            self._charm.set_app_status(BlockedStatus("Cluster version mismatch"))
            return

        self._charm.set_unit_status(MaintenanceStatus("Syncing credentials"))
        self._charm.set_app_status(MaintenanceStatus("Syncing credentials"))

        self._sync_passwords(passwords)

        self._manager_consumer.dissolve_cluster(
            username=USERNAME_OPERATOR,
            password=passwords[PASSWORD_KEY_OPERATOR],
        )
        self._manager_consumer.save_cluster_info(
            instance_label=self._charm.get_unit_label(self._charm.unit),
            instance_host=self._charm.get_unit_address(self._charm.unit),
        )

        self._charm.set_unit_status(WaitingStatus("Waiting for primary cluster"))
        self._charm.set_app_status(WaitingStatus("Waiting for primary cluster"))

    def _handle_consumer_ready(self, _: RelationChangedEvent) -> None:
        """Event handler for the replication-consumer changed with READY status."""
        logger.info("Replication consumer is ready")
        self._manager_consumer.update_state()
        self._manager_consumer.update_cluster_set_name()

        self._charm.update_app_labels()
        self._charm.set_unit_status(self._helpers.build_unit_status())
        self._charm.set_app_status(self._helpers.build_app_status())

    def _handle_consumer_recovering(self, event: RelationChangedEvent) -> None:
        """Event handler for the replication-consumer changed with RECOVERING status."""
        logger.info("Replication consumer must wait for all units")
        self._manager_consumer.update_state()

        self._charm.update_app_labels()
        self._charm.set_unit_status(WaitingStatus("Recovering replica cluster"))
        self._charm.set_app_status(MaintenanceStatus("Recovering replica cluster"))

        event.defer()

    def _handle_offerer_initializing(self, _: RelationChangedEvent) -> None:
        """Event handler for the replication-offerer changed with INITIALIZING status."""
        logger.info("Replication offerer is adding replica cluster")

        cluster_endpoints = self._helpers.build_cluster_endpoints(RELATION_REPL_OFFERER)
        cluster_donor = cluster_endpoints[1][0] if cluster_endpoints[1] else None

        self._manager_offerer.create_cluster_replica(cluster_donor)
        self._manager_offerer.update_state()

        self._charm.update_app_labels()
        self._charm.set_unit_status(self._helpers.build_unit_status())
        self._charm.set_app_status(self._helpers.build_app_status())

    def _handle_offerer_ready(self, _: RelationChangedEvent) -> None:
        """Event handler for the replication-offerer changed with READY status."""
        logger.info("Replication offerer is ready")
        self._manager_offerer.update_state()

        self._charm.update_app_labels()
        self._charm.set_unit_status(self._helpers.build_unit_status())
        self._charm.set_app_status(self._helpers.build_app_status())

    def _handle_offerer_recovering(self, _: RelationChangedEvent) -> None:
        """Event handler for the replication-offerer changed with RECOVERING status."""
        self._charm.set_unit_status(MaintenanceStatus("Replica cluster in recovery"))
        self._charm.set_app_status(MaintenanceStatus("Replica cluster in recovery"))

    def _update_passwords_offerer(self, event: SecretChangedEvent) -> None:
        """Push updated credentials to the consumer cluster (offer side)."""
        status = self._manager_offerer.build_status()
        if status != ReplicationStatus.READY:
            return

        secret_id = self._manager_offerer.get_secret_id()
        if not secret_id:
            return

        if event.secret.id.removeprefix("secret:") != secret_id:
            logger.debug("Skipping secret changed: secret not related")
            return

        logger.info("Updating replication secret with new passwords")
        self._charm.secret_store.set_content(
            content=event.secret.peek_content(),
            secret_id=secret_id,
        )

    def _update_passwords_consumer(self, event: SecretChangedEvent) -> None:
        """Update application passwords from the replication consumer."""
        secret_id = self._manager_consumer.get_secret_id()
        if not secret_id:
            return

        if event.secret.id.removeprefix("secret:") != secret_id:
            logger.debug("Skipping secret changed: secret not related")
            return

        logger.info("Updating replication secret with consumer passwords")
        self._charm.secret_store.set_content(
            content=self._fetch_passwords(),
            secret_id=secret_id,
        )

    def _on_create_replication(self, event: ActionEvent) -> None:
        """Event handler for the create-replication action."""
        if not self._charm.unit.is_leader():
            event.fail(f"The action can only be run on the leader unit")
            return
        if not self._helpers.initialized:
            event.fail(f"Skipped replication creation: charm is not initialized")
            return

        relation = self._charm.model.get_relation(RELATION_REPL_OFFERER)
        if not relation:
            event.fail(f"Skipped replication creation: {RELATION_REPL_OFFERER} relation not found")
            return

        if not self._manager_offerer.get_replication_ready_flag():
            event.fail(f"Skipped replication creation: relation created but not ready yet")
            return

        self._charm.set_unit_status(MaintenanceStatus("Setting up replication"))
        self._charm.set_app_status(MaintenanceStatus("Setting up replication"))

        logger.info("Creating replication secret")
        content = self._charm.secret_store.get_content(secret_label=self._charm.secret_label)
        secret = self._charm.secret_store.create(content)
        secret.grant(relation)

        self._manager_offerer.save_cluster_info(
            secret_id=secret.id,
            replication_name=event.params.get("name", "default"),
        )

    def _on_offer_relation_created(self, event: RelationCreatedEvent) -> None:
        """Event handler for the relation-created event."""
        if not self._charm.unit.is_leader():
            logger.debug("Skipping offering creation: unit is not leader")
            return
        if not self._helpers.initialized:
            logger.debug("Deferring offering creation: charm not initialized")
            event.defer()
            return

        if self._manager_offerer.get_cluster_removed_flag():
            logger.error("Failed to create offering: cluster is in read-only mode")
            self._charm.set_unit_status(BlockedStatus("Cluster is in read-only mode"))
            self._charm.set_app_status(BlockedStatus("Cluster is in read-only mode"))
            return

        if not self._manager_offerer.is_primary_cluster():
            logger.error(f"Failed to create offering: cluster is a replica")
            self._charm.set_unit_status(BlockedStatus("Cluster is a replica"))
            self._charm.set_app_status(BlockedStatus("Cluster is a replica"))
            return

        self._manager_offerer.set_cluster_set_name(self._charm.cluster_set_name)
        self._manager_offerer.set_replication_ready_flag(True)

        self._charm.set_unit_status(BlockedStatus("Ready to create replication"))
        self._charm.set_app_status(BlockedStatus("Ready to create replication"))

    def _on_offer_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event handler for the relation-changed event."""
        if not self._charm.unit.is_leader():
            logger.debug("Skipping offering changed: unit is not leader")
            return

        state = self._manager_offerer.build_status()

        match state:
            case ReplicationStatus.INITIALIZING:
                self._handle_offerer_initializing(event)
            case ReplicationStatus.READY:
                self._handle_offerer_ready(event)
            case ReplicationStatus.RECOVERING:
                self._handle_offerer_recovering(event)

    def _on_offer_relation_broken(self, event: RelationBrokenEvent) -> None:
        """Event handler for the relation-broken event."""
        if not self._charm.unit.is_leader():
            logger.debug("Skipping secret removal: unit is not leader")
            return

        secret_id = self._manager_offerer.get_secret_id()
        if secret_id:
            logger.info(f"Removing secret {secret_id}")
            self._charm.secret_store.delete(secret_id=secret_id)

        # By the time the relation-broken event is received, the remote databag
        # is no longer accessible. The state must be built from the event data
        remote_app_data = event.relation.data[event.relation.app]
        remote_app_state = ReplicationAppState(remote_app_data)
        cluster_name = remote_app_state.get_cluster_name()

        self._manager_offerer.remove_cluster_replica(cluster_name)

        self._charm.update_app_labels()
        self._charm.set_unit_status(self._helpers.build_unit_status())
        self._charm.set_app_status(self._helpers.build_app_status())

    def _on_consumer_relation_created(self, event: RelationCreatedEvent) -> None:
        """Event handler for the relation-created event."""
        if not self._charm.unit.is_leader():
            logger.debug("Skipping consuming creation: unit is not leader")
            return
        if not self._charm.service_server.running:
            logger.debug("Deferring consuming creation: server is not running")
            event.defer()
            return

        if self._manager_consumer.check_instance_databases():
            logger.warning("Skipping consuming creation: user data found")
            self._charm.set_unit_status(BlockedStatus("User data found"))
            self._charm.set_app_status(BlockedStatus("User data found"))

        self._charm.set_unit_status(WaitingStatus("Waiting to synchronize data"))
        self._charm.set_app_status(MaintenanceStatus("Waiting for create-replication to be run"))

    def _on_consumer_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event handler for the relation-changed event."""
        if not self._charm.unit.is_leader():
            logger.debug("Skipping consuming changed: unit is not leader")
            return
        if not self._charm.service_server.running:
            logger.debug("Deferring consuming changed: server is not running")
            event.defer()
            return

        units = len(self._charm.units)
        state = self._manager_consumer.build_status(units)

        match state:
            case ReplicationStatus.SYNCING:
                self._handle_consumer_syncing(event)
            case ReplicationStatus.READY:
                self._handle_consumer_ready(event)
            case ReplicationStatus.RECOVERING:
                self._handle_consumer_recovering(event)

    def _on_consumer_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Event handler for the relation-broken event."""
        if self._manager_consumer.is_primary_cluster():
            self._charm.update_app_labels()
            self._charm.set_unit_status(self._helpers.build_unit_status())
            self._charm.set_app_status(self._helpers.build_app_status())
            return

        self._charm.set_unit_status(WaitingStatus("Waiting for cluster to be dissolved"))

        try:
            self._manager_consumer.wait_cluster_dissolving()
        except RuntimeError:
            self._charm.set_unit_status(BlockedStatus("Replica cluster not dissolved"))
            return

        logger.info("Replica cluster dissolved. Use `recreate-cluster` or `rejoin-cluster`")

        self._manager_consumer.set_cluster_removed_flag(True)
        self._charm.set_unit_status(BlockedStatus("Standalone read-only unit"))
        self._charm.set_app_status(BlockedStatus("Recreate or rejoin cluster"))

    def _on_secret_changed(self, event: SecretChangedEvent) -> None:
        """Event handler for the secret-changed event."""
        if not self._charm.unit.is_leader():
            logger.debug("Skipping secret changed: unit is not leader")
            return

        if self._charm.model.get_relation(RELATION_REPL_OFFERER):
            self._update_passwords_offerer(event)
        elif self._charm.model.get_relation(RELATION_REPL_CONSUMER):
            self._update_passwords_consumer(event)
