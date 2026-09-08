# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from mysql_shell.executors import BaseExecutor, LocalExecutor
from mysql_shell.models import ConnectionDetails
from mysql_shell_contrib.executors import PebbleExecutor
from ops.model import StatusBase, Unit

from ..core import RELATION_PEERS, Substrate
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
    def password_backup(self) -> str:
        """Return the backup user password."""
        pass

    @property
    def server_pool_size(self) -> int:
        """Return the server pool size."""
        pass

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

    def get_unit_address(self, unit: Unit, relation: str = RELATION_PEERS) -> str:
        """Get a unit address."""
        pass

    def get_unit_label(self, unit: Unit) -> str:
        """Get a unit label."""
        return unit.name.replace("/", "-")

    def set_unit_status(self, status: StatusBase) -> None:
        """Set the unit status."""
        self.unit.status = status
