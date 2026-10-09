# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from charmlibs.pathops import LocalPath
from charmlibs.rollingops import OperationResult, RollingOpsManager
from ops.model import Relation

from ....core import RELATION_OPS, RELATION_PEERS
from ....managers import RollingManager

if typing.TYPE_CHECKING:
    from ....charm import BaseCharm

logger = logging.getLogger(__name__)


class RollingHelper:
    """Class to deal with the rolling operations."""

    cluster_callback = "replication"
    instance_callback = "restart"

    def __init__(self, charm: BaseCharm, manager: RollingManager):
        """Initialize the class attributes."""
        self._charm = charm
        self._manager = manager

        self._callbacks = RollingOpsManager(
            charm=charm,
            base_dir=LocalPath("/var/lib/juju/rollingops"),
            peer_relation_name=RELATION_OPS,
            callback_targets={
                self.cluster_callback: self.restart_cluster,
                self.instance_callback: self.restart_instance,
            },
        )

    @property
    def callbacks(self) -> RollingOpsManager:
        """Return the rolling callback manager."""
        return self._callbacks

    def _check_cluster_waiting_ops(self, relation: Relation) -> bool:
        """Check whether there are cluster-level waiting operations."""
        for unit in relation.units:
            if self._callbacks.is_waiting_callback(self.cluster_callback, unit.name):
                return True

        return False

    def _check_instance_waiting_ops(self, relation: Relation) -> bool:
        """Check whether there are instance-level waiting operations."""
        for unit in relation.units:
            if self._callbacks.is_waiting_callback(self.instance_callback, unit.name):
                return True

        return False

    def _recover_instance(self) -> None:
        """Recover the instance after a restart."""
        logger.info("Recovering instance")

        if self._charm.app.planned_units() == 1:
            self._manager.recover_cluster()
            return

        self._manager.recover_instance(self._charm.get_unit_label(self._charm.unit))

    def _restart_instance(self) -> None:
        """Restart the instance."""
        logger.info("Restarting instance")
        self._charm.service_server.stop()
        self._charm.service_server.start()

    def restart_cluster(self) -> OperationResult:
        """Restart the cluster replication."""
        if not self._charm.service_server.running:
            logger.debug("Skipping replication restart: server is not running")
            return OperationResult.RETRY_RELEASE

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.debug("Skipping replication restart: relation missing")
            return OperationResult.RETRY_RELEASE

        if self._manager.is_cluster_primary and self._check_cluster_waiting_ops(peers_relation):
            logger.debug("Skipping replication restart: there are waiting ops")
            return OperationResult.RETRY_RELEASE

        # NOTE:
        # This method used to contain a preemptive switch-over to any other application unit
        # guarded by an `self._charm.app.planned_units() > 1` clause in this specific spot.
        # However, recent reports show race conditions around scale up / down scenarios,
        # therefore we decided to remove it in Charmed MySQL 8.0.

        logger.info("Restarting replication")
        self._manager.restart_instance_replication(
            instance_label=self._charm.get_unit_label(self._charm.unit),
            instance_host=self._charm.get_unit_address(self._charm.unit),
        )

        return OperationResult.RELEASE

    def restart_instance(self) -> OperationResult:
        """Restart the instance."""
        if not self._charm.service_server.running:
            logger.debug("Skipping replication restart: server is not running")
            return OperationResult.RETRY_RELEASE

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            logger.debug("Skipping instance restart: relation missing")
            return OperationResult.RETRY_RELEASE

        if self._manager.is_cluster_primary and self._check_instance_waiting_ops(peers_relation):
            logger.debug("Skipping instance restart: there ware waiting ops")
            return OperationResult.RETRY_RELEASE

        # NOTE:
        # This method used to contain a preemptive switch-over to any other application unit
        # guarded by an `self._charm.app.planned_units() > 1` clause in this specific spot.
        # However, recent reports show race conditions around scale up / down scenarios,
        # therefore we decided to remove it in Charmed MySQL 8.0.

        self._restart_instance()
        self._recover_instance()
        return OperationResult.RELEASE
