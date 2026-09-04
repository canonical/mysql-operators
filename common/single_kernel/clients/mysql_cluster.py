# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Any

from mysql_shell.builders import BaseLockingQueryBuilder
from mysql_shell.clients import ClusterClient
from mysql_shell.executors import BaseExecutor
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterRole
from mysql_shell.models import ClusterStatus as ClusterState

logger = logging.getLogger(__name__)


class MySQLClusterClient:
    """Class to deal with the MySQL cluster."""

    def __init__(self, executor: BaseExecutor, lock_builder: BaseLockingQueryBuilder, cluster: str):
        """Initialize the class attributes."""
        self._executor = executor
        self._cluster = cluster
        self._client = ClusterClient(executor)
        self._lock_builder = lock_builder

    @property
    def _host(self) -> str:
        """Return the executor host."""
        return self._executor.connection_details.host

    @property
    def _port(self) -> str:
        """Return the executor port."""
        return self._executor.connection_details.port

    def _acquire_lock(self, instance_label: str, instance_task: str) -> None:
        """Acquires a lock within the instance operations table."""
        acquire_query = self._lock_builder.build_acquire_query(instance_task, instance_label)
        fetch_query = self._lock_builder.build_fetch_acquired_query(instance_task)

        try:
            logger.debug(f"Acquiring lock {instance_task} for instance {instance_label}")
            ____ = self._executor.execute_sql(acquire_query)
            rows = self._executor.execute_sql(fetch_query)
        except ExecutionError:
            logger.error(f"Failed to acquire lock {instance_task}")
            raise

        executor_labels = [row["executor"] for row in rows]
        if instance_label not in executor_labels:
            raise ExecutionError(f"Failed to acquire lock {instance_task}")

    def _release_lock(self, instance_label: str, instance_task: str) -> None:
        """Releases a lock within the instance operations table."""
        release_query = self._lock_builder.build_release_query(instance_task, instance_label)

        try:
            logger.debug(f"Releasing lock {instance_task} for unit {instance_label}")
            self._executor.execute_sql(release_query)
        except ExecutionError:
            logger.error(f"Failed to release lock {instance_task}")
            raise

    def fetch_instances(self) -> dict[str, dict]:
        """Fetch the MySQL cluster members."""
        status = self._client.fetch_cluster_status(self._cluster)
        topology = status["defaultReplicaSet"]["topology"]

        return topology

    def fetch_primary_host(self) -> str | None:
        """Fetch the MySQL cluster primary host."""
        status = self._client.fetch_cluster_status(self._cluster)

        cluster_state = status["defaultReplicaSet"]["status"]
        cluster_address = status["defaultReplicaSet"]["primary"]

        if cluster_state == ClusterState.NO_QUORUM:
            logger.error(f"Failed to fetch cluster primary: no quorum")
            return None

        return cluster_address.split(":")[0]

    def fetch_role(self) -> ClusterRole:
        """Fetch the MySQL cluster role."""
        status = self._client.fetch_cluster_status(self._cluster)

        role = status["clusterRole"]
        role = ClusterRole(role)
        return role

    def fetch_state(self) -> ClusterState:
        """Fetch the MySQL cluster state."""
        status = self._client.fetch_cluster_status(self._cluster)

        state = status["defaultReplicaSet"]["status"]
        state = ClusterState(state)
        return state

    def fetch_status(self) -> dict[str, dict]:
        """Fetch the MySQL cluster status."""
        return self._client.fetch_cluster_status(self._cluster)

    def promote_instance(self, instance_host: str) -> None:
        """Promote an instance into the MySQL cluster primary."""
        self._client.promote_instance_within_cluster(
            cluster_name=self._cluster,
            instance_host=instance_host,
            instance_port=str(3306),
        )

    def rejoin_instance(self, instance_label: str, instance_host: str) -> None:
        """Rejoin an instance back into the MySQL cluster."""
        self._acquire_lock(
            instance_label=instance_label,
            instance_task=self._lock_builder.INSTANCE_ADDITION_TASK,
        )

        try:
            self._client.rejoin_instance_into_cluster(
                cluster_name=self._cluster,
                instance_host=instance_host,
                instance_port=str(3306),
            )
        except ExecutionError:
            logger.error(f"Failed to rejoin instance {instance_label}")
            raise
        finally:
            self._release_lock(
                instance_label=instance_label,
                instance_task=self._lock_builder.INSTANCE_ADDITION_TASK,
            )

    def set_instance_option(self, option: str, value: Any) -> None:
        """Set an instance option within the MySQL cluster."""
        self._client.update_instance_within_cluster(
            cluster_name=self._cluster,
            instance_host=self._host,
            instance_port=self._port,
            options={option: value},
        )

    def remove_router(self, router_id: str) -> None:
        """Remove a MySQL cluster router."""
        router_name, router_mode = router_id.split("::")

        self._client.remove_router_from_cluster(
            cluster_name=self._cluster,
            router_name=router_name,
            router_mode=router_mode,
        )

    def reboot(self) -> None:
        """Reboot the MySQL cluster from complete outage."""
        self._client.reboot_cluster(self._cluster)

    def rescan(self) -> None:
        """Rescan the MySQL cluster topology."""
        self._client.rescan_cluster(self._cluster)
