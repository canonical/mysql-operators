# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from charmlibs.rollingops import OperationResult
from ops.framework import Object
from ops.model import MaintenanceStatus

from ..core import RELATION_PEERS
from ..managers import RollingOperationManager
from ..workload import BaseServerService

if typing.TYPE_CHECKING:
    from ..charm import Operator

logger = logging.getLogger(__name__)


class RollingOperationEventHandler(Object):
    """Class to deal with the rolling-operation events."""

    replication_callback = "replication"
    restart_callback = "restart"

    def __init__(
        self,
        charm: Operator,
        manager: RollingOperationManager,
        service: BaseServerService,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "rolling-ops")
        self._charm = charm
        self._manager = manager
        self._service = service

    def _recover_instance(self) -> None:
        """Recover the instance after a restart."""
        logger.info("Recovering instance")
        self._charm.set_unit_status(MaintenanceStatus("Recovering instance"))

        if self._charm.app.planned_units() == 1:
            self._manager.recover_cluster()
            return

        self._manager.recover_instance(self._charm.get_unit_label(self._charm.unit))

    def _restart_instance(self) -> None:
        """Restart the instance."""
        logger.info("Restarting instance")
        self._charm.set_unit_status(MaintenanceStatus("Restarting instance"))
        self._service.stop()
        self._service.start()

    def restart_cluster(self) -> OperationResult:
        """Restart the cluster replication."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.warning("Skipping replication restart")
            return OperationResult.RETRY_RELEASE

        ongoing_ops = [
            self._charm.callback_manager.is_waiting_callback(self.replication_callback, unit.name)
            for unit in peers_relation.units
        ]

        if self._manager.is_cluster_primary and any(ongoing_ops):
            logger.warning("Skipping replication restart")
            return OperationResult.RETRY_RELEASE

        if self._manager.is_cluster_primary and self._charm.app.planned_units() > 1:
            new_primary = self._charm.get_unit_address(peers_relation.units.pop())

            try:
                logger.debug(f"Promoting {new_primary} to primary")
                self._manager.prepare_cluster(new_primary)
            except RuntimeError as e:
                logger.error(f"Failed to promote {new_primary}: {e}")
                return OperationResult.RETRY_HOLD

        logger.info("Restarting replication")
        self._manager.restart_instance_replication(
            instance_label=self._charm.get_unit_label(self._charm.unit),
            instance_host=self._charm.get_unit_address(self._charm.unit),
        )

        return OperationResult.RELEASE

    def restart_instance(self) -> OperationResult:
        """Restart the instance."""
        peers_relation = self.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.warning("Skipping instance restart")
            return OperationResult.RETRY_RELEASE

        if not self._charm.initialized:
            logger.warning("Skipping instance restart")
            return OperationResult.RETRY_HOLD

        if self._manager.is_cluster_primary and self._charm.app.planned_units() > 1:
            new_primary = self._charm.get_unit_address(peers_relation.units.pop())

            try:
                logger.debug(f"Promoting {new_primary} to primary")
                self._manager.prepare_cluster(new_primary)
            except RuntimeError as e:
                logger.error(f"Failed to promote {new_primary}: {e}")
                return OperationResult.RETRY_HOLD

        self._restart_instance()
        self._recover_instance()
        return OperationResult.RELEASE
