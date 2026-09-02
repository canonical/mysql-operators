# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import random
import time
from contextlib import suppress

from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterRole

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients

logger = logging.getLogger(__name__)


class OperatorManager:
    """Class to deal with the operator operations."""

    cluster_max_size = 9

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    @property
    def is_cluster_set_primary(self) -> bool:
        """Return whether the MySQL cluster is the primary."""
        return self._clients.cluster.fetch_role() == ClusterRole.PRIMARY

    def get_instance_state(self) -> str | None:
        """Get the MySQL instance state."""
        return self._state.unit.get_instance_state()

    def create_system_password(self) -> str:
        """Create a MySQL instance system password."""
        return self._clients.instance.create_password()

    def check_instance_join_cluster(self, instance_label: str, cluster_name: str) -> bool:
        """Check whether the MySQL instance can join the cluster."""
        try:
            if self.cluster_max_size == self._clients.instance.count_cluster_members():
                logger.debug("The instance cannot join a full cluster")
                return False
            if instance_label in self._clients.cluster.fetch_instances():
                logger.debug("The instance is already part of the cluster")
                return False
            if cluster_name not in self._clients.cluster_set.fetch_clusters():
                logger.debug("The cluster has not been initialized")
                return False
        except ExecutionError as e:
            raise RuntimeError("Failed to check cluster joining") from e

        return True

    def fetch_cluster_status(self) -> dict[str, dict]:
        """Fetch the MySQL cluster status."""
        try:
            return self._clients.cluster.fetch_status()
        except ExecutionError as e:
            raise RuntimeError("Failed to fetch cluster status") from e

    def fetch_cluster_set_status(self) -> dict[str, dict]:
        """Fetch the MySQL cluster-set status."""
        try:
            return self._clients.cluster_set.fetch_status()
        except ExecutionError as e:
            raise RuntimeError("Failed to fetch cluster-set status") from e

    def join_instance(self, instance_label: str, instance_host: str, addresses: list[str]) -> None:
        """Join the MySQL instance to the cluster.

        This function can only be executed from the cluster primary.
        Only the MySQL cluster instances can join other instances.
        """
        # Add random delay to mitigate collisions when multiple units are joining
        # due the difference between the time we test for locks and acquire them
        time.sleep(random.uniform(0, 1.5))

        for address in addresses:
            with suppress(RuntimeError):
                with self._clients.build_cluster_set_client(address) as client:
                    primary_host = client.fetch_primary_host()
                    break

        if not primary_host:
            logger.error("Failed to find cluster-set primary")
            return

        with self._clients.build_cluster_client(primary_host) as client:
            if instance_label in client.fetch_instances():
                client.remove_instance(instance_label, instance_host)
                client.rescan()

            client.add_instance(instance_label, instance_host)

    def promote_instance(self, instance_host: str, force: bool) -> None:
        """Promote the MySQL instance."""
        self._clients.promote_instance(instance_host, force)

    def promote_cluster(self, cluster_name: str, force: bool) -> None:
        """Promote the MySQL cluster."""
        try:
            self._clients.cluster_set.promote_replica_cluster(cluster_name, force)
        except ExecutionError as e:
            raise RuntimeError("Failed to promote cluster") from e

    def recreate_cluster(self, instance_label: str, cluster_set_name: str) -> None:
        """Recreate the MySQL cluster."""
        self._state.app.set_cluster_set_name(cluster_set_name)
        self._state.app.delete_cluster_removed_flag()
        self._clients.recreate_cluster(instance_label)

    def update_cluster_user(self, username: str, password: str) -> None:
        """Update a MySQL instance user password."""
        try:
            primary_host = self._clients.cluster_set.fetch_primary_host()
        except ExecutionError as e:
            raise RuntimeError("Failed to fetch cluster-set primary") from e

        if not primary_host:
            logger.error("Failed to fetch cluster-set primary: no quorum")
            return

        with self._clients.build_instance_client(primary_host) as client:
            client.update_user(username, password)

    def update_state(self) -> None:
        """Update the operator state."""
        try:
            role = self._clients.instance.fetch_role()
            state = self._clients.instance.fetch_state()
        except ExecutionError as e:
            raise RuntimeError("Failed to update operator state") from e

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.unit.set_instance_role(role)
        self._state.unit.set_instance_state(state)
