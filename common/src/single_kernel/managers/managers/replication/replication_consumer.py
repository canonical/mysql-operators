# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import tenacity
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterRole, InstanceState

from ....state import PeerState, ReplicationState
from ....workload import BaseSystem
from ...clients import Clients
from .replication_status import ReplicationStatus

logger = logging.getLogger(__name__)


class ReplicationConsumerManager:
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

    def get_secret_id(self) -> str | None:
        """Get the secret ID."""
        return self._repl_state_remote.app.get_secret_id()

    def get_cluster_removed_flag(self) -> bool | None:
        """Get the cluster removed flag."""
        return self._peer_state.app.get_cluster_removed_flag()

    def set_cluster_removed_flag(self, flag: bool) -> None:
        """Set the cluster removed flag."""
        self._peer_state.app.set_cluster_removed_flag(flag)

    def check_cluster_version(self) -> None:
        """Check whether the MySQL cluster is compatible with the stored version."""
        remote_version = self._repl_state_remote.app.get_cluster_version()
        local_version = self._clients.instance.fetch_version()

        if remote_version != local_version:
            raise RuntimeError(
                f"\n\tPrimary MySQL cluster version {remote_version} is not compatible with the "
                f"\n\treplica MySQL cluster version {local_version}"
            )

    def is_primary_cluster(self) -> bool:
        """Return whether the MySQL cluster is the primary."""
        return self._clients.cluster.fetch_role() == ClusterRole.PRIMARY

    def is_returning_cluster(self) -> bool:
        """Return whether this cluster has joined the cluster-set previously."""
        remote_cluster_set = self._repl_state_remote.app.get_cluster_set_name()

        return all((
            self._peer_state.app.get_cluster_removed_flag(),
            self._peer_state.app.get_cluster_set_name() == remote_cluster_set,
        ))

    def is_initialized_cluster(self, target_members: int) -> bool:
        """Return whether this cluster is fully initialized."""
        online_members = self._clients.instance.count_cluster_members(states=[InstanceState.ONLINE])

        return online_members == target_members

    def build_status(self, target_members: int) -> ReplicationStatus:
        """Build the status out of the replication-consumer relation."""
        remote_secret = self._repl_state_remote.app.get_secret_id()
        if not remote_secret:
            return ReplicationStatus.UNINITIALIZED

        user_data = self._repl_state_local.app.get_user_data_flag()
        if user_data:
            return ReplicationStatus.FAILED

        local_address = self._repl_state_local.app.get_instance_address()
        if not local_address:
            return ReplicationStatus.SYNCING

        remote_replica = self._repl_state_remote.app.get_replica_flag()
        if not remote_replica:
            return ReplicationStatus.INITIALIZING

        if self.is_initialized_cluster(target_members):
            return ReplicationStatus.READY
        else:
            return ReplicationStatus.RECOVERING

    def check_instance_databases(self) -> bool:
        """Check whether the instance has databases."""
        num_databases = len(self._clients.instance.fetch_databases())
        has_databases = bool(num_databases)

        self._repl_state_local.app.set_user_data_flag(has_databases)
        return has_databases

    def create_cluster(self, instance_label: str) -> None:
        """Create a cluster."""
        self._clients.recreate_cluster(instance_label)
        self._peer_state.app.delete_cluster_removed_flag()
        self._peer_state.app.set_cluster_rejoin_flag(True)

    def dissolve_cluster(self, username: str, password: str) -> None:
        """Dissolve the cluster."""
        cluster_name = self._peer_state.app.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        with self._clients.build_cluster_set_client(
            instance_user=username,
            instance_pass=password,
        ) as client:
            client.dissolve_cluster(cluster_name, force=True)

        self._peer_state.app.delete_cluster_rejoin_flag()

    def save_cluster_info(self, instance_label: str, instance_host: str) -> None:
        """Save the cluster information into the databag."""
        logger.info("Setting the cluster information")

        cluster_name = self._peer_state.app.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        self._repl_state_local.app.set_cluster_name(cluster_name)
        self._repl_state_local.app.set_instance_label(instance_label)
        self._repl_state_local.app.set_instance_address(instance_host)

    def update_cluster_user(self, username: str, password: str) -> None:
        """Update a MySQL instance user password."""
        primary_host = self._clients.cluster_set.fetch_primary_host()
        if not primary_host:
            logger.error("Failed to fetch cluster-set primary: no quorum")
            return

        with self._clients.build_instance_client(primary_host) as client:
            client.update_user(username, password)

    def update_cluster_set_name(self) -> None:
        """Update the MySQL cluster-set name."""
        status = self._clients.cluster_set.fetch_status()
        domain = status.get("domainName", "")

        self._peer_state.app.set_cluster_set_name(domain)

    def update_state(self) -> None:
        """Update the operator state."""
        role = self._clients.instance.fetch_role()
        state = self._clients.instance.fetch_state()

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._peer_state.unit.set_instance_role(role)
        self._peer_state.unit.set_instance_state(state)

    def wait_cluster_dissolving(self) -> None:
        """Wait for the MySQL cluster to be dissolved."""
        logger.info("Waiting for cluster to be dissolved")

        cluster_name = self._peer_state.app.get_cluster_name()
        if not cluster_name:
            raise RuntimeError("Cluster name not found")

        try:
            for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_attempt(30),
                wait=tenacity.wait_fixed(10),
                reraise=True,
            ):
                with attempt:
                    if cluster_name in self._clients.instance.fetch_cluster_labels():
                        raise RuntimeError("Waiting for cluster to be dissolved")
        except ExecutionError as e:
            logger.warning(f"Cluster did not dissolve: {e}")
