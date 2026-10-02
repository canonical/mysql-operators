# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import hashlib
import logging
import random
from functools import cached_property

from mysql_shell.models import InstanceRole

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients
from ..models import SystemUser

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Class to deal with the operator lifecycle."""

    cluster_max_size = 9

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    @staticmethod
    def _create_random_hash() -> str:
        """Generate a random hash string."""
        random_int = int(random.getrandbits(64))
        random_str = str(random_int).encode()
        random_hash = hashlib.md5(random_str).hexdigest()

        return random_hash[:10]

    @cached_property
    def is_cluster_primary(self) -> bool:
        """Return whether the MySQL instance is the primary."""
        return self._clients.instance.fetch_role() == InstanceRole.PRIMARY

    def set_leader_flag(self, flag: bool) -> None:
        """Set the unit leader flag."""
        self._state.unit.set_unit_leader_flag(flag)

    def set_cluster_name(self, name: str | None) -> None:
        """Set the MySQL cluster name."""
        if not name:
            name = self._state.app.get_cluster_name()
        if not name:
            name = f"cluster-{self._create_random_hash()}"

        self._state.app.set_cluster_name(name)

    def set_cluster_set_name(self, name: str | None) -> None:
        """Set the MySQL cluster name."""
        if not name:
            name = self._state.app.get_cluster_set_name()
        if not name:
            name = f"cluster-set-{self._create_random_hash()}"

        self._state.app.set_cluster_set_name(name)

    def fetch_cluster_instances(self) -> dict[str, dict]:
        """Fetch the MySQL cluster instances."""
        return self._clients.cluster.fetch_instances()

    def create_system_password(self) -> str:
        """Create a MySQL instance system password."""
        return self._clients.instance.create_password()

    def create_system_roles(self, router_role: str) -> None:
        """Configure the MySQL instance system roles."""
        self._clients.instance.create_router_role(router_role)
        self._clients.instance.create_auth_roles()

    def create_system_users(self, users: list[SystemUser]) -> None:
        """Configure a MySQL instance system users."""
        self._clients.instance.delete_root()

        for user in users:
            self._clients.instance.create_user(user.username, user.password, user.roles)

    def install_system_components(self, components: list[str]) -> None:
        """Configure the MySQL instance system components."""
        self._clients.instance.install_components(components)

    def configure_instance(self, username: str, password: str) -> None:
        """Configure the MySQL instance cluster settings."""
        self._clients.configure_instance(username, password)

    def promote_instance(self, instance_host: str) -> None:
        """Promote a MySQL instance."""
        self._clients.promote_instance(instance_host, force=False)

    def remove_instance(self, instance_host: str, instance_label: str, addrs: list[str]) -> None:
        """Remove the MySQL instance from the cluster.

        This function can only be executed from the cluster primary.
        Only the MySQL cluster primary can remove other instances.
        """
        primary_host = self._clients.find_cluster_primary(addrs)
        if not primary_host:
            logger.error("Failed to find cluster primary")
            return

        with self._clients.build_cluster_client(primary_host) as client:
            if instance_label in client.fetch_instances():
                client.remove_instance(instance_label, instance_host)

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate cluster."""
        self._clients.configure_instance()
        self._clients.recreate_cluster(instance_label)

    def update_state(self, role: str | None = None, state: str | None = None) -> None:
        """Update the operator state."""
        if not role:
            role = self._clients.instance.fetch_role()
        if not state:
            state = self._clients.instance.fetch_state()

        logger.info(f"Instance member-role is {role}")
        logger.info(f"Instance member-state is {state}")

        self._state.unit.set_instance_role(role)
        self._state.unit.set_instance_state(state)
