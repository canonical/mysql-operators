# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from abc import ABC, abstractmethod
from typing import Generic, Type, TypeVar

from mysql_shell.executors import BaseExecutor
from mysql_shell.models import ConnectionDetails
from mysql_shell_contrib.builders import (
    CharmAuthorizationQueryBuilder,
    CharmLockingQueryBuilder,
    CharmLoggingQueryBuilder,
)
from ops.charm import CharmBase
from ops.model import Unit
from pydantic.main import BaseModel

from ...core import (
    PASSWORD_KEY_OPERATOR,
    RELATION_PEERS,
    ROLENAME_BACKUPS,
    ROLENAME_DBA,
    ROLENAME_DDL,
    ROLENAME_DML,
    ROLENAME_MONITOR,
    ROLENAME_READ,
    USERNAME_OPERATOR,
    EndpointRole,
)
from ...events import (
    DatabaseEventHandler,
)
from ...managers.clients import Clients
from ...managers.clients.mysql_server import (
    MySQLClusterClient,
    MySQLClusterSetClient,
    MySQLInstanceClient,
)
from ...state import (
    PeerState,
    PeerStateApp,
    PeerStateUnit,
)
from ...workload import (
    BaseExporterService,
    BaseServerService,
    BaseSystem,
)
from ..secrets import SecretStore

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseCharm(CharmBase, Generic[T], ABC):
    """Abstract class for the operator charms."""

    config_type: Type[T]

    @property
    @abstractmethod
    def database(self) -> DatabaseEventHandler:
        """Return the operator database handler."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def refreshing(self) -> bool:
        """Return the operator refresh handler."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def service_exporter(self) -> BaseExporterService:
        """Return the MySQL Exporter service."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def service_server(self) -> BaseServerService:
        """Return the MySQL Server service."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def system(self) -> BaseSystem:
        """Return the system."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def units(self) -> set[Unit]:
        """The peer-related units in the application."""
        raise NotImplementedError()

    @abstractmethod
    def build_database_endpoints(self) -> dict[EndpointRole, list]:
        """Build the dictionary of database endpoints."""
        raise NotImplementedError()

    @abstractmethod
    def get_unit_label(self, unit: Unit) -> str:
        """Get a unit label."""
        raise NotImplementedError()

    @abstractmethod
    def get_unit_address(self, unit: Unit, relation: str = RELATION_PEERS) -> str:
        """Get a unit address."""
        raise NotImplementedError()

    @abstractmethod
    def set_unit_address(self, unit: Unit, relation: str) -> None:
        """Set the unit address into the data-bag."""
        raise NotImplementedError()

    @abstractmethod
    def create_app_services(self) -> bool:
        """Create the runtime services."""
        raise NotImplementedError()

    @abstractmethod
    def update_app_labels(self) -> bool:
        """Update the runtime labels."""
        raise NotImplementedError()

    @property
    def cluster_name(self) -> str:
        """Return the cluster name."""
        state = self._build_state()
        name = state.app.get_cluster_name()
        if not name:
            logger.warning("Failed to fetch the cluster name: not yet available")
            return ""

        return name

    @property
    def cluster_set_name(self) -> str:
        """Return the cluster-set name."""
        state = self._build_state()
        name = state.app.get_cluster_set_name()
        if not name:
            logger.warning("Failed to fetch the cluster-set name: not yet available")
            return ""

        return name

    @property
    def config(self) -> T:
        """Return a config instance validated and parsed."""
        translated_keys = {k.replace("-", "_"): v for k, v in self.model.config.items()}
        return self.config_type(**translated_keys)

    @property
    def secret_label(self) -> str:
        """Return the secret label for the system passwords."""
        return f"{RELATION_PEERS}.{self.model.app.name}.app"

    @property
    def secret_store(self) -> SecretStore:
        """Return the secret store."""
        return SecretStore(self.model)

    def _build_mysql_connection(self) -> ConnectionDetails:
        """Build the MySQL Shell connection details."""
        try:
            username = USERNAME_OPERATOR
            password = self.secret_store.get_value(
                secret_label=self.secret_label,
                secret_key=PASSWORD_KEY_OPERATOR,
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to fetch executor credentials: {e}")
            username = ""
            password = ""

        return ConnectionDetails(
            username=username,
            password=password,
            host="127.0.0.1",
            port="330602",
        )

    def _build_mysql_clients(self, executor: BaseExecutor) -> Clients:
        """Build the MySQL Shell clients."""
        builder_logs = CharmLoggingQueryBuilder()
        builder_lock = CharmLockingQueryBuilder(
            table_schema="mysql",
            table_name="juju_units_operations",
        )
        builder_auth = CharmAuthorizationQueryBuilder(
            role_admin=ROLENAME_DBA,
            role_backup=ROLENAME_BACKUPS,
            role_ddl=ROLENAME_DDL,
            role_stats=ROLENAME_MONITOR,
            role_reader=ROLENAME_READ,
            role_writer=ROLENAME_DML,
        )

        instance_client = MySQLInstanceClient(
            executor=executor,
            builder_auth=builder_auth,
            builder_logs=builder_logs,
        )
        cluster_client = MySQLClusterClient(
            executor=executor,
            cluster_name=self.cluster_name,
            builder_lock=builder_lock,
        )
        cluster_set_client = MySQLClusterSetClient(
            executor=executor,
            cluster_set_name=self.cluster_set_name,
        )

        return Clients(instance_client, cluster_client, cluster_set_client)

    def _build_state(self) -> PeerState:
        """Build a peer relation state."""
        peer_relation = self.model.get_relation(RELATION_PEERS)

        if not peer_relation:
            app_data = {}
            unit_data = {}
        else:
            app_data = peer_relation.data[self.model.app]
            unit_data = peer_relation.data[self.model.unit]

        return PeerState(
            PeerStateApp(app_data),
            PeerStateUnit(unit_data),
        )
