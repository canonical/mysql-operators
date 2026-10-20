# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from mysql_shell.models import ClusterGlobalStatus, ClusterRole

from ....state import PeerState, ReplicationState
from ....workload import BaseSystem
from ...clients import Clients
from .replication_status import ReplicationStatus

logger = logging.getLogger(__name__)


class ReplicationOffererManager:
    """Class to deal with the replication operations."""

    def __init__(
        self,
        repl_state_local: ReplicationState,
        repl_state_remote: ReplicationState,
        peer_state: PeerState,
        system: BaseSystem,
        clients: Clients,
    ):
        """Initialize the class attributes."""
        self._repl_state_local = repl_state_local
        self._repl_state_remote = repl_state_remote
        self._peer_state = peer_state
        self._system = system
        self._clients = clients

    def get_cluster_removed_flag(self) -> bool | None:
        """Get the cluster removed flag."""
        return self._peer_state.app.get_cluster_removed_flag()

    def get_replication_ready_flag(self) -> bool | None:
        """Get the replication ready flag."""
        return self._repl_state_local.app.get_replication_ready_flag()

    def get_secret_id(self) -> str | None:
        """Get the secret ID."""
        return self._repl_state_local.app.get_secret_id()

    def set_cluster_set_name(self, name: str) -> None:
        """Set the cluster-set name."""
        self._repl_state_local.app.set_cluster_set_name(name)

    def set_replication_ready_flag(self, flag: bool) -> None:
        """Set the replication ready flag."""
        self._repl_state_local.app.set_replication_ready_flag(flag)

    def delete_replication_ready_flag(self) -> None:
        """Delete the replication ready flag."""
        self._repl_state_local.app.delete_replication_ready_flag()

    def is_primary_cluster(self) -> bool:
        """Return whether the MySQL cluster is the primary."""
        return self._clients.cluster.fetch_role() == ClusterRole.PRIMARY

    def build_status(self) -> ReplicationStatus:
        """Build the status out of the replication-offerer relation."""
        local_secret = self._repl_state_local.app.get_secret_id()
        if not local_secret:
            return ReplicationStatus.UNINITIALIZED

        remote_address = self._repl_state_remote.app.get_instance_address()
        remote_cluster = self._repl_state_remote.app.get_cluster_name()
        if not remote_address:
            return ReplicationStatus.SYNCING

        if remote_address and remote_cluster:
            state = self._clients.cluster_set.fetch_cluster_state(remote_cluster)

            # When the cluster does not have a cluster-set replication state,
            # it means the cluster is not in the cluster-set (just dissolved)
            if not state:
                return ReplicationStatus.INITIALIZING

            match state:
                case ClusterGlobalStatus.OK:
                    return ReplicationStatus.READY
                case ClusterGlobalStatus.OK_NOT_CONSISTENT:
                    return ReplicationStatus.READY
                case ClusterGlobalStatus.INVALIDATED:
                    return ReplicationStatus.READY
                case ClusterGlobalStatus.UNKNOWN:
                    return ReplicationStatus.INITIALIZING
                case _:
                    return ReplicationStatus.RECOVERING

        return ReplicationStatus.RECOVERING

    def check_cluster_rejoin(self, cluster_name: str) -> bool:
        """Check whether the cluster can rejoin the cluster-set."""
        clusters = self._clients.cluster_set.fetch_clusters()
        state = self._clients.cluster_set.fetch_cluster_state(cluster_name)

        if cluster_name not in clusters.keys():
            return False
        if state != ClusterGlobalStatus.INVALIDATED:
            return False

        return True

    def create_cluster_replica(self, donor: str | None) -> None:
        """Create a cluster replica."""
        logger.info("Creating replica cluster")

        cluster_name = self._repl_state_remote.app.get_cluster_name()
        instance_addr = self._repl_state_remote.app.get_instance_address()
        instance_label = self._repl_state_remote.app.get_instance_label()

        if not cluster_name:
            logger.warning("Skipping cluster creation: cluster name not found")
            return
        if not instance_label:
            logger.warning("Skipping cluster creation: instance label not found")
            return

        self._clients.cluster_set.create_replica_cluster(
            instance_label=instance_label,
            instance_host=instance_addr.split(":")[0],
            cluster_name=cluster_name,
            donor=donor,
        )

        self._repl_state_local.app.set_replica_flag(True)

    def remove_cluster_replica(self, cluster_name: str | None) -> None:
        """Remove a MySQL cluster replica.

        The cluster-name argument must be provided by the caller, given that the
        remote databag may be empty when handling a relation-broken event.
        """
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        logger.info(f"Removing cluster {cluster_name}")

        state = self._clients.cluster_set.fetch_cluster_state(cluster_name)
        if not state:
            return

        match state:
            case ClusterGlobalStatus.INVALIDATED:
                force = True
            case ClusterGlobalStatus.UNKNOWN:
                force = True
            case _:
                force = False

        self._clients.cluster_set.remove_replica_cluster(cluster_name, force=force)

    def rejoin_cluster_replica(self, cluster_name: str) -> None:
        """Rejoin a MySQL cluster replica."""
        self._clients.cluster_set.rejoin_replica_cluster(cluster_name)

    def save_cluster_info(self, secret_id: str, replication_name: str) -> None:
        """Save the cluster information into the databag."""
        logger.info("Setting the cluster information")

        cluster_name = self._peer_state.app.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        cluster_version = self._clients.instance.fetch_version()
        if not cluster_version:
            raise RuntimeError("Cluster version not found")

        self._repl_state_local.app.set_secret_id(secret_id)
        self._repl_state_local.app.set_cluster_name(cluster_name)
        self._repl_state_local.app.set_cluster_version(cluster_version)
        self._repl_state_local.app.set_replication_name(replication_name)

        self._repl_state_local.app.delete_replication_ready_flag()

    def update_state(self) -> None:
        """Update the operator state."""
        role = self._clients.instance.fetch_role()
        state = self._clients.instance.fetch_state()

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._peer_state.unit.set_instance_role(role)
        self._peer_state.unit.set_instance_state(state)
