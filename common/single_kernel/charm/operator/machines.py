# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import importlib
import logging

import charm_refresh
import ops_tracing
import tenacity
from charmlibs.pathops import LocalPath
from mysql_shell.executors import LocalExecutor
from ops.model import Unit

from ... import resources
from ...core import (
    RELATION_DATABASE,
    RELATION_PEERS,
    RELATION_TRACING,
    EndpointRole,
)
from ...events.handlers import (
    AddressEventHandler,
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
from ...libs import COSAgentProvider
from ...managers.managers import (
    AddressResolutionManager,
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
    AddressResolutionService,
    LogrotateService,
    SelfHealingService,
)
from ...state import PeerStateUnit
from ...workload import (
    MachinePaths,
    MachineRuntime,
    VMExporterService,
    VMServerService,
    VMSystem,
)
from ..architecture import check_architecture
from ..config import CharmConfig
from ..refresh import VMRefreshHandler
from .base import BaseCharm

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class VMCharm(BaseCharm):
    """Class to wrap all the operator logic."""

    config_type = CharmConfig

    def __init__(self, *args):
        """Initialize the class."""
        super().__init__(*args)
        check_architecture()

        machine_root = LocalPath("/")
        machine_paths = MachinePaths(machine_root, "charmed-mysql")
        machine_runtime = MachineRuntime()

        self._system = VMSystem(
            paths=machine_paths,
            runtime=machine_runtime,
        )

        self._service_exporter = VMExporterService(self._system)
        self._service_server = VMServerService(self._system)

        self._state = self._build_state()
        self._clients = self._build_mysql_clients(self._build_executor())
        self._helpers = EventHelpers(self, self._clients)

        # The IP Address event handler is VM specific
        self._handler_address = AddressEventHandler(
            charm=self,
            helpers=self._helpers,
            manager=AddressResolutionManager(self._state, self._system, self._clients),
            service=AddressResolutionService(self._state, self._system),
        )
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
            relation="cos-agent",
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

        # Observability objects must be instantiated at the end
        self._cos_agent = self._build_cos_agent()
        self._cos_traces = self._build_cos_traces()

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
    def service_exporter(self) -> VMExporterService:
        """Return the MySQL Exporter service."""
        return self._service_exporter

    @property
    def service_server(self) -> VMServerService:
        """Return the MySQL Server service."""
        return self._service_server

    @property
    def system(self) -> VMSystem:
        """Return the system."""
        return self._system

    @property
    def units(self) -> set[Unit]:
        """The peer-related units in the application."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return set()

        return {self.unit, *peers_relation.units}

    def _build_executor(self) -> LocalExecutor:
        """Build a MySQL Shell executor."""
        shell_binary = self._system.paths.binary("mysqlsh")
        shell_details = self._build_mysql_connection()

        return LocalExecutor(shell_details, str(shell_binary), timeout=120)

    def _build_cos_agent(self) -> COSAgentProvider:
        """Builds the COS agent object."""
        resources_dir = importlib.resources.files(resources)
        prom_rules = resources_dir / "observability" / "prometheus_rules"
        loki_rules = resources_dir / "observability" / "loki_rules"

        return COSAgentProvider(
            self,
            metrics_endpoints=[{"path": "/metrics", "port": 9104}],
            metrics_rules_dir=prom_rules,
            logs_rules_dir=loki_rules,
            tracing_protocols=["otlp_http"],
        )

    def _build_cos_traces(self) -> ops_tracing.Tracing:
        """Builds the COS tracing object."""
        tracing = ops_tracing.Tracing(self, tracing_relation_name=RELATION_TRACING)

        if not self._cos_agent.is_ready():
            logger.debug("Observability agent is not ready yet")
            return tracing

        endpoint = self._cos_agent.get_tracing_endpoint("otlp_http")
        if endpoint.startswith("https://"):
            logger.warning("Observability agent does not support sending traces over HTTPS")
            return tracing

        ops_tracing.set_destination(f"{endpoint}/v1/traces", None)
        return tracing

    def _build_refresh(self) -> charm_refresh.Machines | None:
        """Builds the refresh object."""
        try:
            handler = VMRefreshHandler(self, self._clients)
            refresh = charm_refresh.Machines(handler)
        except charm_refresh.PeerRelationNotReady:
            refresh = None
        except charm_refresh.UnitTearingDown:
            refresh = None

        if refresh and refresh.workload_allowed_to_start:
            refresh.next_unit_allowed_to_refresh = True

        return refresh

    def build_database_endpoints(self) -> dict[EndpointRole, list]:
        """Build the dictionary of database endpoints."""
        cluster_endpoints = self._helpers.build_cluster_endpoints(RELATION_DATABASE)

        return {
            "primary": cluster_endpoints[0],
            "replicas": cluster_endpoints[1],
            "offline": cluster_endpoints[2],
        }

    def get_unit_label(self, unit: Unit) -> str:
        """Get a unit label."""
        return unit.name.replace("/", "-")

    def get_unit_address(self, unit: Unit, relation: str = RELATION_PEERS) -> str:
        """Get a unit address."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.debug(f"Skipping address resolution: missing {RELATION_PEERS} relation")
            return ""

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_delay(120),
            wait=tenacity.wait_fixed(2),
            reraise=True,
        ):
            with attempt:
                unit_state = PeerStateUnit(peers_relation.data[unit])
                unit_address = unit_state.get_unit_address(relation)
                if not unit_address:
                    logger.warning("The unit address has not been populated yet")
                    raise ValueError("The unit address has not been populated yet")

                return unit_address

        raise RuntimeError("Failed to resolve unit address")

    def set_unit_address(self, unit: Unit, relation: str) -> None:
        """Set the unit address into the data-bag."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.debug(f"Skipping address saving: missing {RELATION_PEERS} relation")
            return

        address = self.model.get_binding(relation).network.bind_address
        state = PeerStateUnit(peers_relation.data[unit])
        state.set_unit_address(relation, str(address))

    def create_app_services(self) -> bool:
        """Create the runtime services."""
        pass

    def update_app_labels(self) -> bool:
        """Update the runtime labels."""
        pass
