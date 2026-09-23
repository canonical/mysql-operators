# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from charm_refresh import CharmSpecificCommon, CharmVersion, PrecheckFailed
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceState

from ...managers import Clients

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class BaseRefreshHandler(CharmSpecificCommon):
    """Abstract class to deal with the operator refresh."""

    def __init__(self, charm: BaseCharm, clients: Clients):
        """Initialize the class attributes."""
        self._charm = charm
        self._clients = clients

    @classmethod
    def is_compatible(
        cls,
        *,
        old_charm_version: CharmVersion,
        new_charm_version: CharmVersion,
        old_workload_version: str,
        new_workload_version: str,
    ) -> bool:
        """Check charm and workload version compatibility."""
        if not super().is_compatible(
            old_charm_version=old_charm_version,
            new_charm_version=new_charm_version,
            old_workload_version=old_workload_version,
            new_workload_version=new_workload_version,
        ):
            return False

        # Check workload version compatibility
        old_major, old_minor = (int(component) for component in old_workload_version.split("."))
        new_major, new_minor = (int(component) for component in new_workload_version.split("."))

        return all((
            old_major == new_major,
            old_minor == new_minor,
        ))

    def _check_cluster(self) -> None:
        """Check the MySQL cluster health."""
        try:
            _________ = self._clients.cluster.rescan()
            instances = self._clients.cluster.fetch_instances()
        except ExecutionError as e:
            raise PrecheckFailed("Failed to check cluster health") from e

        for info in instances.values():
            if info["status"] != InstanceState.ONLINE:
                raise PrecheckFailed("Cluster instances are not online")

    def _prepare_cluster(self) -> None:
        """Prepare the MySQL cluster for an operator refresh."""
        instance_host = self._charm.get_unit_address(self._charm.unit)

        try:
            self._clients.promote_instance(instance_host, force=False)
        except ExecutionError as e:
            raise PrecheckFailed("Failed to prepare cluster") from e

    def _prepare_instance(self, instance_host: str) -> None:
        """Prepare the MySQL instance for an operator refresh."""
        with self._clients.build_instance_client(instance_host) as client:
            try:
                client.update_variable("innodb_fast_shutdown", 0)
            except ExecutionError as e:
                raise PrecheckFailed("Failed to prepare instance") from e

    @staticmethod
    def run_pre_refresh_checks_after_1_unit_refreshed() -> None:
        """Run the pre-refresh checks after the 1st unit is refreshed."""
        pass

    def run_pre_refresh_checks_before_any_units_refreshed(self) -> None:
        """Run the pre-refresh checks before any unit is refreshed."""
        logger.info("Running pre-refresh checks")

        self._check_cluster()
        self._prepare_cluster()

        for unit in self._charm.units:
            self._prepare_instance(self._charm.get_unit_address(unit))
