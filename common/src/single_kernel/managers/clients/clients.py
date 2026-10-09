# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
import logging
from contextlib import contextmanager, suppress
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
        instance_client: MySQLInstanceClient,
        cluster_client: MySQLClusterClient,
        cluster_set_client: MySQLClusterSetClient,
    ):
        """Initialize the class attributes."""
        self._instance_client = instance_client
        self._cluster_client = cluster_client
        self._cluster_set_client = cluster_set_client

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
        except ExecutionError:
            logging.error(f"Failed to execute operation in {instance_host}")
            raise

    @contextmanager
    def build_cluster_set_client(self, instance_host: str) -> Iterator[MySQLClusterSetClient]:
        """Build a cluster-set client for the given host."""
        client = copy.deepcopy(self._cluster_set_client)
        client._executor._conn_details.host = instance_host

        try:
            yield client
        except ExecutionError:
            logging.error(f"Failed to execute operation in {instance_host}")
            raise

    @contextmanager
    def build_instance_client(self, instance_host: str) -> Iterator[MySQLInstanceClient]:
        """Build a cluster client for the given host."""
        client = copy.deepcopy(self._instance_client)
        client._executor._conn_details.host = instance_host

        try:
            yield client
        except ExecutionError:
            logging.error(f"Failed to execute operation in {instance_host}")
            raise

    def find_cluster_primary(self, addresses: list[str]) -> str | None:
        """Find the MySQL cluster-set primary from a list of addresses."""
        for address in addresses:
            with suppress(RuntimeError):
                with self.build_cluster_set_client(address) as client:
                    return client.fetch_primary_host()

        return None

    def configure_instance(self, username: str = "", password: str = "") -> None:
        """Configure the MySQL instance."""
        self._cluster_client.set_instance_config(username, password)

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_delay(120),
            wait=tenacity.wait_fixed(2),
            reraise=True,
        ):
            with attempt:
                self._instance_client._executor.check_connection()

    def promote_instance(self, instance_host: str, force: bool) -> None:
        """Promote the MySQL instance."""
        if self._cluster_client.fetch_primary_host() == instance_host:
            logging.warning(f"Skipping instance promotion: {instance_host} is already primary")
            return

        self._cluster_client.promote_instance(instance_host, force)

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate the MySQL cluster."""
        self._cluster_client.init_locks_table()

        try:
            self._cluster_client.create(instance_label)
            self._cluster_set_client.create(self._cluster_client._cluster)
            self._cluster_client.rescan()
        except ExecutionError:
            logging.error(f"Failed to recreate cluster from {instance_label}")
            raise
