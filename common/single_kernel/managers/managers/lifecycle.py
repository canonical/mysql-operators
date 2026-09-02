# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Sequence

from mysql_shell import ExecutionError

from ...state import LifecycleState
from ...workload import BaseSystem
from ..clients import Clients
from ..models import SystemUser

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Class to deal with the operator lifecycle."""

    cluster_max_size = 9

    def __init__(self, state: LifecycleState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def get_cluster_name(self) -> str | None:
        """Get the cluster name."""
        return self._state.get_cluster_name()

    def create_system_roles(self, router_role: str) -> None:
        """Configure the MySQL instance system roles."""
        try:
            self._clients.instance.create_router_role(router_role)
            self._clients.instance.create_auth_roles()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to create system roles") from e

    def create_system_users(self, users: Sequence[SystemUser]) -> None:
        """Configure a MySQL instance system users."""
        try:
            self._clients.instance.delete_root()
            for user in users:
                self._clients.instance.create_user(user.username, user.password, user.roles)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to create system users") from e

    def install_system_components(self, audit_log_enabled: bool) -> None:
        """Configure the MySQL instance system components."""
        components = ["binlog_utils_udf", "validate_password"]

        if audit_log_enabled:
            components.append("audit_log_filter")

        try:
            self._clients.instance.install_components(components)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to install system components") from e

    def update_state(self) -> None:
        """Update the operator state."""
        try:
            role = self._clients.instance.fetch_role()
            state = self._clients.instance.fetch_state()
        except ExecutionError as e:
            raise RuntimeError("Failed to update operator state") from e

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.set_instance_role(role)
        self._state.set_instance_state(state)
