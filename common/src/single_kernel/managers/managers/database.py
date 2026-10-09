# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Class to deal with the operator database provider."""

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def get_removing_flag(self) -> bool | None:
        """Get the unit removing flag."""
        return self._state.unit.get_unit_removing_flag()

    def set_removing_flag(self) -> None:
        """Set the unit removing flag."""
        self._state.unit.set_unit_removing_flag()

    def create_database(self, database: str) -> None:
        """Create a MySQL instance database."""
        if database in self._clients.instance.fetch_databases():
            logger.warning("Skipping database creation: database already exists")
            return

        primary_host = self._clients.cluster_set.fetch_primary_host()
        if not primary_host:
            raise RuntimeError("Failed to fetch cluster-set primary: no quorum")

        with self._clients.build_instance_client(primary_host) as client:
            client.create_database(database)

    def create_database_user(
        self,
        database: str,
        username: str,
        password: str | None,
        roles: list[str] | None = None,
    ) -> str:
        """Create a MySQL instance user."""
        if not password:
            password = self._clients.instance.create_password()

        primary_host = self._clients.cluster_set.fetch_primary_host()
        if not primary_host:
            raise RuntimeError("Failed to fetch cluster-set primary: no quorum")

        with self._clients.build_instance_client(primary_host) as client:
            client.create_database_user(
                database=database,
                username=username,
                password=password,
                roles=roles,
            )

        return password

    def delete_users(self, username: str) -> None:
        """Delete user and child users from the cluster."""
        primary_host = self._clients.cluster_set.fetch_primary_host()
        if not primary_host:
            raise RuntimeError("Failed to fetch cluster-set primary: no quorum")

        attributes = {
            "created_by_user": username,
        }

        with self._clients.build_instance_client(primary_host) as client:
            client.delete_user(username)
            client.delete_users_by_attrs(attributes)

    def fetch_version(self) -> str:
        """Fetch the MySQL instance version."""
        return self._clients.instance.fetch_version()

    def remove_router(self, router_user: str, router_name: str) -> None:
        """Remove a MySQL Router from the cluster."""
        primary_host = self._clients.cluster_set.fetch_primary_host()
        if not primary_host:
            raise RuntimeError("Failed to fetch cluster-set primary: no quorum")

        attributes = {
            "created_by_juju_unit": router_name,
            "created_by_user": router_user,
        }

        router_user = self._clients.instance.fetch_user_by_attrs(attributes)
        if not router_user:
            return

        with self._clients.build_instance_client(primary_host) as client:
            client.delete_user(router_user.username)
        with self._clients.build_cluster_client(primary_host) as client:
            client.remove_router(router_user.attributes["router_id"])
