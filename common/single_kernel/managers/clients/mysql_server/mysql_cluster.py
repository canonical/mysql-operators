# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

import tenacity
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

        try:
            logger.debug(f"Acquiring lock {instance_task} for instance {instance_label}")
            self._executor.execute_sql(acquire_query)
        except ExecutionError:
            logger.error(f"Failed to acquire lock {instance_task}")
            raise

    def _release_lock(self, instance_label: str, instance_task: str) -> None:
        """Releases a lock within the instance operations table."""
        release_query = self._lock_builder.build_release_query(instance_task, instance_label)

        try:
            logger.debug(f"Releasing lock {instance_task} for unit {instance_label}")
            self._executor.execute_sql(release_query)
        except ExecutionError:
            logger.error(f"Failed to release lock {instance_task}")
            raise

    @contextmanager
    def _locking(self, instance_label: str, instance_task: str) -> Iterator[None]:
        """Wraps the desired operation into a cluster-level lock."""
        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(10),
            wait=tenacity.wait_fixed(10),
            reraise=True,
        ):
            with attempt:
                self._acquire_lock(instance_label, instance_task)

        try:
            yield
        finally:
            self._release_lock(instance_label, instance_task)

    def add_instance(self, instance_label: str, instance_host: str, method: str = "auto") -> None:
        """Add an instance into the MySQL cluster.

        This function can only be executed from the cluster-set primary.
        Only the MySQL cluster instances can join other instances.
        """
        options = {
            "label": instance_label,
            "recoveryMethod": method,
        }

        with self._locking(instance_label, self._lock_builder.INSTANCE_ADDITION_TASK):
            try:
                self._client.attach_instance(
                    cluster_name=self._cluster,
                    instance_host=instance_host,
                    instance_port=str(3306),
                    options=options,
                )
            except ExecutionError as e:
                logger.warning(f"Failed to add instance to cluster: {e}")
                if method == "clone":
                    raise

                logger.warning(f"Defaulting to `clone` recovery method")
                self._client.attach_instance(
                    cluster_name=self._cluster,
                    instance_host=instance_host,
                    instance_port=str(3306),
                    options={**options, "recoveryMethod": "clone"},
                )

    def create(self, instance_label: str) -> None:
        """Create the MySQL cluster from current instance."""
        self._client.create_cluster(
            cluster_name=self._cluster,
            options={"communicationStack": "MySQL"},
        )
        self._client.update_instance(
            cluster_name=self._cluster,
            instance_host=self._host,
            instance_port=self._port,
            options={"label": instance_label},
        )

    def drop_metadata(self) -> None:
        """Drop the replication schema."""
        self._executor.execute_py("dba.drop_metadata_schema()")

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
            logger.warning("Cluster does not have quorum")
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

    def init_locks_table(self) -> None:
        """Initialize the instance locks table."""
        query = self._lock_builder.build_table_creation_query()

        try:
            logger.debug("Initializing locks table")
            self._executor.execute_sql(query)
        except ExecutionError as e:
            logger.error(f"Failed to initialize locks table: {e}")
            raise

    def promote_instance(self, instance_host: str) -> None:
        """Promote an instance into the MySQL cluster primary."""
        self._client.promote_instance(
            cluster_name=self._cluster,
            instance_host=instance_host,
            instance_port=str(3306),
        )

    def rejoin_instance(self, instance_label: str, instance_host: str) -> None:
        """Rejoin an instance back into the MySQL cluster.

        This function can only be executed from the cluster-set primary.
        Only the MySQL cluster instances can join other instances.
        """
        with self._locking(instance_label, self._lock_builder.INSTANCE_ADDITION_TASK):
            self._client.rejoin_instance(
                cluster_name=self._cluster,
                instance_host=instance_host,
                instance_port=str(3306),
            )

    def set_instance_option(self, option: str, value: Any) -> None:
        """Set an instance option within the MySQL cluster."""
        self._client.update_instance(
            cluster_name=self._cluster,
            instance_host=self._host,
            instance_port=self._port,
            options={option: value},
        )

    def set_instance_config(self, username: str, password: str) -> None:
        """Set an instance config before the MySQL cluster."""
        options = {"restart": True}

        if username and password:
            options = {
                "clusterAdmin": username,
                "clusterAdminPassword": password,
                "restart": True,
            }

        self._client.setup_instance_config(options)

    def remove_instance(self, instance_label: str, instance_host: str) -> None:
        """Remove an instance from the MySQL cluster.

        This function can only be executed from the cluster-set primary.
        Only the MySQL cluster instances can join other instances.
        """
        context = self._locking(instance_label, self._lock_builder.INSTANCE_REMOVAL_TASK)

        # Only when the primary is being removed (for example in a scale down to zero scenario)
        # we should avoid locking, given that we do not know which instance will become primary,
        # and therefore, hold the lock
        if self.fetch_primary_host() == instance_host:
            context = nullcontext()

        with context:
            self._client.detach_instance(
                cluster_name=self._cluster,
                instance_host=instance_host,
                instance_port=str(3306),
                options={"force": True},
            )

    def remove_router(self, router_id: str) -> None:
        """Remove a MySQL cluster router."""
        router_name, router_mode = router_id.split("::")

        self._client.remove_router(
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
