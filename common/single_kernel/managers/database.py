# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import secrets
import string
from functools import cached_property

from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceRole

from ..clients import MySQLClusterClient, MySQLInstanceClient
from ..state import DatabaseState
from ..workload import BaseSystem

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Class to deal with the operator database provider."""

    default_password_len = 24

    def __init__(
        self,
        state: DatabaseState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    @cached_property
    def _is_cluster_primary(self) -> bool:
        """Return whether the MySQL instance is the primary."""
        return self._instance_client.fetch_role() == InstanceRole.PRIMARY

    def _generate_password(self) -> str:
        """Generate a random password."""
        choices = string.ascii_letters + string.digits

        while True:
            password = "".join([secrets.choice(choices) for _ in range(self.default_password_len)])
            if all((
                any(c.islower() for c in password),
                any(c.isupper() for c in password),
                any(c.isdigit() for c in password),
            )):
                return password

    def create_database(self, database: str) -> None:
        """Create a MySQL instance database."""
        if not self._is_cluster_primary:
            logger.debug("Skipping database creation: instance is not the primary")
            return

        if database in self._instance_client.fetch_databases():
            logger.debug("Skipping database creation: database already exists")
            return

        try:
            self._instance_client.create_database(database)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to create database: {e}")

    def create_database_user(
        self,
        database: str,
        username: str,
        password: str | None = None,
        attributes: dict[str, str] | None = None,
        extra_roles: list[str] | None = None,
    ) -> str | None:
        """Create a MySQL instance user."""
        if not self._is_cluster_primary:
            logger.debug("Skipping database user creation: instance is not the primary")
            return

        if not password:
            password = self._generate_password()

        try:
            self._instance_client.create_database_user(
                database=database,
                username=username,
                password=password,
                attributes=attributes,
                extra_roles=extra_roles,
            )
        except ExecutionError as e:
            raise RuntimeError(f"Failed to create database user: {e}")

        return password

    def delete_users(self, parent_user: str) -> None:
        """Delete all users in the cluster."""
        if not self._is_cluster_primary:
            logger.debug("Skipping users deletion: instance is not the primary")
            return

        attributes = {
            "created_by_user": parent_user,
        }

        try:
            self._instance_client.delete_users_by_attrs(attributes)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to delete users: {e}")

    def remove_router(self, router_user: str, router_name: str) -> None:
        """Remove a MySQL Router from the cluster."""
        if not self._is_cluster_primary:
            logger.debug("Skipping router user deletion: instance is not the primary")
            return

        attributes = {
            "created_by_juju_unit": router_name,
            "created_by_user": router_user,
        }

        router_user = self._instance_client.fetch_user_by_attrs(attributes)
        if not router_user:
            return

        try:
            self._instance_client.delete_user(router_user.username)
            self._cluster_client.remove_router(router_user.attributes["router_id"])
        except ExecutionError as e:
            raise RuntimeError(f"Failed to delete router user: {e}")
