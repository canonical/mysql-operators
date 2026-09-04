# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import time
from typing import Any

from mysql_shell.builders import BaseAuthorizationQueryBuilder
from mysql_shell.clients import InstanceClient
from mysql_shell.executors import BaseExecutor
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceState, User
from mysql_shell.models import VariableScope as Scope

logger = logging.getLogger(__name__)


class MySQLInstanceClient:
    """Class to deal with the MySQL instance."""

    system_rolename_len = 32
    system_databases = {
        "information_schema",
        "mysql",
        "mysql_innodb_cluster_metadata",
        "performance_schema",
        "sys",
    }

    def __init__(self, executor: BaseExecutor, auth_builder: BaseAuthorizationQueryBuilder):
        """Initialize the class attributes."""
        self._executor = executor
        self._client = InstanceClient(executor)
        self._auth_builder = auth_builder

    def _build_database_dba_role(self, database_name: str) -> str:
        """Build the instance database DBA role, given length constraints."""
        role_prefix = "charmed_dba"
        role_suffix = "XX"

        role_name_available = self.system_rolename_len - len(role_prefix) - len(role_suffix) - 2
        role_name_trimmed = database_name[:role_name_available]
        role_name_pattern = f"{role_prefix}_{role_name_trimmed}_%"

        role_name_collisions = self._client.search_instance_roles(role_name_pattern)

        return "_".join((
            role_prefix,
            role_name_trimmed,
            str(len(role_name_collisions)).zfill(len(role_suffix)),
        ))

    def _set_variable(self, scope: Scope, name: str, value: Any) -> None:
        """Set an instance global scoped variable."""
        self._client.set_instance_variable(
            scope=scope,
            name=name,
            value=value,
        )

    def create_database(self, database: str) -> None:
        """Create an instance database."""
        self._client.create_instance_database(database)

        rolename = self._build_database_dba_role(database)
        queries = ";".join([
            self._auth_builder.build_instance_reader_role_update_query(database),
            self._auth_builder.build_instance_writer_role_update_query(database),
            self._auth_builder.build_database_admin_role_query(rolename, database),
        ])

        try:
            self._executor.execute_sql(queries)
        except ExecutionError:
            logger.error(f"Failed to create database DBA role {rolename}")
            raise
        else:
            logger.info(f"Succeeded to create database DBA role {rolename}")

    def create_database_user(
        self,
        database: str,
        username: str,
        password: str,
        attributes: dict[str, str] | None = None,
        extra_roles: list[str] | None = None,
    ) -> None:
        """Create an instance user."""
        host = "%"
        user = User(username, host, attributes)
        self._client.create_instance_user(user, password, extra_roles)

        if extra_roles:
            return

        queries = ";".join([
            f"GRANT USAGE ON *.* TO `{username}`@`{host}`",
            f"GRANT ALL PRIVILEGES ON `{database}`.* TO `{username}`@`{host}`",
        ])

        try:
            self._executor.execute_sql(queries)
        except ExecutionError:
            logger.error(f"Failed to grant privileges to user {username}")
            raise
        else:
            logger.info(f"Succeeded to grant privileges to user {username}")

    def delete_user(self, username: str) -> None:
        """Delete an instance user."""
        user = User(username, "%")
        ____ = self._client.delete_instance_user(user)

    def delete_users_by_attrs(self, attributes: dict[str, str]) -> None:
        """Delete the instance users selected by their attributes."""
        users = self._client.search_instance_users("%", attributes)
        _____ = self._client.delete_instance_users(users)

    def fetch_user_by_attrs(self, attributes: dict[str, str]) -> User | None:
        """Fetch the instance user selected by its attributes."""
        users = self._client.search_instance_users("%", attributes)
        if len(users) > 1:
            logger.warning(f"Multiple users with attributes {attributes}")

        if users:
            return users[0]
        else:
            return None

    def fetch_databases(self) -> list[str]:
        """Fetch the instance databases."""
        databases = self._client.search_instance_databases("%")
        databases = set(databases) - self.system_databases

        return list(databases)

    def fetch_role(self) -> str:
        """Fetch the instance role."""
        if state := self._client.get_instance_replication_role():
            return state.value
        else:
            return "UNKNOWN"

    def fetch_state(self) -> str:
        """Fetch the instance state."""
        if state := self._client.get_instance_replication_state():
            return state.value
        else:
            return "UNKNOWN"

    def fetch_version(self) -> str:
        """Fetch the instance version."""
        if version := self._client.get_instance_version():
            return version
        else:
            return ""

    def fetch_cluster_labels(self) -> list[str]:
        """Fetch the instance cluster metadata."""
        return self._client.get_cluster_labels()

    def count_cluster_members(self, states: list[InstanceState] | None = None) -> int:
        """Count the number of cluster members in the provided states."""
        try:
            status = self._client.search_instance_replication_members(states=states)
        except ExecutionError:
            logger.warning("Failed to count cluster members")
            return 0
        else:
            return len(status)

    def kill_client_sessions(self) -> None:
        """Kill the instance open client connections."""
        procs = self._client.search_instance_connection_processes("%")
        return self._client.stop_instance_processes(procs)

    def set_client_tls(self, ca_path: str, key_path: str, cert_path: str, enable: bool) -> None:
        """Set an instance client connections TLS configuration."""
        tls_usage = "ON" if enable else "OFF"

        try:
            self._set_variable(Scope.PERSIST, "ssl_ca", ca_path)
            self._set_variable(Scope.PERSIST, "ssl_key", key_path)
            self._set_variable(Scope.PERSIST, "ssl_cert", cert_path)
            self._set_variable(Scope.PERSIST, "require_secure_transport", tls_usage)
            self._client.reload_instance_certs()
        except ExecutionError as e:
            logger.error(f"Failed to setup client TLS: {e}")
            raise

    def set_group_tls(self, ca_path: str, key_path: str, cert_path: str, enable: bool) -> None:
        """Set an instance group connections TLS configuration."""
        tls_usage = "ON" if enable else "OFF"
        tls_mode = "REQUIRED" if enable else "DISABLED"

        try:
            self._set_variable(Scope.PERSIST, "group_replication_recovery_ssl_ca", ca_path)
            self._set_variable(Scope.PERSIST, "group_replication_recovery_ssl_key", key_path)
            self._set_variable(Scope.PERSIST, "group_replication_recovery_ssl_cert", cert_path)
            self._set_variable(Scope.PERSIST, "group_replication_recovery_use_ssl", tls_usage)
            self._set_variable(Scope.PERSIST, "group_replication_ssl_mode", tls_mode)
        except ExecutionError as e:
            logger.error(f"Failed to setup group TLS: {e}")
            raise

    def update_variable(self, name: str, value: Any) -> None:
        """Update an instance global scoped variable."""
        self._set_variable(Scope.GLOBAL, name, value)

    def update_user(self, username: str, password: str) -> None:
        """Update an instance user information."""
        user = User(username, "%")
        self._client.update_instance_user(user, password)

    def wait_recovering(self) -> None:
        """Wait for the instance to recover."""
        while True:
            try:
                state = self.fetch_state()
            except ExecutionError:
                break

            if state == InstanceState.RECOVERING:
                time.sleep(10)
            else:
                break
