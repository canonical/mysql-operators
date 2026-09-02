# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import cached_property

import tenacity
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterRole, InstanceState

from .base import BaseReplicationManager
from .replication_status import ReplicationStatus

logger = logging.getLogger(__name__)


class ConsumingReplicationManager(BaseReplicationManager):
    """Class to deal with the MySQL server replication consuming."""

    @cached_property
    def cluster_role(self) -> ClusterRole:
        """Return the MySQL cluster role."""
        return self._cluster_client.fetch_role()

    def get_status(self, target_members: int) -> ReplicationStatus:
        """Return the status of the replication relation."""
        remote_secret = self._state_remote.get_secret_id()
        local_endpoint = self._state_local.get_endpoint()

        # Credentials exists in the primary cluster but not yet synchronized
        if remote_secret and not local_endpoint:
            return ReplicationStatus.SYNCING

        # Cluster not yet initialized
        if not self._state_local.get_replica_flag():
            return ReplicationStatus.INITIALIZING

        online_members = self._instance_client.count_cluster_members(states=[InstanceState.ONLINE])
        if online_members == target_members:
            return ReplicationStatus.READY
        else:
            return ReplicationStatus.RECOVERING

    def check_instance_data(self) -> None:
        """Check whether the MySQL instance has user data."""
        try:
            databases = self._instance_client.fetch_databases()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch instance databases: {e}")

        if databases:
            raise RuntimeError(
                "\n\tUser data found, aborting async replication setup."
                "\n\tEnsure the cluster has no user data before trying to join a cluster set."
                "\n\tAfter removing/backing up the data, remove the relation and add it again."
            )

    def check_cluster_version(self) -> None:
        """Check whether the MySQL cluster is compatible with the stored version."""
        try:
            remote_version = self._state_remote.get_version()
            local_version = self._instance_client.fetch_version()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to check cluster version: {e}")

        if remote_version != local_version:
            raise RuntimeError(
                f"\n\tPrimary MySQL cluster version {remote_version} is not compatible with the "
                f"\n\treplica MySQL cluster version {local_version}"
            )

    def dissolve_cluster(self) -> None:
        """Dissolve the MySQL cluster."""
        logger.info("Dissolving cluster")

        cluster_name = self._state_local.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        try:
            self._cluster_set_client.dissolve_cluster(cluster_name, force=True)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to dissolve cluster: {e}")

    def update_cluster_credentials(self, usernames: dict[str, str]) -> None:
        """Update the MySQL cluster credentials."""
        logger.info("Updating cluster credentials")

        secret_id = self._state_remote.get_secret_id()
        if not secret_id:
            raise RuntimeError("Secret ID not found")

        for key, password in self._state_remote.store.get_secret_content(secret_id).items():
            self._instance_client.update_user(usernames[key], password)

    def wait_cluster_dissolving(self) -> None:
        """Wait for the MySQL cluster to be dissolved."""
        logger.info("Waiting for cluster to be dissolved")

        cluster_name = self._state_local.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        try:
            for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_attempt(30),
                wait=tenacity.wait_fixed(10),
                reraise=True,
            ):
                with attempt:
                    if all((
                        cluster_name in self._instance_client.fetch_cluster_labels(),
                        cluster_name in self._cluster_set_client.fetch_clusters(),
                    )):
                        logger.debug("Waiting for cluster to be dissolved")
        except ExecutionError as e:
            logger.warning(f"Cluster did not dissolve: {e}")
