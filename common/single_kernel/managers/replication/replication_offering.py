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
        return self._cluster_client.fetch_role()

    def get_status(self, target_members: int) -> ReplicationStatus:
        """Return the status of the replication relation."""
        if not self._state_local._relation_data:
            return ReplicationStatus.UNINITIALIZED

        if self.cluster_role == ClusterRole.REPLICA:
            return ReplicationStatus.FAILED

        local_secret = self._state_local.get_secret_id()
        remote_endpoint = self._state_remote.get_endpoint()
        remote_cluster = self._state_remote.get_cluster_name()

        # Credentials exists in the primary cluster but not yet synchronized
        if local_secret and not remote_endpoint:
            return ReplicationStatus.SYNCING

        if local_secret and remote_endpoint:
            match self._cluster_set_client.fetch_cluster_state(remote_cluster):
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

        endpoint = self._state_remote.get_endpoint()
        cluster_name = self._state_remote.get_cluster_name()
        instance_label = self._state_remote.get_instance_label()

        if not cluster_name:
            logger.warning("Skipping cluster creation: no cluster name found")
            return
        if not instance_label:
            logger.warning("Skipping cluster creation: no instance name found")
            return

        try:
            self._cluster_set_client.create_replica_cluster(
                instance_label=instance_label,
                instance_host=endpoint.split(":")[0],
                cluster_name=cluster_name,
                donor=donor,
            )
        except ExecutionError as e:
            raise RuntimeError(f"Failed to create replica cluster: {e}")

        self._state_local.set_replica_flag(True)

    def remove_cluster_replica(self) -> None:
        """Remove a MySQL cluster replica."""
        cluster_name = self._state_remote.get_cluster_name()
        if not cluster_name:
            logger.warning("Skipping cluster removal: no cluster name found")
            return

        logger.info(f"Removing cluster {cluster_name}")

        status = self._cluster_set_client.fetch_cluster_state(cluster_name)
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
            self._cluster_set_client.remove_replica_cluster(cluster_name, force=force)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to remove cluster: {e}")

    def set_cluster_info(self, cluster_name: str, replication_name: str) -> None:
        """Set the MySQL cluster information into the databag."""
        logger.info("Setting the cluster information")

        try:
            version = self._instance_client.fetch_version()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch instance version: {e}")

        self._state_local.set_cluster_name(cluster_name)
        self._state_local.set_replication_name(replication_name)
        self._state_local.set_version(version)

    def set_instance_passwords(self, passwords: dict[str, str]) -> None:
        """Set the MySQL instance passwords into a secret."""
        logger.info("Setting the instance passwords into a secret")

        secret_id = self._state_local.store.create_secret(passwords)
        _________ = self._state_local.set_secret_id(secret_id)

    def remove_instance_passwords(self) -> None:
        """Remove the MySQL instance passwords from a secret."""
        secret_id = self._state_local.get_secret_id()
        if not secret_id:
            return

        logger.info("Removing the instance passwords from a secret")
        self._state_local.store.delete_secret(secret_id)
