# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from mysql_shell.models import InstanceState

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

    def fetch_cluster_state(self) -> str:
        """Fetch the cluster state."""
        return self._clients.cluster.fetch_state()

    def fetch_instance_state(self) -> str:
        """Fetch the instance state."""
        return self._clients.instance.fetch_state()

    def recover_cluster_quorum(self) -> None:
        """Recover the cluster quorum."""
        # Group replication quorum recovery must not run when a peer is UNREACHABLE.
        # That scenario indicates a network partition where the remote side may be healthy.
        if self._clients.instance.count_cluster_members(states=[InstanceState.UNREACHABLE]) > 0:
            logger.warning("Skipping quorum recovery")
            return

        logger.debug("Recovering cluster quorum")

        # Group replication needs to be stopped beforehand.
        # MySQL reboot functionality reject instances that are not OFFLINE
        self._clients.instance.stop_replication()
        self._clients.cluster.reboot()

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate the cluster."""
        self._clients.cluster.drop_metadata()
        self._clients.recreate_cluster(instance_label)

    def update_state(self) -> None:
        """Update the operator state."""
        role = self._clients.instance.fetch_role()
        state = self._clients.instance.fetch_state()

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.unit.set_instance_role(role)
        self._state.unit.set_instance_state(state)
