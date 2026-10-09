# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import random
import time

from mysql_shell.models import ClusterStatus, InstanceState

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients

logger = logging.getLogger(__name__)


class SelfHealingManager:
    """Class to deal with the self-healing operations."""

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def fetch_cluster_members(self) -> int:
        """Fetch the cluster members."""
        return self._clients.instance.count_cluster_members(states=[InstanceState.ONLINE])

    def fetch_cluster_state(self) -> str:
        """Fetch the cluster state."""
        state = self._clients.cluster.fetch_state()
        if not state:
            state = ClusterStatus.UNREACHABLE

        return state

    def fetch_instance_state(self) -> str:
        """Fetch the instance state."""
        state = self._clients.instance.fetch_state()
        if not state:
            state = InstanceState.UNREACHABLE

        return state

    def rejoin_instance(self, instance_label: str, instance_host: str, addrs: list[str]) -> None:
        """Rejoin the instance back into the cluster.

        This function can only be executed from the cluster primary.
        Only the MySQL cluster primary can rejoin other instances.
        """
        primary_host = self._clients.find_cluster_primary(addrs)
        if not primary_host:
            logger.error("Failed to find cluster primary")
            return

        # Add random delay to mitigate collisions when multiple units are joining
        # due the difference between the time we test for locks and acquire them
        time.sleep(random.uniform(0, 1.5))

        with self._clients.build_cluster_client(primary_host) as client:
            client.rejoin_instance(instance_label, instance_host)
            logger.info(f"Succeeded to rejoin instance {instance_label}")

    def recover_cluster_quorum(self) -> None:
        """Recover the cluster quorum."""
        # Group replication quorum recovery must not run when a peer is UNREACHABLE.
        # That scenario indicates a network partition where the remote side may be healthy.
        if self._clients.instance.count_cluster_members(states=[InstanceState.UNREACHABLE]) > 0:
            logger.warning("Skipping quorum recovery: there are unreachable instances")
            return

        logger.info("Recovering cluster quorum")
        self._clients.cluster.reboot()

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate the cluster."""
        self._clients.cluster.drop_metadata()
        self._clients.recreate_cluster(instance_label)

    def stop_replication(self) -> None:
        """Stop the instance replication."""
        self._clients.instance.stop_replication()

    def update_state(self) -> None:
        """Update the operator state."""
        role = self._clients.instance.fetch_role()
        state = self._clients.instance.fetch_state()

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.unit.set_instance_role(role)
        self._state.unit.set_instance_state(state)
