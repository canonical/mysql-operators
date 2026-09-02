# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import secrets
import string
import time
from contextlib import suppress
from typing import Any, Mapping, Sequence

from mysql_shell.builders import BaseAuthorizationQueryBuilder, BaseLoggingQueryBuilder
from mysql_shell.clients import InstanceClient
from mysql_shell.executors import BaseExecutor
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceState, LogType, User
from mysql_shell.models import VariableScope as Scope

logger = logging.getLogger(__name__)


class MySQLInstanceClient:
    """Class to deal with the MySQL instance."""

    system_password_len = 24
    system_rolename_len = 32
    system_databases = {
        "information_schema",
        "mysql",
        "mysql_innodb_cluster_metadata",
        "performance_schema",
        "sys",
    }
    system_components = {
        "audit_log_filter": "file://component_audit_log_filter",
        "binlog_utils_udf": "file://component_binlog_utils_udf",
        "validate_password": "file://component_validate_password",
    }

    def __init__(
        self,
        executor: BaseExecutor,
        builder_auth: BaseAuthorizationQueryBuilder,
        builder_logs: BaseLoggingQueryBuilder,
    ):
        """Initialize the class attributes."""
        self._executor = executor
        self._client = InstanceClient(executor)
        self._builder_auth = builder_auth
        self._builder_logs = builder_logs

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
            self._builder_auth.build_instance_reader_role_update_query(database),
            self._builder_auth.build_instance_writer_role_update_query(database),
            self._builder_auth.build_database_admin_role_query(rolename, database),
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
        roles: list[str] | None = None,
    ) -> None:
        """Create an instance user."""
        user = User(username, "%")
        self._client.create_instance_user(user, password, roles)

        if roles:
            return

        queries = ";".join([
            f"GRANT USAGE ON *.* TO `{username}`",
            f"GRANT ALL PRIVILEGES ON `{database}`.* TO `{username}`",
        ])

        try:
            self._executor.execute_sql(queries)
        except ExecutionError:
            logger.error(f"Failed to grant privileges to user {username}")
            raise
        else:
            logger.info(f"Succeeded to grant privileges to user {username}")

    def create_router_role(self, rolename: str) -> None:
        """Create an instance role for the MySQL Router users."""
        # The granting of all privileges to the MySQL Router role can only be restricted
        # when the privileges to the users created by such role are restricted as well
        # https://github.com/canonical/mysql-router-operators/blob/8.4/edge/common/common/mysql_shell/__init__.py#L131-L132
        queries = ";".join([
            f"CREATE ROLE {rolename}",
            f"GRANT CREATE ON *.* TO {rolename}",
            f"GRANT CREATE USER ON *.* TO {rolename}",
            f"GRANT ALL ON *.* TO {rolename} WITH GRANT OPTION",
        ])

        try:
            self._executor.execute_sql(queries)
        except ExecutionError:
            logger.error(f"Failed to create router role {rolename}")
            raise
        else:
            logger.info(f"Succeeded to create router role {rolename}")

    def create_auth_roles(self) -> None:
        """Create the instance auth roles."""
        query = self._builder_auth.build_instance_auth_roles_query()
        _____ = self._executor.execute_sql(query)

    def create_password(self) -> str:
        """Generate a random password."""
        choices = string.ascii_letters + string.digits

        while True:
            password = "".join([secrets.choice(choices) for _ in range(self.system_password_len)])
            if all((
                any(c.islower() for c in password),
                any(c.isupper() for c in password),
                any(c.isdigit() for c in password),
            )):
                return password

    def create_user(self, username: str, password: str, roles: Sequence[str] | None = None) -> None:
        """Create an instance user."""
        user = User(username, "%")
        ____ = self._client.create_instance_user(user, password, roles)

    def delete_user(self, username: str) -> None:
        """Delete an instance user."""
        user = User(username, "%")
        ____ = self._client.delete_instance_user(user)

    def delete_root(self) -> None:
        """Delete an instance user."""
        user = User("root", "localhost")
        ____ = self._client.delete_instance_user(user)

    def delete_users_by_attrs(self, attributes: Mapping[str, str]) -> None:
        """Delete the instance users selected by their attributes."""
        users = self._client.search_instance_users("%", attributes)
        _____ = self._client.delete_instance_users(users)

    def fetch_user_by_attrs(self, attributes: Mapping[str, str]) -> User | None:
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

    def flush_native_logs(self, logs: Sequence[LogType]) -> None:
        """Flush the instance native logs."""
        query = self._builder_logs.build_logs_flushing_query(logs)
        _____ = self._executor.execute_sql(query)

    def flush_audit_log(self) -> None:
        """Flush the instance audit logs."""
        query = "SELECT audit_log_rotate()"
        _____ = self._executor.execute_sql(query)

    def flush_host_cache(self):
        """Flush the instance host cache."""
        query = "TRUNCATE TABLE performance_schema.host_cache"
        _____ = self._executor.execute_sql(query)

    def count_cluster_members(self, states: Sequence[InstanceState] | None = None) -> int:
        """Count the number of cluster members in the provided states."""
        try:
            members = self._client.search_instance_replication_members(states=states)
        except ExecutionError:
            logger.warning("Failed to count cluster members")
            return 0
        else:
            return len(members)

    def install_components(self, components: Sequence[str]) -> None:
        """Install the provided components into the instance."""
        installed_components = self._client.search_instance_components("%")

        for component_name in components:
            component_urn = self.system_components.get(component_name)
            if component_urn in installed_components:
                logger.debug(f"Component {component_name} already installed")
                continue
            if component_urn is None:
                logger.warning(f"Component {component_name} is not supported")
                continue

            self._client.install_instance_component(component_urn)

    def kill_client_sessions(self) -> None:
        """Kill the instance open client connections."""
        procs = self._client.search_instance_connection_processes("%")
        return self._client.stop_instance_processes(procs)

    def set_client_tls(self, ca_path: str, cert_path: str, key_path: str, enable: bool) -> None:
        """Set an instance client connections TLS configuration."""
        tls_usage = "ON" if enable else "OFF"

        try:
            self._set_variable(Scope.PERSIST, "ssl_ca", ca_path)
            self._set_variable(Scope.PERSIST, "ssl_cert", cert_path)
            self._set_variable(Scope.PERSIST, "ssl_key", key_path)
            self._set_variable(Scope.PERSIST, "require_secure_transport", tls_usage)
            self._client.reload_instance_certs()
        except ExecutionError as e:
            logger.error(f"Failed to setup client TLS: {e}")
            raise

    def set_group_tls(self, ca_path: str, cert_path: str, key_path: str, enable: bool) -> None:
        """Set an instance group connections TLS configuration."""
        tls_usage = "ON" if enable else "OFF"
        tls_mode = "REQUIRED" if enable else "DISABLED"

        try:
            self._set_variable(Scope.PERSIST, "group_replication_recovery_ssl_ca", ca_path)
            self._set_variable(Scope.PERSIST, "group_replication_recovery_ssl_cert", cert_path)
            self._set_variable(Scope.PERSIST, "group_replication_recovery_ssl_key", key_path)
            self._set_variable(Scope.PERSIST, "group_replication_recovery_use_ssl", tls_usage)
            self._set_variable(Scope.PERSIST, "group_replication_ssl_mode", tls_mode)
        except ExecutionError as e:
            logger.error(f"Failed to setup group TLS: {e}")
            raise

    def stop_replication(self) -> None:
        """Stop the replication if enabled."""
        with suppress(ExecutionError):
            self._client.stop_instance_replication()

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
