# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import cached_property

from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterGlobalStatus, ClusterRole

from .base import BaseReplicationManager
from .replication_status import ReplicationStatus

logger = logging.getLogger(__name__)


class OfferingReplicationManager(BaseReplicationManager):
    """Class to deal with the MySQL server replication offering."""

    @cached_property
    def cluster_role(self) -> ClusterRole:
        """Return the MySQL cluster role."""
        return self._clients.cluster.fetch_role()

    def get_status(self, target_members: int) -> ReplicationStatus:
        """Return the status of the replication relation."""
        if not self._state_local.app._data:
            return ReplicationStatus.UNINITIALIZED

        if self.cluster_role == ClusterRole.REPLICA:
            return ReplicationStatus.FAILED

        local_secret = self._state_local.app.get_secret_id()
        remote_address = self._state_remote.app.get_instance_address()
        remote_cluster = self._state_remote.app.get_cluster_name()

        # Credentials exists in the primary cluster but not yet synchronized
        if local_secret and not remote_address:
            return ReplicationStatus.SYNCING

        if local_secret and remote_address:
            match self._clients.cluster_set.fetch_cluster_state(remote_cluster):
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

    def create_cluster_replica(self, donor: str | None) -> None:
        """Create a MySQL cluster replica."""
        logger.info("Creating replica cluster")

        cluster_name = self._state_remote.app.get_cluster_name()
        instance_addr = self._state_remote.app.get_instance_address()
        instance_label = self._state_remote.app.get_instance_label()

        if not cluster_name:
            logger.warning("Skipping cluster creation: no cluster name found")
            return
        if not instance_label:
            logger.warning("Skipping cluster creation: no instance name found")
            return

        try:
            self._clients.cluster_set.create_replica_cluster(
                instance_label=instance_label,
                instance_host=instance_addr.split(":")[0],
                cluster_name=cluster_name,
                donor=donor,
            )
        except ExecutionError as e:
            raise RuntimeError("Failed to create replica cluster") from e

        self._state_local.app.set_replica_flag(True)

    def remove_cluster_replica(self) -> None:
        """Remove a MySQL cluster replica."""
        cluster_name = self._state_remote.app.get_cluster_name()
        if not cluster_name:
            logger.warning("Skipping cluster removal: no cluster name found")
            return

        logger.info(f"Removing cluster {cluster_name}")

        status = self._clients.cluster_set.fetch_cluster_state(cluster_name)
        if not status:
            return

        match status:
            case ClusterGlobalStatus.INVALIDATED:
                force = True
            case ClusterGlobalStatus.UNKNOWN:
                force = True
            case _:
                force = False

        try:
            self._clients.cluster_set.remove_replica_cluster(cluster_name, force=force)
        except ExecutionError as e:
            raise RuntimeError("Failed to remove cluster") from e

    def set_cluster_info(self, cluster_name: str, replication_name: str) -> None:
        """Set the MySQL cluster information into the databag."""
        logger.info("Setting the cluster information")

        try:
            cluster_version = self._clients.instance.fetch_version()
        except ExecutionError as e:
            raise RuntimeError("Failed to fetch instance version") from e

        self._state_local.app.set_cluster_name(cluster_name)
        self._state_local.app.set_cluster_version(cluster_version)
        self._state_local.app.set_replication_name(replication_name)
