# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import random
import time

from mysql_shell import ExecutionError

from ...state import OperatorState
from ...workload import BaseSystem
from ..clients import MySQLClusterClient, MySQLInstanceClient

logger = logging.getLogger(__name__)


class OperatorManager:
    """Class to deal with the operator operations."""

    cluster_max_size = 9

    def __init__(
        self,
        state: OperatorState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    @property
    def cluster_initialized(self) -> bool:
        """Return whether the MySQL cluster is initialized."""
        try:
            return len(self._cluster_client.fetch_instances()) > 0
        except ExecutionError as e:
            logger.warning(f"The MySQL cluster is not yet initialized: {e}")
            return False

    def check_instance_join_cluster(self, instance_label: str) -> None:
        """Check whether the MySQL instance can join the cluster."""
        if instance_label in self._cluster_client.fetch_instances():
            raise RuntimeError("The MySQL instance is already part of the cluster")
        if self.cluster_max_size == self._instance_client.count_cluster_members():
            raise RuntimeError("The MySQL cluster cannot contain more members")

    def join_instance_to_cluster(self, instance_label: str, instance_host: str) -> None:
        """Join the MySQL instance to the cluster.

        This function can only be executed from the cluster primary.
        Only the MySQL cluster instances can join other instances.
        """
        # Add random delay to mitigate collisions when multiple units are joining
        # due the difference between the time we test for locks and acquire them
        time.sleep(random.uniform(0, 1.5))

        try:
            if instance_label in self._cluster_client.fetch_instances():
                self._cluster_client.remove_instance(instance_label, instance_host)
                self._cluster_client.rescan()

            self._cluster_client.add_instance(instance_label, instance_host)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to join MySQL instance to cluster: {e}")

    def update_state(self) -> None:
        """Update the operator state."""
        try:
            role = self._instance_client.fetch_role()
            state = self._instance_client.fetch_state()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to update operator state: {e}")

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.set_instance_role(role)
        self._state.set_instance_state(state)
