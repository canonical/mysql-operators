# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import charm_refresh
import tenacity
from charmlibs.pathops import ContainerPath
from mysql_shell_contrib.executors import PebbleExecutor
from ops.model import Unit

from ...core import (
    RELATION_DATABASE,
    RELATION_PEERS,
    EndpointRole,
)
from ...events.handlers import (
    BackupS3EventHandler,
    DatabaseEventHandler,
    LifecycleEventHandler,
    LogRotationEventHandler,
    OperatorEventHandler,
    SelfHealingEventHandler,
    TLSClientEventHandler,
    TLSPeerEventHandler,
)
from ...events.helpers import EventHelpers
from ...managers.managers import (
    ClientTLSManager,
    DatabaseManager,
    LifecycleManager,
    LogrotateManager,
    OperatorManager,
    PeerTLSManager,
    S3BackupManager,
    SelfHealingManager,
)
from ...services import (
    LogrotateService,
    SelfHealingService,
)
from ...workload import (
    ContainerPaths,
    ContainerRuntime,
    K8sExporterService,
    K8sServerService,
    K8sSystem,
)
from ..architecture import check_architecture
from ..config import CharmConfig
from ..refresh import K8sRefreshHandler
from .base import BaseCharm

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class K8sCharm(BaseCharm):
    """Class to wrap all the operator logic."""

    config_type = CharmConfig

    def __init__(self, *args):
        """Initialize the class."""
        super().__init__(*args)
        check_architecture()

        container = self.unit.get_container("mysql")
        container_root = ContainerPath("/", container=container)
        container_paths = ContainerPaths(container_root)
        container_runtime = ContainerRuntime(
            namespace=self.model.name,
            pod_name=self.get_unit_label(self.unit),
            container_name="mysql",
        )

        self._system = K8sSystem(
            paths=container_paths,
            runtime=container_runtime,
            container=container,
        )

        self._service_exporter = K8sExporterService(self._system, container)
        self._service_server = K8sServerService(self._system, container)

        self._clients = self._build_mysql_clients(self._build_executor())
        self._helpers = EventHelpers(self, self._clients)

        self._state = self._build_state()
        self._refresh = self._build_refresh()

        self._handler_backup = BackupS3EventHandler(
            charm=self,
            helpers=self._helpers,
            manager=S3BackupManager(self._state, self._system, self._clients),
        )
        self._handler_database = DatabaseEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=DatabaseManager(self._state, self._system, self._clients),
        )
        self._handler_lifecycle = LifecycleEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=LifecycleManager(self._state, self._system, self._clients),
        )
        self._handler_log_rotation = LogRotationEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=LogrotateManager(self._state, self._system, self._clients),
            service=LogrotateService(self._state, self._system),
            relation="logging",
        )
        self._handler_operator = OperatorEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=OperatorManager(self._state, self._system, self._clients),
        )
        self._handler_self_healing = SelfHealingEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=SelfHealingManager(self._state, self._system, self._clients),
            service=SelfHealingService(self._state, self._system),
        )
        self._handler_tls_client = TLSClientEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=ClientTLSManager(self._state, self._system, self._clients),
        )
        self._handler_tls_peer = TLSPeerEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=PeerTLSManager(self._state, self._system, self._clients),
        )

        # Refresh object must be instantiated after the handlers
        self._refresh = self._build_refresh()

    @property
    def database(self) -> DatabaseEventHandler:
        """Return the operator database handler."""
        return self._handler_database

    @property
    def refreshing(self) -> bool:
        """Return the operator refresh handler."""
        if not self._refresh:
            return True

        return self._refresh.in_progress

    @property
    def service_exporter(self) -> K8sExporterService:
        """Return the MySQL Exporter service."""
        return self._service_exporter

    @property
    def service_server(self) -> K8sServerService:
        """Return the MySQL Server service."""
        return self._service_server

    @property
    def system(self) -> K8sSystem:
        """Return the system."""
        return self._system

    @property
    def units(self) -> set[Unit]:
        """The peer-related units in the application."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return set()

        return {self.unit, *peers_relation.units}

    def _build_executor(self) -> PebbleExecutor:
        """Build a MySQL Shell executor."""
        shell_binary = self._system.paths.binary("mysqlsh")
        shell_details = self._build_mysql_connection()

        return PebbleExecutor(shell_details, str(shell_binary), timeout=120)

    def _build_refresh(self) -> charm_refresh.Kubernetes | None:
        """Builds the refresh object."""
        try:
            handler = K8sRefreshHandler(self, self._clients)
            refresh = charm_refresh.Kubernetes(handler)
        except charm_refresh.KubernetesJujuAppNotTrusted:
            refresh = None
        except charm_refresh.PeerRelationNotReady:
            refresh = None
        except charm_refresh.UnitTearingDown:
            refresh = None

        if refresh and refresh.workload_allowed_to_start:
            refresh.next_unit_allowed_to_refresh = True

        return refresh

    def _create_service(self, endpoint_role: EndpointRole) -> None:
        """Create a runtime service."""
        try:
            self._system.runtime.create_service(
                name=f"{self.app.name}-{endpoint_role}",
                labels={
                    "application-name": self.app.name,
                    "cluster-name": self.cluster_name,
                    "role": endpoint_role,
                },
            )
        except RuntimeError as e:
            logger.error(f"Failed to create runtime service: {e}")
            raise

    def _update_label(self, endpoint_role: EndpointRole, address: str) -> None:
        """Update the runtime label."""
        try:
            self._system.runtime.update_labels(
                name=address.split(".")[0],
                labels={
                    "application-name": self.app.name,
                    "cluster-name": self.cluster_name,
                    "role": endpoint_role,
                },
            )
        except RuntimeError as e:
            logger.error(f"Failed to update runtime labels: {e}")
            raise

    def build_database_endpoints(self) -> dict[EndpointRole, list]:
        """Build the dictionary of database endpoints."""
        primary_hostname = self._system.runtime.get_hostname(f"{self.app.name}-primary")
        replica_hostname = self._system.runtime.get_hostname(f"{self.app.name}-replicas")

        # Wait for the primary endpoint service to be ready
        self._system.runtime.check_service(primary_hostname, 3306)

        return {
            "primary": [f"{primary_hostname}:3306"],
            "replicas": [f"{replica_hostname}:3306"],
            "offline": [],
        }

    def get_unit_label(self, unit: Unit) -> str:
        """Get a unit label."""
        return unit.name.replace("/", "-")

    def get_unit_address(self, unit: Unit, relation: str = RELATION_PEERS) -> str:
        """Get a unit address."""
        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_delay(120),
            wait=tenacity.wait_fixed(2),
            reraise=True,
        ):
            with attempt:
                unit_label = self.get_unit_label(unit)
                unit_address = f"{unit_label}.{self.app.name}-endpoints"
                unit_hostname = self.system.runtime.get_hostname(unit_label)

                # DNS domain name should contain unit address. Example:
                # Address: mysql-k8s-0.mysql-k8s-endpoints
                # Totally propagated: mysql-k8s-0.mysql-k8s-endpoints.dev.svc.cluster.local
                # Partially propagated: 10-1-142-191.mysql-k8s.dev.svc.cluster.local
                if unit_address not in unit_hostname:
                    logger.warning("The unit address has not been populated yet")
                    raise ValueError("The unit address has not been populated yet")

                return unit_hostname

        raise RuntimeError("Failed to resolve unit address")

    def set_unit_address(self, unit: Unit, relation: str) -> None:
        """Set the unit address into the data-bag."""
        pass

    def create_app_services(self) -> bool:
        """Create a runtime service."""
        logger.info("Creating application services")

        try:
            self._create_service("primary")
            self._create_service("replicas")
        except RuntimeError as e:
            logger.error(f"Failed to create the application services: {e}")
            return False

        return True

    def update_app_labels(self) -> bool:
        """Update the runtime labels."""
        cluster_endpoints = self._helpers.build_cluster_endpoints(RELATION_DATABASE)

        logger.info("Updating application labels")
        for address in cluster_endpoints[0]:
            self._update_label("primary", address)
        for address in cluster_endpoints[1]:
            self._update_label("replicas", address)
        for address in cluster_endpoints[2]:
            self._update_label("offline", address)

        return True
