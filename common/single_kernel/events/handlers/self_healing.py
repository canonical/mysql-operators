# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from mysql_shell.models import ClusterStatus, InstanceState
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus

from ...core import RELATION_PEERS
from ...managers import SelfHealingManager
from ...services import SelfHealingService
from ...state import PeerStateUnit
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class SelfHealingEvent(EventBase):
    """Custom event to heal the MySQL cluster."""


class SelfHealingEventHandler(Object):
    """Class to deal with the self-healing events."""

    self_healing = EventSource(SelfHealingEvent)

    def __init__(
        self,
        charm: BaseCharm,
        helpers: EventHelpers,
        manager: SelfHealingManager,
        service: SelfHealingService,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "self-healing")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager
        self._service = service

        self.framework.observe(self._charm.on.self_healing, self._on_self_healing)

    def _collect_peer_states(self) -> list[str]:
        """Collect all peer unit states."""
        peer_states = []

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return peer_states

        for unit in peers_relation.units:
            unit_state = PeerStateUnit(peers_relation.data[unit])
            peer_state = unit_state.get_instance_state() or "UNKNOWN"
            peer_states.append(peer_state)

        return peer_states

    def _recover_from_online_instance(self) -> None:
        """Recover the cluster from an ONLINE instance.

        A surviving cluster member can stay ONLINE in its local view
        while the cluster has lost quorum (status is UNREACHABLE).
        """
        if not self._manager.fetch_cluster_state() == ClusterStatus.NO_QUORUM:
            return

        try:
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.error(f"Failed to recover cluster quorum: {e}")
            self._charm.unit.status = BlockedStatus("Unable to recover cluster")

    def _recover_from_offline_instance(self) -> None:
        """Recover the cluster from an OFFLINE instance."""
        peer_states = self._collect_peer_states()
        if not peer_states:
            return

        if not set(peer_states) == {InstanceState.OFFLINE}:
            return

        try:
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.error(f"Failed to recover cluster quorum: {e}")
            self._charm.unit.status = BlockedStatus("Unable to recover cluster")

    def _recover_from_waiting_instance(self) -> None:
        """Recover the cluster from a WAITING instance."""
        peer_states = self._collect_peer_states()
        if not peer_states:
            return

        if not set(peer_states) == {"waiting"}:
            return

        try:
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.warning(f"Failed to recover cluster quorum: {e}")
            self._manager.recreate_cluster(self._charm.get_unit_label(self._charm.unit))
            self._charm.unit.status = self._helpers.build_unit_status()
            self._charm.app.status = self._helpers.build_app_status()

    def _recover_from_unreachable_instance(self) -> None:
        """Recover the cluster from an UNREACHABLE instance."""
        self._charm.unit.status = BlockedStatus("Unable to recover cluster")

    def _on_self_healing(self, _: SelfHealingEvent) -> None:
        """Event handler for the self-healing event."""
        if not self._helpers.initialized:
            return
        if not self._charm.unit.is_leader():
            return
        if self._charm.refreshing:
            return

        _____ = self._manager.update_state()
        state = self._manager.fetch_instance_state()

        match state:
            case InstanceState.ONLINE:
                self._recover_from_online_instance()
            case InstanceState.OFFLINE:
                self._recover_from_offline_instance()
            case InstanceState.UNREACHABLE:
                self._recover_from_unreachable_instance()
            case "waiting":
                self._recover_from_waiting_instance()
