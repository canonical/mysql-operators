# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from mysql_shell.clients import ClusterClient
from mysql_shell.executors import BaseExecutor
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterGlobalStatus as ClusterGlobalState
from mysql_shell.models import ClusterRole

logger = logging.getLogger(__name__)


class MySQLClusterSetClient:
    """Class to deal with the MySQL cluster-set."""

    def __init__(self, executor: BaseExecutor):
        """Initialize the class attributes."""
        self._executor = executor
        self._client = ClusterClient(executor)

    def create_replica_cluster(
        self,
        instance_label: str,
        instance_host: str,
        cluster_name: str,
        donor: str | None = None,
        method: str | None = None,
    ):
        """Create a MySQL cluster-set replica cluster out of the provided instance."""
        options = {
            "communicationStack": "MySQL",
            "recoveryProgress": 0,
            "timeout": 0,
        }
        if donor:
            options["cloneDonor"] = donor
        if method:
            options["recoveryMethod"] = method

        try:
            self._client.create_cluster_set_replica(
                cluster_name=cluster_name,
                source_host=instance_host,
                source_port=str(3306),
                options=options,
            )
            self._client.update_instance_within_cluster(
                cluster_name=cluster_name,
                instance_host=instance_host,
                instance_port=str(3306),
                options={"label": instance_label},
            )
        except ExecutionError as e:
            logger.warning(f"Failed to create replica cluster: {e}")
            if method == "clone":
                raise

            logger.warning(f"Defaulting to `clone` recovery method")
            self.create_replica_cluster(
                instance_label=instance_label,
                instance_host=instance_host,
                cluster_name=cluster_name,
                donor=donor,
                method="clone",
            )

    def fetch_primary_host(self) -> str | None:
        """Fetch the MySQL cluster-set primary host."""
        status = self._client.fetch_cluster_set_status(extended=False)

        cluster = status["primaryCluster"]
        cluster_state = status["clusters"][cluster]["globalStatus"]
        cluster_address = status["clusters"][cluster]["primary"]

        if cluster_state == ClusterGlobalState.INVALIDATED:
            logger.error(f"Failed to fetch cluster-set primary: no quorum")
            return None

        return cluster_address.split(":")[0]

    def fetch_clusters(self) -> dict[str, dict]:
        """Fetch the MySQL cluster-set clusters."""
        status = self._client.fetch_cluster_set_status(extended=False)
        clusters = status["clusters"]

        return clusters

    def fetch_cluster_state(self, cluster_name: str) -> ClusterGlobalState | None:
        """Fetch a MySQL cluster-set cluster global state."""
        status = self._client.fetch_cluster_set_status(extended=False)

        cluster = status["clusters"].get(cluster_name)
        if not cluster:
            return

        state = cluster["globalStatus"]
        state = ClusterGlobalState(state)
        return state

    def fetch_status(self) -> dict[str, dict]:
        """Fetch a MySQL cluster-set cluster status."""
        return self._client.fetch_cluster_set_status(extended=False)

    def dissolve_cluster(self, cluster_name: str, force: bool = False) -> None:
        """Dissolve a MySQL cluster-set cluster."""
        status = self._client.fetch_cluster_set_status(extended=False)
        clusters = status["clusters"].keys()

        cluster = status["clusters"].get(cluster_name)
        if not cluster:
            return

        role = cluster["clusterRole"]
        role = ClusterRole(role)

        if len(clusters) > 1 and not role == ClusterRole.REPLICA:
            another_cluster = (clusters - {cluster_name}).pop()
            self._client.promote_cluster_set_replica(another_cluster)
            self._client.remove_cluster_set_replica(cluster_name)

        if force:
            self._client.destroy_cluster(cluster_name, {"force": force})

    def promote_replica_cluster(self, cluster_name: str, force: bool = False) -> None:
        """Promote a MySQL cluster-set replica cluster."""
        self._client.promote_cluster_set_replica(
            cluster_name=cluster_name,
            force=force,
        )

    def remove_replica_cluster(self, cluster_name: str, force: bool = False) -> None:
        """Remove a MySQL cluster-set replica cluster."""
        self._client.remove_cluster_set_replica(
            cluster_name=cluster_name,
            options={"force": force},
        )

    def rejoin_replica_cluster(self, cluster_name: str) -> None:
        """Rejoin a MySQL cluster-set replica cluster."""
        self._client.rejoin_cluster_set_cluster(cluster_name)
