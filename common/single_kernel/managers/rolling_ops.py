# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import tenacity
from mysql_shell.executors.errors import ExecutionError

from ..clients import MySQLClusterClient, MySQLInstanceClient
from ..state import RollingOperationState
from ..workload import BaseSystem

logger = logging.getLogger(__name__)


class RollingOperationManager:
    """Class to deal with the rolling operations."""

    def __init__(
        self,
        state: RollingOperationState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    def prepare_cluster(self, instance_label: str) -> None:
        """Prepare the MySQL cluster for a rolling operation."""
        try:
            self._cluster_client.promote_instance(instance_label)
        except ExecutionError as e:
            logger.error(f"Failed to prepare cluster: {e}")
            raise

    def recover_cluster(self) -> None:
        """Recover the MySQL cluster."""
        try:
            self._cluster_client.reboot()
        except ExecutionError as e:
            logger.error(f"Failed to recover cluster: {e}")
            raise

    def recover_instance(self, instance_label: str) -> None:
        """Recover the MySQL instance."""
        try:
            self._instance_client.wait_recovering()
        except ExecutionError as e:
            logger.error(f"Failed to recover instance: {e}")
            raise

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(30),
            wait=tenacity.wait_fixed(10),
            reraise=True,
        ):
            with attempt:
                _________ = self._instance_client.fetch_cluster_labels()
                instances = self._cluster_client.fetch_instances()
                if instance_label not in instances.keys():
                    raise RuntimeError("Instance did not join back the cluster")

    def restart_instance_replication(self, instance_label: str, instance_host: str) -> None:
        """Restart the MySQL instance replication.

        This function can only be executed from the cluster primary.
        Only the MySQL cluster instances can rejoin other instances, restarting their replication.
        """
        try:
            self._cluster_client.rejoin_instance(
                instance_label=instance_label,
                instance_host=instance_host,
            )
        except ExecutionError as e:
            logger.error(f"Failed to restart cluster replication: {e}")
            raise
