# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from mysql_shell.models import ClusterRole, InstanceState

from ...managers.clients import Clients
from ...managers.managers import ConfigManager, RefreshManager, RollingManager
from .lifecycle import (
    ConfigHelper,
    RefreshHelper,
    RollingHelper,
)

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class Helpers:
    """Class to wrap all the helpers."""

    def __init__(self, charm: Operator, clients: Clients):
        """Initialize the class attributes."""
        self._charm = charm
        self._clients = clients

        self._config = ConfigHelper(charm, ConfigManager(None, charm.system, clients))
        self._refresh = RefreshHelper(charm, RefreshManager(None, charm.system, clients))
        self._rolling = RollingHelper(charm, RollingManager(None, charm.system, clients))

    @property
    def refresh(self) -> RefreshHelper:
        """Return the MySQL instance refresh."""
        return self._refresh

    @property
    def rolling(self) -> RollingHelper:
        """Return the MySQL instance rolling ops."""
        return self._rolling

    def apply_config(self) -> None:
        """Apply the MySQL instance configuration."""
        config_diff = self._config.update_config()

        if self._config.check_restart(config_diff):
            self._rolling.callbacks.request_async_lock(callback_id="restart")

    def build_cluster_endpoints(self, relation: str) -> tuple[list, list, list]:
        """Return (rw, ro, offline) endpoints tuple."""
        cluster_instances = self._clients.cluster.fetch_instances()
        cluster_role = self._clients.cluster.fetch_role()

        no_addresses = []
        ro_addresses = []
        rw_addresses = []

        for label, info in cluster_instances.items():
            # When a replica instance is catching up with the primary instance,
            # the custom label assigned by the operator code has not yet been applied.
            if info["status"] == InstanceState.RECOVERING:
                continue

            try:
                address = f"{self._charm.get_unit_address(self._charm.unit, relation)}:3306"
            except RuntimeError:
                logger.warning(f"Unit {self._charm.unit} address is not available")
                continue

            if info["status"] != InstanceState.ONLINE:
                no_addresses.append(address)
            if info["status"] == InstanceState.ONLINE and info["mode"] == "R/O":
                ro_addresses.append(address)
            if info["status"] == InstanceState.ONLINE and info["mode"] == "R/W":
                rw_addresses.append(address) if cluster_role == ClusterRole.PRIMARY else None

        # Replica return global primary address
        if cluster_role == ClusterRole.REPLICA:
            primary_address = f"{self._clients.cluster_set.fetch_primary_host()}:3306"
            rw_addresses.append(primary_address)

        return rw_addresses, ro_addresses, no_addresses
