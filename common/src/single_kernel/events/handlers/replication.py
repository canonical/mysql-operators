# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from time import sleep

from mysql_shell.models import ClusterGlobalStatus, ClusterRole
from ops.charm import ActionEvent, RelationBrokenEvent, RelationChangedEvent, RelationCreatedEvent
from ops.framework import Object
from ops.model import (
    BlockedStatus,
    MaintenanceStatus,
    SecretNotFoundError,
    WaitingStatus,
)

from ...core import (
    PASSWORD_KEY_BACKUPS,
    PASSWORD_KEY_MONITOR,
    PASSWORD_KEY_OPERATOR,
    PASSWORD_KEY_REPLICATION,
    RELATION_RPL_CONSUMER,
    RELATION_RPL_OFFERER,
    USERNAME_BACKUPS,
    USERNAME_MONITOR,
    USERNAME_OPERATOR,
    USERNAME_REPLICATION,
)
from ...managers import (
    ReplicationConsumingManager,
    ReplicationOfferingManager,
    ReplicationStatus,
)
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)

# Credentials that must be kept in sync between primary and replica clusters.
# The operator password MUST come last: updating it invalidates the current
# executor credentials, so it is refreshed explicitly after the loop.
_CREDENTIALS_TO_SYNC: dict[str, str] = {
    PASSWORD_KEY_REPLICATION: USERNAME_REPLICATION,
    PASSWORD_KEY_MONITOR: USERNAME_MONITOR,
    PASSWORD_KEY_BACKUPS: USERNAME_BACKUPS,
    PASSWORD_KEY_OPERATOR: USERNAME_OPERATOR,
}

# Seconds a non-leader unit pauses in relation-broken to let the leader
# update app peer data before followers read it.
_NON_LEADER_BROKEN_DELAY = 10


