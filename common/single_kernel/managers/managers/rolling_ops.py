# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import cached_property

import tenacity
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceRole

from ...state import RollingOperationState
from ...workload import BaseSystem
from ..clients import ManagerClients

logger = logging.getLogger(__name__)


class RollingOperationManager:
    """Class to deal with the rolling operations."""

    def __init__(self, state: RollingOperationState, system: BaseSystem, clients: ManagerClients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    @cached_property
    def is_cluster_primary(self) -> bool:
        """Return whether the MySQL instance is the primary."""
        return self._clients.instance.fetch_role() == InstanceRole.PRIMARY

    def prepare_cluster(self, instance_label: str) -> None:
        """Prepare the MySQL cluster for a rolling operation."""
        try:
            self._clients.cluster.promote_instance(instance_label)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to prepare cluster: {e}")

    def recover_cluster(self) -> None:
        """Recover the MySQL cluster."""
        try:
            self._clients.cluster.reboot()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to recover cluster: {e}")

    def recover_instance(self, instance_label: str) -> None:
        """Recover the MySQL instance."""
        try:
            self._clients.instance.wait_recovering()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to recover instance: {e}")

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(30),
            wait=tenacity.wait_fixed(10),
            reraise=True,
        ):
            with attempt:
                _________ = self._clients.instance.fetch_cluster_labels()
                instances = self._clients.cluster.fetch_instances()
                if instance_label not in instances.keys():
                    raise RuntimeError("Instance did not join back the cluster")

    def restart_instance_replication(self, instance_label: str, instance_host: str) -> None:
        """Restart the MySQL instance replication."""
        try:
            primary_host = self._clients.cluster_set.fetch_primary_host()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to fetch cluster-set primary: {e}")

        if not primary_host:
            logger.error(f"Failed to fetch cluster-set primary: no quorum")
            return

        with self._clients.build_cluster_client(primary_host) as client:
            client.rejoin_instance(
                instance_label=instance_label,
                instance_host=instance_host,
            )
