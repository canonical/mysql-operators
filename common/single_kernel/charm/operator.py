# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from charmlibs.pathops import LocalPath
from charmlibs.rollingops import RollingOpsManager
from mysql_shell.executors import BaseExecutor, LocalExecutor
from mysql_shell.models import ConnectionDetails
from mysql_shell_contrib.executors import PebbleExecutor
from ops.model import StatusBase, Unit

from ..core import RELATION_OPS, RELATION_PEERS, Substrate
from ..workload import BaseSystem
from .base import TypedCharmBase
from .config import CharmConfig


class Operator(TypedCharmBase[CharmConfig]):
    """Class to encapsulate all operator logic."""

    def __init__(self, substrate: Substrate, *args, **kwargs):
        """Initialize the class attributes."""
        super().__init__(*args, **kwargs)
        self._substrate = substrate

        self._manager_operator = None
        self._service_exporter = None
        self._service_server = None

    @property
    def initialized(self) -> bool:
        """Return whether the operator is initialized."""
        return all((
            self._manager_operator.cluster_initialized,
            self._service_exporter.running,
            self._service_server.running,
        ))

    @property
    def callback_manager(self) -> RollingOpsManager:
        """Return the callback manager."""
        return RollingOpsManager(
            charm=self,
            base_dir=LocalPath("/var/lib/juju/rollingops"),
            peer_relation_name=RELATION_OPS,
            callback_targets={
                "replication": "",
                "restart": "",
            },
        )

    @property
    def system(self) -> BaseSystem:
        """Return the system."""
        pass

    @property
    def units(self) -> set[Unit]:
        """The peer-related units in the application."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return set()

        return {self.unit, *peers_relation.units}

    @property
    def unit_departing(self) -> bool:
        """Return whether the unit is departing."""
        return self._manager_operator.get_instance_teardown()

    def build_app_status(self) -> StatusBase:
        """Build app status."""
        pass

    def build_unit_status(self) -> StatusBase:
        """Build unit status."""
        pass

    def build_executor(self, username: str, password: str, host: str, port: str) -> BaseExecutor:
        """Build a MySQL Shell executor."""
        shell_binary = self.system.paths.binary("mysqlsh")
        conn_details = ConnectionDetails(
            username=username,
            password=password,
            host=host,
            port=port,
        )

        match self._substrate:
            case Substrate.K8s:
                return PebbleExecutor(conn_details, str(shell_binary), timeout=120)
            case Substrate.VM:
                return LocalExecutor(conn_details, str(shell_binary), timeout=120)
            case _:
                raise ValueError("Unknown substrate")

    def get_unit_address(self, unit: Unit) -> str:
        """Get a unit address."""
        pass

    def get_unit_label(self, unit: Unit) -> str:
        """Get a unit label."""
        return unit.name.replace("/", "-")

    def set_unit_status(self, status: StatusBase) -> None:
        """Set the unit status."""
        self.unit.status = status
