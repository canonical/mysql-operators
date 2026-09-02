# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from functools import cached_property

from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceRole

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

    @cached_property
    def is_cluster_primary(self) -> bool:
        """Return whether the MySQL instance is the primary."""
        return self._clients.instance.fetch_role() == InstanceRole.PRIMARY

    def get_removing_flag(self) -> bool | None:
        """Get the unit removing flag."""
        return self._state.unit.get_unit_removing_flag()

    def set_removing_flag(self) -> None:
        """Set the unit removing flag."""
        self._state.unit.set_unit_removing_flag()

    def create_database(self, database: str) -> None:
        """Create a MySQL instance database."""
        if database in self._clients.instance.fetch_databases():
            logger.debug("Skipping database creation: database already exists")
            return

        try:
            self._clients.instance.create_database(database)
        except ExecutionError as e:
            raise RuntimeError("Failed to create database") from e

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

        try:
            self._clients.instance.create_database_user(
                database=database,
                username=username,
                password=password,
                roles=roles,
            )
        except ExecutionError as e:
            raise RuntimeError("Failed to create database user") from e

        return password

    def delete_users(self, username: str) -> None:
        """Delete user and child users from the cluster."""
        attributes = {
            "created_by_user": username,
        }

        try:
            self._clients.instance.delete_user(username)
            self._clients.instance.delete_users_by_attrs(attributes)
        except ExecutionError as e:
            raise RuntimeError("Failed to delete users") from e

    def fetch_version(self) -> str:
        """Fetch the MySQL instance version."""
        try:
            return self._clients.instance.fetch_version()
        except ExecutionError as e:
            raise RuntimeError("Failed to fetch database version") from e

    def remove_router(self, router_user: str, router_name: str) -> None:
        """Remove a MySQL Router from the cluster."""
        attributes = {
            "created_by_juju_unit": router_name,
            "created_by_user": router_user,
        }

        router_user = self._clients.instance.fetch_user_by_attrs(attributes)
        if not router_user:
            return

        try:
            self._clients.instance.delete_user(router_user.username)
            self._clients.cluster.remove_router(router_user.attributes["router_id"])
        except ExecutionError as e:
            raise RuntimeError("Failed to delete router user") from e
