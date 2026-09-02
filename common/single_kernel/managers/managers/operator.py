# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import random
import time

from mysql_shell import ExecutionError

from ...state import OperatorState
from ...workload import BaseSystem
from ..clients import ManagerClients

logger = logging.getLogger(__name__)


class OperatorManager:
    """Class to deal with the operator operations."""

    cluster_max_size = 9

    def __init__(self, state: OperatorState, system: BaseSystem, clients: ManagerClients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    @property
    def cluster_initialized(self) -> bool:
        """Return whether the MySQL cluster is initialized."""
        try:
            return len(self._clients.cluster.fetch_instances()) > 0
        except ExecutionError as e:
            logger.warning(f"The MySQL cluster is not yet initialized: {e}")
            return False

    def get_instance_teardown(self) -> bool:
        """Get the instance teardown status."""
        return self._state.get_unit_status() == "removing"

    def set_instance_teardown(self) -> None:
        """Set the instance teardown status."""
        return self._state.set_unit_status("removing")

    def check_instance_join_cluster(self, instance_label: str) -> None:
        """Check whether the MySQL instance can join the cluster."""
        if instance_label in self._clients.cluster.fetch_instances():
            raise RuntimeError("The MySQL instance is already part of the cluster")
        if self.cluster_max_size == self._clients.instance.count_cluster_members():
            raise RuntimeError("The MySQL cluster cannot contain more members")

    def join_instance_to_cluster(self, instance_label: str, instance_host: str) -> None:
        """Join the MySQL instance to the cluster.

        This function can only be executed from the cluster primary.
        Only the MySQL cluster instances can join other instances.
        """
        # Add random delay to mitigate collisions when multiple units are joining
        # due the difference between the time we test for locks and acquire them
        time.sleep(random.uniform(0, 1.5))

        # TODO: Use any of the online members to fetch the cluster-set primary?
        try:
            primary_host = self._clients.cluster_set.fetch_primary_host()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch cluster-set primary: {e}")

        if not primary_host:
            logger.error(f"Failed to fetch cluster-set primary: no quorum")
            return

        with self._clients.build_cluster_client(primary_host) as client:
            if instance_label in client.fetch_instances():
                client.remove_instance(instance_label, instance_host)
                client.rescan()

            client.add_instance(instance_label, instance_host)

    def update_state(self) -> None:
        """Update the operator state."""
        try:
            role = self._clients.instance.fetch_role()
            state = self._clients.instance.fetch_state()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to update operator state: {e}")

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.set_instance_role(role)
        self._state.set_instance_state(state)
