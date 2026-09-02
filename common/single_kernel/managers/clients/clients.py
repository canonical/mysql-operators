# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
from contextlib import contextmanager
from typing import Iterator

import tenacity
from mysql_shell.executors.errors import ExecutionError

from .mysql_server import (
    MySQLClusterClient,
    MySQLClusterSetClient,
    MySQLInstanceClient,
)


class Clients:
    """Class to wrap all the clients."""

    def __init__(
        self,
        cluster_client: MySQLClusterClient,
        cluster_set_client: MySQLClusterSetClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._cluster_client = cluster_client
        self._cluster_set_client = cluster_set_client
        self._instance_client = instance_client

    @property
    def cluster(self) -> MySQLClusterClient:
        """Return the MySQL cluster client."""
        return self._cluster_client

    @property
    def cluster_set(self) -> MySQLClusterSetClient:
        """Return the MySQL cluster-set client."""
        return self._cluster_set_client

    @property
    def instance(self) -> MySQLInstanceClient:
        """Return the MySQL instance client."""
        return self._instance_client

    @contextmanager
    def build_cluster_client(self, instance_host: str) -> Iterator[MySQLClusterClient]:
        """Build a cluster client for the given host."""
        client = copy.deepcopy(self._cluster_client)
        client._executor._conn_details.host = instance_host

        try:
            yield client
        except ExecutionError as e:
            raise RuntimeError(f"Failed to execute operation in {instance_host}") from e

    @contextmanager
    def build_instance_client(self, instance_host: str) -> Iterator[MySQLInstanceClient]:
        """Build a cluster client for the given host."""
        client = copy.deepcopy(self._instance_client)
        client._executor._conn_details.host = instance_host

        try:
            yield client
        except ExecutionError as e:
            raise RuntimeError(f"Failed to execute operation in {instance_host}") from e

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate the MySQL cluster."""
        try:
            self._cluster_client.drop_metadata()
            self._cluster_client.init_locks_table()

            self._cluster_client.create(instance_label)
            self._cluster_set_client.create(self._cluster_client._cluster)
            self._cluster_client.rescan()
        except ExecutionError as e:
            raise RuntimeError("Failed to recreate cluster") from e

    def configure_instance(self, username: str = "", password: str = "") -> None:
        """Configure the MySQL instance."""
        try:
            self._cluster_client.set_instance_config(username, password)

            for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_delay(120),
                wait=tenacity.wait_fixed(2),
                reraise=True,
            ):
                with attempt:
                    self._instance_client._executor.check_connection()
        except ExecutionError as e:
            raise RuntimeError("Failed to configure instance") from e
