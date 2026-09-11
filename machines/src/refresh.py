# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Refresh logic for MySQL charm."""

import dataclasses
import logging
import typing

import charm_refresh
from charms.mysql.v0.mysql import (
    InstanceState,
    MySQLRescanClusterError,
    MySQLSetClusterPrimaryError,
    MySQLSetVariableError,
)
from ops import MaintenanceStatus

from constants import PEER
from mysql_vm_helpers import MySQL

if typing.TYPE_CHECKING:
    from charm import MySQLOperatorCharm

logger = logging.getLogger(__name__)


@dataclasses.dataclass(eq=False)
class MachinesMySQLRefresh(charm_refresh.CharmSpecificMachines):
    """Base class for MySQL refresh operations."""

    _charm: "MySQLOperatorCharm"

    @classmethod
    def is_compatible(
        cls,
        *,
        old_charm_version: charm_refresh.CharmVersion,
        new_charm_version: charm_refresh.CharmVersion,
        old_workload_version: str,
        new_workload_version: str,
    ) -> bool:
        """Checks charm and workload version compatibility."""
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

    @property
    def highest_ordinal(self) -> int:
        """Return the max ordinal."""
        return self._charm.app.planned_units() - 1

    @staticmethod
    def run_pre_refresh_checks_after_1_unit_refreshed() -> None:
        """Implement pre-refresh checks after 1 unit refreshed."""
        pass

    def run_pre_refresh_checks_before_any_units_refreshed(self) -> None:
        """Implement pre-refresh checks before any unit is refreshed."""
        logger.debug("Running pre-refresh checks")

        try:
            self._charm._mysql.rescan_cluster()
        except MySQLRescanClusterError as e:
            raise charm_refresh.PrecheckFailed("Failed to rescan cluster") from e

        status = self._charm._mysql.get_cluster_status(extended=True)
        if not status:
            raise charm_refresh.PrecheckFailed("Failed to retrieve cluster status")

        num_online = self._charm._mysql.get_cluster_node_count(node_status=InstanceState.ONLINE)
        if num_online < self._charm.app.planned_units():
            raise charm_refresh.PrecheckFailed("Not all units are online")

        try:
            # Set the primary to the first unit for switchover mitigation
            if self._charm._mysql.get_primary_label() != self._charm.unit_label:
                self._charm._mysql.set_cluster_primary(self._charm.unit_address)
        except MySQLSetClusterPrimaryError as e:
            raise charm_refresh.PrecheckFailed("Failed to set primary") from e

        try:
            # Set slow shutdown on all instances
            for unit in self._charm.app_units:
                self._charm._mysql.set_dynamic_variable(
                    instance_address=self._charm.get_unit_address(unit, PEER),
                    variable="innodb_fast_shutdown",
                    value=0,
                )
        except MySQLSetVariableError as e:
            raise charm_refresh.PrecheckFailed("Failed to set slow shutdown") from e

    def refresh_snap(
        self,
        *,
        snap_name: str,
        snap_revision: str,
        refresh: charm_refresh.Machines,
    ) -> None:
        """Refreshes the installed snap."""
        # TODO add graceful shutdown before refreshing snap?
        # TODO: Future improvement
        # If snap refresh fails (i.e. same snap revision installed) after graceful shutdown, restart workload

        self._charm.set_unit_status(MaintenanceStatus("refreshing the snap"), refresh=refresh)
        MySQL.install_and_configure_mysql_dependencies(revision=snap_revision)
        # Must be called immediately after the snap is refreshed, otherwise
        # `next_unit_allowed_to_refresh = True` raises. The workload is started & rejoined
        # to the cluster by `MySQLOperatorCharm._post_snap_refresh`.
        refresh.update_snap_revision()
