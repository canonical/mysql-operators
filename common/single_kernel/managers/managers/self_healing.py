# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Mapping, Sequence

from mysql_shell import InstanceState
from mysql_shell.executors.errors import ExecutionError

from ...state import SelfHealingState
from ...workload import BaseSystem
from ..clients import MySQLClusterClient, MySQLInstanceClient

logger = logging.getLogger(__name__)


class SelfHealingManager:
    """Class to deal with the self-healing operations."""

    def __init__(
        self,
        state: SelfHealingState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    def fetch_cluster_state(self) -> str:
        """Fetch the cluster state."""
        try:
            return self._cluster_client.fetch_state()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch cluster state: {e}")

    def fetch_instance_state(self) -> str:
        """Fetch the instance state."""
        try:
            return self._instance_client.fetch_state()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch instance state: {e}")

    def recover_cluster_quorum(self) -> None:
        """Recover cluster quorum."""
        # Group replication quorum recovery must not run when a peer is UNREACHABLE.
        # That scenario indicates a network partition where the remote side may be healthy.
        if self._instance_client.count_cluster_members(states=[InstanceState.UNREACHABLE]) > 0:
            logger.warning("Skipping quorum recovery")
            return

        logger.debug("Recovering cluster quorum")

        try:
            # Group replication needs to be stopped beforehand.
            # MySQL reboot functionality reject instances that are not OFFLINE
            self._instance_client.stop_replication()
            self._cluster_client.reboot()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to recover cluster quorum: {e}")

    def update_labels(self, addresses: Sequence[str], labels: Mapping[str, str]) -> None:
        """Update address related labels."""
        logger.debug("Updating address labels")

        for address in addresses:
            try:
                self._system.runtime.update_labels(address, labels)
            except RuntimeError as e:
                logger.exception(f"Failed to update endpoint labels: {e}")
                raise
