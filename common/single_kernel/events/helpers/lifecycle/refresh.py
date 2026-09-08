# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from charm_refresh import CharmSpecificCommon, CharmVersion

from ....managers import RefreshManager

if typing.TYPE_CHECKING:
    from ....charm import Operator

logger = logging.getLogger(__name__)


class RefreshHelper(CharmSpecificCommon):
    """Class to deal with the operator refresh."""

    def __init__(self, charm: Operator, manager: RefreshManager):
        """Initialize the class attributes."""
        self._charm = charm
        self._manager = manager

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

    @staticmethod
    def run_pre_refresh_checks_after_1_unit_refreshed() -> None:
        """Run the pre-refresh checks after the 1st unit is refreshed."""
        pass

    def run_pre_refresh_checks_before_any_units_refreshed(self) -> None:
        """Run the pre-refresh checks before any unit is refreshed."""
        logger.info("Running pre-refresh checks")

        self._manager.check_cluster()

        # Set the primary to the first unit for switchover mitigation
        if not self._manager.is_cluster_primary:
            self._manager.prepare_cluster(self._charm.get_unit_label(self._charm.unit))

        for unit in self._charm.units:
            self._manager.prepare_instance(self._charm.get_unit_address(unit))