class ReplicationEventHandler(Object):
    """Class to deal with the async replication events."""

    def __init__(
        self,
        charm: BaseCharm,
        helpers: EventHelpers,
        offering_manager: ReplicationOfferingManager,
        consuming_manager: ReplicationConsumingManager,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "replication")
        self._charm = charm
        self._helpers = helpers
        self._offering = offering_manager
        self._consuming = consuming_manager

        # Offer-side events
        self.framework.observe(
            self._charm.on[RELATION_RPL_OFFERER].relation_created,
            self._on_offer_created,
        )
        self.framework.observe(
            self._charm.on[RELATION_RPL_OFFERER].relation_changed,
            self._on_offer_changed,
        )
        self.framework.observe(
            self._charm.on[RELATION_RPL_OFFERER].relation_broken,
            self._on_offer_broken,
        )

        # Consumer-side events
        self.framework.observe(
            self._charm.on[RELATION_RPL_CONSUMER].relation_created,
            self._on_consumer_created,
        )
        self.framework.observe(
            self._charm.on[RELATION_RPL_CONSUMER].relation_changed,
            self._on_consumer_changed,
        )
        self.framework.observe(
            self._charm.on[RELATION_RPL_CONSUMER].relation_broken,
            self._on_consumer_broken,
        )

        # Secret propagation – observed on both sides, branched at runtime
        self.framework.observe(
            self._charm.on.secret_changed,
            self._on_secret_changed,
        )

        # Actions
        self.framework.observe(
            self._charm.on.create_replication_action,
            self._on_create_replication,
        )
        self.framework.observe(
            self._charm.on.promote_to_primary_action,
            self._on_promote_to_primary,
        )
        self.framework.observe(
            self._charm.on.rejoin_cluster_action,
            self._on_rejoin_cluster,
        )

    @property
    def idle(self) -> bool:
        """Return whether async replication is not in an active transition."""
        if not self._charm.unit.is_leader():
            return True

        if self._charm.model.get_relation(RELATION_RPL_OFFERER):
            if self._offering.get_ready_flag():
                return False
            return self._offering.get_status() in (
                ReplicationStatus.READY,
                ReplicationStatus.UNINITIALIZED,
            )

        if self._charm.model.get_relation(RELATION_RPL_CONSUMER):
            target_members = len(self._charm.units)
            return self._consuming.get_status(target_members) in (
                ReplicationStatus.READY,
                ReplicationStatus.UNINITIALIZED,
            )

        return True

    def _create_replication_secret(self):
        """Create a Juju secret containing only the password entries from the app secret."""
        app_secret = self._charm.model.get_secret(label=self._charm.secret_label)
        all_content = app_secret.peek_content()
        password_content = {k: v for k, v in all_content.items() if "password" in k}
        return self._charm.model.app.add_secret(content=password_content)

    def _remove_replication_secret(self) -> None:
        """Delete the replication Juju secret if one was created."""
        secret_id = self._offering.get_secret_id()
        if not secret_id:
            logger.debug("No replication secret to remove")
            return

        try:
            secret = self._charm.model.get_secret(id=secret_id)
            secret.remove_all_revisions()
            logger.debug("Replication secret removed")
        except SecretNotFoundError:
            logger.warning(f"Replication secret {secret_id!r} not found; skipping removal")

    def _fetch_replication_secret(self) -> dict[str, str] | None:
        """Retrieve the credential content from the replication secret.

        Returns None when the secret is not yet accessible.
        """
        secret_id = self._consuming.get_remote_secret_id()
        if not secret_id:
            return None

        try:
            secret = self._charm.model.get_secret(id=secret_id)
            return secret.peek_content()
        except SecretNotFoundError:
            return None

    def _apply_synced_credentials(self, credentials: dict[str, str]) -> None:
        """Update local system user passwords and persist them to the app secret."""
        for password_key, username in _CREDENTIALS_TO_SYNC.items():
            password = credentials.get(password_key)
            if not password:
                continue

            self._consuming.sync_user_password(username, password)

            content = self._charm.secret_store.get_content(secret_label=self._charm.secret_label)
            content[password_key] = password
            self._charm.secret_store.set_content(content, secret_label=self._charm.secret_label)
            logger.debug(f"Synced password for user {username!r}")

        # The operator password was updated last in the loop above.  The executor
        # still holds the old password, which would cause Access Denied on any
        # subsequent MySQL call within this hook (e.g. dissolve_cluster).  Refresh
        # the connection details so the rest of the hook uses the new credentials.
        if op_password := credentials.get(PASSWORD_KEY_OPERATOR):
            self._consuming.refresh_operator_password(op_password)

    def _refresh_status(self) -> None:
        """Rebuild and apply the current unit and app status."""
        self._charm.set_unit_status(self._helpers.build_unit_status())
        self._charm.set_app_status(self._helpers.build_app_status())

    def _on_offer_created(self, event: RelationCreatedEvent) -> None:
        """Validate the offer side on relation creation and set the ready flag."""
        if not self._charm.unit.is_leader():
            return

        if not self._helpers.initialized:
            logger.info("Deferring offer created: charm not initialized")
            event.defer()
            return

        if self._offering.get_cluster_remove_flag():
            logger.error("Failed to create offering: cluster is in read-only mode")
            self._charm.set_unit_status(BlockedStatus("Cluster is in read-only mode"))
            self._charm.set_app_status(BlockedStatus("Cluster is in read-only mode"))
            return

        if self._offering.cluster_role == ClusterRole.REPLICA:
            logger.error(f"Failed to create offering: cluster is a replica")
            self._charm.set_unit_status(BlockedStatus("Cluster is a replica"))
            self._charm.set_app_status(BlockedStatus("Cluster is a replica"))
            return

        self._offering.set_cluster_set_name(self._charm.cluster_set_name)
        self._offering.set_ready_flag(True)

        ready_message = "Ready to create replication"
        self._charm.set_unit_status(BlockedStatus(ready_message))
        self._charm.set_app_status(BlockedStatus(ready_message))

    def _on_offer_changed(self, event: RelationChangedEvent) -> None:
        """React to state transitions on the offer side."""
        if not self._charm.unit.is_leader():
            return

        status = self._offering.get_status()
        logger.debug(f"Offer-side replication status: {status}")

        if status == ReplicationStatus.INITIALIZING:
            self._add_replica_cluster(event)
        elif status == ReplicationStatus.RECOVERING:
            self._charm.set_unit_status(MaintenanceStatus("Replica cluster in recovery"))
        elif status == ReplicationStatus.READY:
            self._refresh_status()

    def _add_replica_cluster(self, event: RelationChangedEvent) -> None:
        """Add the replica cluster to the cluster-set (offer side, INITIALIZING state)."""
        if not self._offering.get_remote_cluster_name():
            logger.debug("Consumer identity not yet in databag; deferring")
            event.defer()
            return

        self._charm.set_unit_status(MaintenanceStatus("Adding replica cluster"))

        _, ro_endpoints, _ = self._helpers.build_cluster_endpoints(RELATION_RPL_OFFERER)
        donor = ro_endpoints[0] if ro_endpoints else None

        self._offering.create_cluster_replica(donor=donor)
        logger.info("Replica cluster created")
        self._refresh_status()

    def _on_offer_broken(self, event: RelationBrokenEvent) -> None:
        """Remove the replica cluster and clean up the replication secret."""
        if self._charm.unit.is_leader():
            self._remove_replication_secret()
            self._offering.remove_cluster_replica()
            self._refresh_status()

        self._offering.delete_ready_flag()

    def _on_consumer_created(self, event: RelationCreatedEvent) -> None:
        """Handle relation creation on the consumer side."""
        if not self._charm.unit.is_leader():
            self._handle_consumer_non_leader_created()
            return

        if not self._helpers.initialized:
            logger.info("Deferring consumer created: charm not initialized")
            event.defer()
            return

        self._charm.set_app_status(
            MaintenanceStatus("Waiting for create-replication on the offer side")
        )
        self._charm.set_unit_status(WaitingStatus("Awaiting credentials from primary cluster"))

    def _handle_consumer_non_leader_created(self) -> None:
        """Inhibit auto-recovery on non-leader units while the cluster joins the cluster-set."""
        unit_state = self._charm._build_state().unit
        if unit_state.get_instance_state() != "waiting":
            unit_state.set_instance_state("waiting")
            self._charm.set_unit_status(
                WaitingStatus("Waiting for replica cluster to be configured")
            )

    def _on_consumer_changed(self, event: RelationChangedEvent) -> None:
        """React to state transitions on the consumer side."""
        if not self._charm.unit.is_leader():
            self._handle_consumer_non_leader_changed()
            return

        if not self._helpers.initialized:
            logger.info("Deferring consumer changed: charm not initialized")
            event.defer()
            return

        target_members = len(self._charm.units)
        status = self._consuming.get_status(target_members)
        logger.debug(f"Consumer-side replication status: {status}")

        if status == ReplicationStatus.SYNCING:
            self._sync_credentials(event)
        elif status == ReplicationStatus.RECOVERING:
            self._handle_consumer_recovering()
        elif status == ReplicationStatus.READY:
            self._handle_consumer_ready()

    def _handle_consumer_non_leader_changed(self) -> None:
        """Allow non-leader units to rejoin the cluster after primary recovery."""
        peer_state = self._charm._build_state()
        replica_initialized = self._consuming.get_replica_initialized()
        rejoin_flag = peer_state.app.get_cluster_rejoin_flag()

        if not (replica_initialized or rejoin_flag):
            return

        unit_label = self._charm.get_unit_label(self._charm.unit)
        if not self._consuming.is_instance_in_cluster(unit_label):
            logger.debug("Resetting non-leader unit state to allow cluster rejoin")
            peer_state.unit.set_instance_state("waiting")
            self._charm.set_unit_status(WaitingStatus("Waiting to join the cluster"))

    def _sync_credentials(self, event: RelationChangedEvent) -> None:
        """Sync system user passwords from the primary cluster (consumer side, SYNCING state)."""
        if self._consuming.returning_cluster:
            self._handle_returning_cluster(event)
            return

        target_members = len(self._charm.units)
        online_members = self._consuming.count_online_members()
        if online_members < target_members:
            logger.debug(
                f"Cluster not fully initialized ({online_members}/{target_members}); deferring"
            )
            self._charm.set_unit_status(WaitingStatus("Waiting for all units to join the cluster"))
            event.defer()
            return

        try:
            self._consuming.check_cluster_version()
        except RuntimeError as e:
            logger.error(str(e))
            self._charm.set_unit_status(
                BlockedStatus("MySQL version mismatch. Check logs and remove relation")
            )
            return

        credentials = self._fetch_replication_secret()
        if credentials is None:
            logger.debug("Replication secret not yet accessible; deferring")
            event.defer()
            return

        self._charm.set_unit_status(MaintenanceStatus("Syncing credentials"))
        self._charm.set_app_status(MaintenanceStatus("Setting up replication"))
        self._apply_synced_credentials(credentials)

        self._charm.set_unit_status(MaintenanceStatus("Dissolving replica cluster"))
        self._consuming.dissolve_cluster()

        self._consuming.rename_cluster_if_conflicting()
        self._consuming.set_consumer_identity(
            cluster_name=self._charm.cluster_name,
            instance_address=self._charm.get_unit_address(self._charm.unit, RELATION_RPL_CONSUMER),
            instance_label=self._charm.get_unit_label(self._charm.unit),
        )
        logger.debug("Consumer identity shared with primary cluster")
        self._charm.set_unit_status(WaitingStatus("Waiting for primary cluster"))

    def _handle_returning_cluster(self, event: RelationChangedEvent) -> None:
        """Recreate the local cluster before syncing credentials (returning cluster path)."""
        logger.debug("Returning cluster: recreating standalone cluster before credential sync")
        instance_label = self._charm.get_unit_label(self._charm.unit)
        self._consuming.recreate_standalone_cluster(instance_label)
        event.defer()

    def _handle_consumer_recovering(self) -> None:
        """Set state flags to allow secondary units to join during cluster recovery."""
        self._charm.set_app_status(MaintenanceStatus("Recovering replica cluster"))
        self._charm.set_unit_status(
            WaitingStatus("Waiting for recovery to complete on other units")
        )
        logger.debug("Awaiting other units to join the replica cluster")

        peer_unit_state = self._charm._build_state().unit
        peer_unit_state.set_instance_state("ONLINE")
        peer_unit_state.set_instance_role("PRIMARY")

    def _handle_consumer_ready(self) -> None:
        """Finalize the consumer side once the replica cluster is ready."""
        logger.info("Replica cluster is ready")
        self._consuming.sync_cluster_set_domain_name()
        self._refresh_status()

    def _on_consumer_broken(self, _: RelationBrokenEvent) -> None:
        """Wait for the primary cluster to dissolve this cluster."""
        if self._consuming.cluster_role != ClusterRole.REPLICA:
            # This cluster is the primary in the cluster-set; nothing to dissolve locally.
            self._refresh_status()
            self._consuming.delete_ready_flag()
            return

        self._charm.set_unit_status(WaitingStatus("Waiting for cluster to be dissolved"))

        try:
            self._consuming.wait_cluster_dissolving()
        except RuntimeError:
            self._charm.set_unit_status(
                BlockedStatus("Replica cluster not dissolved after relation broken")
            )
            logger.warning(
                "Replica cluster was not dissolved by the primary cluster after relation broken. "
                "This cluster can be promoted to primary with the `promote-to-primary` action."
            )
            self._consuming.delete_ready_flag()
            return

        self._charm.set_unit_status(BlockedStatus("Standalone read-only unit."))
        peer_state = self._charm._build_state()
        peer_state.unit.set_instance_state("waiting")

        if not self._charm.unit.is_leader():
            sleep(_NON_LEADER_BROKEN_DELAY)
            self._consuming.delete_ready_flag()
            return

        self._charm.set_app_status(BlockedStatus("Recreate or rejoin cluster."))
        peer_state.app.set_cluster_removed_flag(True)
        logger.info(
            "Replica cluster dissolved. "
            "Use `recreate-cluster` to rebuild or rejoin it to the cluster-set."
        )
        self._consuming.delete_ready_flag()

    def _on_create_replication(self, event: ActionEvent) -> None:
        """Set up the offer side as the primary cluster in the cluster-set."""
        if not self._charm.unit.is_leader():
            event.fail("Only the leader unit can set up replication")
            return

        if not self._offering.get_ready_flag():
            event.fail("Relation created but not ready")
            return

        if self._charm.model.get_relation(RELATION_RPL_CONSUMER):
            event.fail("Only the offer side can be set up as primary cluster")
            return

        if not self._helpers.initialized:
            event.fail("Wait until the cluster is initialized")
            return

        if self._offering.get_secret_id():
            event.fail("create-replication has already been run")
            return

        self._charm.set_app_status(MaintenanceStatus("Setting up replication"))
        self._charm.set_unit_status(MaintenanceStatus("Sharing credentials with replica cluster"))

        replication_secret = self._create_replication_secret()
        replication_secret.grant(self._charm.model.get_relation(RELATION_RPL_OFFERER))

        replication_name = event.params.get("name", "default")
        self._offering.set_cluster_info(self._charm.cluster_name, replication_name)
        self._offering.set_secret_id(replication_secret.id or "")
        self._offering.delete_ready_flag()

        logger.info(f"Replication setup complete: name={replication_name!r}")
        event.set_results({"message": "Replication created"})

    def _on_promote_to_primary(self, event: ActionEvent) -> None:
        """Event handler for the promote-to-primary action."""
        scope = event.params.get("scope", "")
        force = event.params.get("force", False)

        if scope != "cluster":
            return

        if not self._charm.unit.is_leader():
            event.fail("The action can only be run on the leader unit")
            return
        if self._offering.cluster_role != ClusterRole.REPLICA:
            event.fail("The action can only be run on a replica cluster")
            return

        logger.info("Setting cluster as cluster-set primary")

        try:
            self._offering.promote_cluster(self._charm.cluster_name, force)
        except RuntimeError as e:
            logger.error(f"Failed to promote cluster: {e}")
            event.fail(f"Failed to promote cluster: {e}")
            return
        else:
            event.set_results({"message": "Cluster is now primary"})

        self._refresh_status()

    def _on_rejoin_cluster(self, event: ActionEvent) -> None:
        """Rejoin an invalidated cluster back into the cluster-set."""
        cluster_name = event.params.get("cluster-name", "")
        if not cluster_name:
            event.fail("Invalid or empty cluster name")
            return

        state = self._offering.get_replica_cluster_state(cluster_name)
        if state is None:
            event.fail(f"Cluster {cluster_name!r} not found in cluster-set")
            return
        if state != ClusterGlobalStatus.INVALIDATED:
            event.fail(f"Cluster state is {state!r}. Only INVALIDATED clusters can be rejoined")
            return

        try:
            self._offering.rejoin_cluster(cluster_name)
        except Exception:
            logger.exception(f"Failed to rejoin cluster {cluster_name!r}")
            event.fail(f"Failed to rejoin cluster {cluster_name!r} to the cluster-set")
            return

        message = f"Cluster {cluster_name!r} rejoined to cluster-set"
        logger.info(message)
        event.set_results({"message": message})

    def _on_secret_changed(self, event) -> None:
        """Propagate credential changes across the cluster-set."""
        if not self._charm.unit.is_leader():
            return

        if self._charm.model.get_relation(RELATION_RPL_OFFERER):
            self._propagate_secret_to_consumer(event)
        elif self._charm.model.get_relation(RELATION_RPL_CONSUMER):
            self._propagate_secret_from_offer(event)

    def _propagate_secret_to_consumer(self, event) -> None:
        """Push updated credentials to the consumer cluster (offer side)."""
        if self._offering.get_status() != ReplicationStatus.READY:
            return

        if event.secret.label != self._charm.secret_label:
            return

        secret_id = self._offering.get_secret_id()
        if not secret_id:
            return

        replication_secret = self._charm.model.get_secret(id=secret_id)
        replication_secret.set_content(event.secret.peek_content())
        logger.debug("Replication secret updated with new credentials")

    def _propagate_secret_from_offer(self, event) -> None:
        """Apply incoming credential update from the offer cluster (consumer side)."""
        remote_secret_id = self._consuming.get_remote_secret_id()
        if not remote_secret_id:
            return

        if event.secret.id.removeprefix("secret:") not in remote_secret_id:
            logger.info("Secret change is unrelated to replication; skipping")
            return

        credentials = self._fetch_replication_secret()
        if credentials is None:
            return

        app_secret = self._charm.model.get_secret(label=self._charm.secret_label)
        app_secret.set_content(credentials)
        logger.debug("Local app secret updated from offer cluster credentials")
