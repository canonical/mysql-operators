# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from charm_refresh import PrecheckFailed
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceState

from ..clients import MySQLClusterClient, MySQLInstanceClient
from ..state import RefreshState
from ..workload import BaseSystem

logger = logging.getLogger(__name__)


class RefreshManager:
    """Class to deal with the operator refresh."""

    def __init__(
        self,
        state: RefreshState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    def check_cluster(self) -> None:
        """Check the MySQL cluster health."""
        try:
            _________ = self._cluster_client.rescan()
            instances = self._cluster_client.fetch_instances()
        except ExecutionError as e:
            raise PrecheckFailed(f"Failed to check cluster health: {e}")

        for instance in instances.values():
            if instance["status"] != InstanceState.ONLINE:
                raise PrecheckFailed("Cluster instances are not online")

    def prepare_cluster(self, instance_label: str) -> None:
        """Prepare the MySQL cluster for an operator refresh."""
        try:
            self._cluster_client.promote_instance(instance_label)
        except ExecutionError as e:
            raise PrecheckFailed(f"Failed to prepare cluster: {e}")

    def prepare_instance(self) -> None:
        """Prepare the MySQL instance for an operator refresh."""
        try:
            self._instance_client.update_variable("innodb_fast_shutdown", 0)
        except ExecutionError as e:
            raise PrecheckFailed(f"Failed to prepare instance: {e}")
