# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterRole, ClusterStatus, InstanceRole, InstanceState
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, StatusBase

from ...managers.clients import Clients
from ...managers.managers import ConfigManager, RollingManager
from .events import ConfigHelper, RollingHelper

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class EventHelpers:
    """Class to wrap all the event helpers."""

    def __init__(self, charm: BaseCharm, clients: Clients):
        """Initialize the class attributes."""
        self._charm = charm
        self._clients = clients

        self._config = ConfigHelper(charm, ConfigManager(None, charm.system, clients))
        self._rolling = RollingHelper(charm, RollingManager(None, charm.system, clients))

    @property
    def config(self) -> ConfigHelper:
        """Return the config helper."""
        return self._config

    @property
    def rolling(self) -> RollingHelper:
        """Return the rolling helper."""
        return self._rolling

    @property
    def initialized(self) -> bool:
        """Return whether the operator is initialized."""
        if not self._charm.service_server.running:
            logger.debug(f"Failed to connect to MySQL Server: unit not yet initialized")
            return False

        try:
            cluster_labels = self._clients.instance.fetch_cluster_labels()
        except ExecutionError as e:
            logger.debug(f"Failed to fetch the cluster labels: {e}")
            return False

        return self._charm.cluster_name in cluster_labels

    def apply_config(self) -> None:
        """Apply the MySQL instance config."""
        config_old = self._config.load_config()
        config_new = self._config.save_config()

        _______ = self._config.apply_config(config_old, config_new)
        restart = self._config.check_restart(config_old, config_new)

        if self.initialized and restart:
            logger.info("Configuration change requires restart")
            self._rolling.callbacks.request_async_lock(callback_id="restart")

    def build_cluster_endpoints(self, relation: str) -> tuple[list, list, list]:
        """Return the MySQL cluster endpoints."""
        cluster_instances = self._clients.cluster.fetch_instances()
        cluster_role = self._clients.cluster.fetch_role()

        unit_labels = {self._charm.get_unit_label(unit): unit for unit in self._charm.units}

        no_endpoints = []
        ro_endpoints = []
        rw_endpoints = []

        for label, info in cluster_instances.items():
            # When the instance is still catching up with the primary instance,
            # the label assigned by the operator may not be applied yet.
            if info["status"] == InstanceState.RECOVERING:
                continue

            # When the unit is still joining the peer-to-peer relation,
            # the address persisted by the operator may not be available yet.
            if label not in unit_labels:
                continue

            unit_address = self._charm.get_unit_address(unit_labels[label], relation)
            unit_endpoint = f"{unit_address}:3306"

            if info["status"] != InstanceState.ONLINE:
                no_endpoints.append(unit_endpoint)
            if info["status"] == InstanceState.ONLINE and info["mode"] == "R/O":
                ro_endpoints.append(unit_endpoint)
            if info["status"] == InstanceState.ONLINE and info["mode"] == "R/W":
                rw_endpoints.append(unit_endpoint) if cluster_role == ClusterRole.PRIMARY else None

        # Replica return global primary address
        if cluster_role == ClusterRole.REPLICA:
            rw_address = self._clients.cluster_set.fetch_primary_host()
            rw_endpoint = f"{rw_address}:3306"
            rw_endpoints.append(rw_endpoint)

        return rw_endpoints, ro_endpoints, no_endpoints

    def build_app_status(self) -> StatusBase:
        """Build the MySQL cluster application status."""
        units = self._clients.cluster.fetch_instances()
        state = self._clients.cluster.fetch_state()

        match state:
            case ClusterStatus.OK | ClusterStatus.OK_PARTIAL:
                return ActiveStatus("Healthy")
            case ClusterStatus.OK_NO_TOLERANCE | ClusterStatus.OK_NO_TOLERANCE_PARTIAL:
                return ActiveStatus("Healthy") if len(units) < 3 else ActiveStatus("Degraded")
            case ClusterStatus.NO_QUORUM:
                return BlockedStatus("No quorum")
            case ClusterStatus.OFFLINE | ClusterStatus.ERROR:
                return BlockedStatus("No online members")
            case ClusterStatus.UNREACHABLE:
                return BlockedStatus("No connectivity")

        return MaintenanceStatus("Unknown")

    def build_unit_status(self) -> StatusBase:
        """Build the MySQL cluster unit status."""
        instance_role = self._clients.instance.fetch_role()
        instance_state = self._clients.instance.fetch_state()

        if instance_role != InstanceRole.PRIMARY:
            return ActiveStatus("")
        if instance_state != InstanceState.ONLINE:
            return MaintenanceStatus("")

        cluster_role = self._clients.cluster.fetch_role()
        cluster_state = self._clients.cluster.fetch_state()

        if cluster_role == ClusterRole.PRIMARY:
            return ActiveStatus("Primary")

        return ActiveStatus(f"Standby ({cluster_state})")
