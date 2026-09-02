# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Mapping, Sequence

from mysql_shell import InstanceState
from mysql_shell.executors.errors import ExecutionError

from ...state import SelfHealingState
from ...workload import BaseSystem
from ..clients import ManagerClients

logger = logging.getLogger(__name__)


class SelfHealingManager:
    """Class to deal with the self-healing operations."""

    def __init__(self, state: SelfHealingState, system: BaseSystem, clients: ManagerClients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def fetch_cluster_state(self) -> str:
        """Fetch the cluster state."""
        try:
            return self._clients.cluster.fetch_state()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch cluster state: {e}")

    def fetch_instance_state(self) -> str:
        """Fetch the instance state."""
        try:
            return self._clients.instance.fetch_state()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch instance state: {e}")

    def recover_cluster_quorum(self) -> None:
        """Recover cluster quorum."""
        # Group replication quorum recovery must not run when a peer is UNREACHABLE.
        # That scenario indicates a network partition where the remote side may be healthy.
        if self._clients.instance.count_cluster_members(states=[InstanceState.UNREACHABLE]) > 0:
            logger.warning("Skipping quorum recovery")
            return

        logger.debug("Recovering cluster quorum")

        try:
            # Group replication needs to be stopped beforehand.
            # MySQL reboot functionality reject instances that are not OFFLINE
            self._clients.instance.stop_replication()
            self._clients.cluster.reboot()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to recover cluster quorum: {e}")

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate cluster."""
        try:
            self._clients.instance.drop_replication_schema()
            self._clients.cluster.init_locks_table()
            self._clients.cluster.create(instance_label)
            self._clients.cluster_set.create(self._clients.cluster._cluster)

            # Rescan cluster for cleanup of unused recovery users
            self._clients.cluster.rescan()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to recreate cluster: {e}")

    def update_labels(self, addresses: Sequence[str], labels: Mapping[str, str]) -> None:
        """Update address related labels."""
        logger.debug("Updating address labels")

        for address in addresses:
            try:
                self._system.runtime.update_labels(address, labels)
            except RuntimeError as e:
                logger.exception(f"Failed to update endpoint labels: {e}")
                raise
