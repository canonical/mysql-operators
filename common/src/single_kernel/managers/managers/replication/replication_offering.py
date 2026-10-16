# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import cached_property

from mysql_shell.models import ClusterGlobalStatus, ClusterRole

from .base import BaseReplicationManager
from .replication_status import ReplicationStatus

logger = logging.getLogger(__name__)


class ReplicationOfferingManager(BaseReplicationManager):
    """Class to deal with the MySQL server replication offering."""

    @cached_property
    def cluster_role(self) -> ClusterRole | None:
        """Return the MySQL cluster role within the cluster-set."""
        return self._clients.cluster.fetch_role()

    def get_status(self, target_members: int = 0) -> ReplicationStatus:
        """Return the current replication status from the offer side.

        The target_members argument is accepted for interface compatibility
        but is not used: the offer side classifies status from cluster-set
        state rather than a member count.
        """
        local_secret = self._state_local.app.get_secret_id()
        if not local_secret:
            return ReplicationStatus.UNINITIALIZED

        remote_address = self._state_remote.app.get_instance_address()
        remote_cluster = self._state_remote.app.get_cluster_name()

        if not remote_address:
            return ReplicationStatus.SYNCING

        if remote_address and remote_cluster:
            match self._clients.cluster_set.fetch_cluster_state(remote_cluster):
                case ClusterGlobalStatus.OK:
                    return ReplicationStatus.READY
                case ClusterGlobalStatus.OK_NOT_CONSISTENT:
                    return ReplicationStatus.READY
                case ClusterGlobalStatus.INVALIDATED:
                    return ReplicationStatus.READY
                case ClusterGlobalStatus.UNKNOWN | None:
                    # None means the cluster is not yet present in the cluster-set,
                    # which is equivalent to UNKNOWN: the replica node needs to be added.
                    return ReplicationStatus.INITIALIZING
                case _:
                    return ReplicationStatus.RECOVERING

        return ReplicationStatus.RECOVERING

    def get_cluster_remove_flag(self) -> bool | None:
        """Return the cluster remove flag from the offer side."""
        return self._peer_state.app.get_cluster_removed_flag()

    def get_secret_id(self) -> str | None:
        """Return the replication secret ID stored in the offer databag."""
        return self._state_local.app.get_secret_id()

    def set_secret_id(self, secret_id: str) -> None:
        """Persist the replication secret ID to the offer databag."""
        self._state_local.app.set_secret_id(secret_id)

    def set_cluster_set_name(self, name: str) -> None:
        """Persist the cluster-set name to the offer databag."""
        self._state_local.app.set_cluster_set_name(name)

    def set_cluster_info(self, cluster_name: str, replication_name: str) -> None:
        """Persist offer-side cluster identity to the local databag.

        Fetches the MySQL version from the running instance so the caller
        does not need to supply it separately.
        """
        cluster_version = self._clients.instance.fetch_version()

        self._state_local.app.set_cluster_name(cluster_name)
        self._state_local.app.set_cluster_version(cluster_version)
        self._state_local.app.set_replication_name(replication_name)

    def get_remote_cluster_name(self) -> str | None:
        """Return the cluster name written by the consumer cluster."""
        return self._state_remote.app.get_cluster_name()

    def create_cluster_replica(self, donor: str | None) -> None:
        """Create a replica cluster in the cluster-set from consumer identity.

        Reads cluster_name, instance_address, and instance_label directly
        from the consumer (remote) databag.
        """
        cluster_name = self._state_remote.app.get_cluster_name()
        instance_addr = self._state_remote.app.get_instance_address()
        instance_label = self._state_remote.app.get_instance_label()

        if not cluster_name:
            logger.warning("Skipping cluster creation: no cluster name in consumer databag")
            return
        if not instance_addr:
            logger.warning("Skipping cluster creation: no instance address in consumer databag")
            return
        if not instance_label:
            logger.warning("Skipping cluster creation: no instance label in consumer databag")
            return

        logger.info(f"Creating replica cluster {cluster_name!r} at {instance_addr!r}")
        self._clients.cluster_set.create_replica_cluster(
            instance_label=instance_label,
            instance_host=instance_addr.split(":")[0],
            cluster_name=cluster_name,
            donor=donor,
        )
        self._state_local.app.set_replica_flag(True)
        logger.info(f"Replica cluster {cluster_name!r} created successfully")

    def remove_cluster_replica(self) -> None:
        """Remove the replica cluster from the cluster-set.

        Reads the cluster name from the consumer (remote) databag and
        determines whether a forced removal is needed from the cluster state.
        """
        cluster_name = self._state_remote.app.get_cluster_name()
        if not cluster_name:
            logger.warning("Skipping cluster removal: no cluster name in consumer databag")
            return

        logger.info(f"Removing replica cluster {cluster_name!r}")

        status = self._clients.cluster_set.fetch_cluster_state(cluster_name)
        if not status:
            logger.warning(f"Could not fetch state for cluster {cluster_name!r}; skipping removal")
            return

        force = status in (ClusterGlobalStatus.INVALIDATED, ClusterGlobalStatus.UNKNOWN)
        self._clients.cluster_set.remove_replica_cluster(cluster_name, force=force)
        logger.info(f"Replica cluster {cluster_name!r} removed (force={force})")

    def promote_cluster(self, cluster_name: str, force: bool = False) -> None:
        """Promote a replica cluster to primary and record the switchover.

        Incrementing the switchover counter triggers a relation-changed event
        on the consumer cluster so it can refresh its status.
        """
        self._clients.cluster_set.promote_replica_cluster(cluster_name, force=force)
        self._state_local.app.set_switchover_count(self._state_local.app.get_switchover_count() + 1)

    def rejoin_cluster(self, cluster_name: str) -> None:
        """Rejoin an invalidated replica cluster back into the cluster-set."""
        self._clients.cluster_set.rejoin_replica_cluster(cluster_name)

    def get_replica_cluster_state(self, cluster_name: str) -> ClusterGlobalStatus | None:
        """Return the global state of the named replica cluster."""
        return self._clients.cluster_set.fetch_cluster_state(cluster_name)
