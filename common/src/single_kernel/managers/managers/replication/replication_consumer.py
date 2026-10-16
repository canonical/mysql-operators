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


class ReplicationConsumingManager(BaseReplicationManager):
    """Class to deal with the MySQL server replication consuming."""

    @cached_property
    def cluster_role(self) -> ClusterRole | None:
        """Return the MySQL cluster role within the cluster-set."""
        return self._clients.cluster.fetch_role()

    @property
    def returning_cluster(self) -> bool:
        """Return whether this cluster is rejoining a cluster-set it previously left.

        Both conditions must hold: the local removed-from-cluster-set flag is set
        AND the remote cluster-set name matches the one stored in the peer state,
        confirming this is the same cluster-set the unit belonged to before.
        """
        if not self._peer_state.app.get_cluster_removed_flag():
            return False

        remote_cluster_set_name = self._state_remote.app.get_cluster_set_name()
        local_cluster_set_name = self._peer_state.app.get_cluster_set_name()
        return remote_cluster_set_name == local_cluster_set_name

    def get_status(self, target_members: int = 0) -> ReplicationStatus:
        """Return the current replication status from the consumer side.

        Args:
            target_members: Total expected ONLINE members in the local cluster.
                When the replica flag is set, the status is READY only when
                all expected members are online; otherwise RECOVERING.
        """
        remote_secret = self._state_remote.app.get_secret_id()
        if not remote_secret:
            return ReplicationStatus.UNINITIALIZED

        local_address = self._state_local.app.get_instance_address()
        if not local_address:
            return ReplicationStatus.SYNCING

        if not self._state_remote.app.get_replica_flag():
            return ReplicationStatus.INITIALIZING

        online_members = self._clients.instance.count_cluster_members(states=[InstanceState.ONLINE])
        if online_members == target_members:
            return ReplicationStatus.READY
        return ReplicationStatus.RECOVERING

    def get_remote_secret_id(self) -> str | None:
        """Return the replication secret ID written by the primary cluster."""
        return self._state_remote.app.get_secret_id()

    def get_replica_initialized(self) -> bool:
        """Return whether the primary cluster has marked this replica as initialized."""
        return self._state_remote.app.get_replica_flag() or False

    def check_cluster_version(self) -> None:
        """Verify that the local MySQL version matches the primary cluster's version.

        Raises:
            RuntimeError: when the versions differ.
        """
        remote_version = self._state_remote.app.get_cluster_version()
        local_version = self._clients.instance.fetch_version()

        if remote_version != local_version:
            raise RuntimeError(
                f"MySQL version mismatch: primary={remote_version!r}, "
                f"local={local_version!r}. Remove the relation to abort."
            )

    def count_online_members(self) -> int:
        """Return the number of ONLINE members currently in the local cluster."""
        return self._clients.instance.count_cluster_members(states=[InstanceState.ONLINE])

    def dissolve_cluster(self) -> None:
        """Dissolve the local cluster before joining the cluster-set.

        Reads the cluster name from peer state, which is always populated
        regardless of whether the consumer relation databag has been written yet.

        Raises:
            RuntimeError: when the cluster name is not available.
        """
        cluster_name = self._peer_state.app.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cannot dissolve cluster: cluster name not found in peer state")

        logger.info(f"Dissolving cluster {cluster_name!r}")
        self._clients.cluster_set.dissolve_cluster(cluster_name, force=True)

    def wait_cluster_dissolving(self) -> None:
        """Poll until the primary cluster removes this cluster from the cluster-set.

        Reads the cluster name from peer state for consistency with dissolve_cluster.

        Raises:
            RuntimeError: when the cluster name is missing or the wait times out.
        """
        cluster_name = self._peer_state.app.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cannot wait for dissolution: cluster name not found in peer state")

        logger.info(f"Waiting for cluster {cluster_name!r} to be dissolved by primary")
        try:
            for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_attempt(30),
                wait=tenacity.wait_fixed(10),
                reraise=True,
            ):
                with attempt:
                    if all((
                        cluster_name in self._clients.instance.fetch_cluster_labels(),
                        cluster_name in self._clients.cluster_set.fetch_clusters(),
                    )):
                        logger.debug(f"Cluster {cluster_name!r} still being dissolved, retrying")
                        raise RuntimeError("cluster not yet dissolved")
        except ExecutionError as e:
            raise RuntimeError(f"Cluster {cluster_name!r} dissolution check failed: {e}") from e

    def recreate_standalone_cluster(self, instance_label: str) -> None:
        """Recreate the local cluster as a standalone cluster.

        Used when a returning cluster needs to re-establish a local single-node
        cluster before credential sync and rejoining the cluster-set.
        Clears the removed-from-cluster-set flag and sets the rejoin flag so
        secondary units know to rejoin after the primary comes back.
        """
        self._clients.recreate_cluster(instance_label)
        self._peer_state.app.delete_cluster_removed_flag()
        self._peer_state.app.set_cluster_rejoin_flag(True)

    def rename_cluster_if_conflicting(self) -> None:
        """Rename the local cluster when its name collides with the primary cluster.

        MySQL InnoDB ClusterSet requires unique cluster names. When the names
        match, a suffix derived from the cluster-set name is appended, truncated
        to MySQL's 63-character limit.
        """
        remote_name = self._state_remote.app.get_cluster_name()
        local_name = self._peer_state.app.get_cluster_name() or ""

        if remote_name and remote_name == local_name:
            suffix = self._peer_state.app.get_cluster_set_name() or ""
            new_name = f"{local_name}{suffix}x"[:63]
            logger.warning(
                f"Cluster name {local_name!r} conflicts with primary cluster. "
                f"Renaming to {new_name!r}"
            )
            self._peer_state.app.set_cluster_name(new_name)

    def sync_cluster_set_domain_name(self) -> None:
        """Pull the cluster-set domain name from the server and persist it to peer state."""
        status = self._clients.cluster_set.fetch_status()
        domain_name = status.get("domainName")
        if domain_name:
            self._peer_state.app.set_cluster_set_name(domain_name)
        else:
            logger.warning("Could not fetch cluster-set domain name from server status")

    def sync_user_password(self, username: str, password: str) -> None:
        """Update a system user's password on the local instance."""
        self._clients.instance.update_user(username, password)

    def refresh_operator_password(self, password: str) -> None:
        """Refresh the executor connection details after the operator password is synced.

        Must be called after sync_user_password for the operator user so that
        subsequent MySQL operations within the same hook (e.g. dissolve_cluster)
        use the updated credentials.
        """
        self._clients.refresh_password(password)

    def set_consumer_identity(
        self,
        cluster_name: str,
        instance_address: str,
        instance_label: str,
    ) -> None:
        """Write the consumer identity fields to the local databag.

        These values are read by the primary cluster to create the replica cluster
        entry in the cluster-set.
        """
        self._state_local.app.set_cluster_name(cluster_name)
        self._state_local.app.set_instance_address(instance_address)
        self._state_local.app.set_instance_label(instance_label)

    def is_instance_in_cluster(self, instance_label: str) -> bool:
        """Return whether the labelled instance is currently a member of the local cluster."""
        return instance_label in self._clients.cluster.fetch_instances()
