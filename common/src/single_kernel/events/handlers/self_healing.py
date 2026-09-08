# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from mysql_shell.models import ClusterStatus, InstanceState
from ops.framework import EventBase, Object
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

        if self._helpers.initialized:
            self._service.start(self._charm.unit.name, self._charm.charm_dir)

    def _collect_peer_addresses(self) -> list[str]:
        """Collect all peer unit addresses."""
        peer_addresses = []

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return peer_addresses

        for unit in peers_relation.units:
            peer_address = self._charm.get_unit_address(unit)
            peer_addresses.append(peer_address)

        return peer_addresses

    def _collect_peer_states(self) -> list[str]:
        """Collect all peer unit states."""
        peer_states = []

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return peer_states

        for unit in peers_relation.units:
            unit_state = PeerStateUnit(peers_relation.data[unit])
            peer_state = unit_state.get_instance_state()
            peer_states.append(peer_state)

        return peer_states

    def _rejoin_instance(self) -> None:
        """Rejoin the cluster member."""
        peer_addresses = self._collect_peer_addresses()
        if not peer_addresses:
            return

        instance_label = self._charm.get_unit_label(self._charm.unit)
        instance_host = self._charm.get_unit_address(self._charm.unit)

        self._manager.rejoin_instance(
            instance_label=instance_label,
            instance_host=instance_host,
            addrs=peer_addresses,
        )

    def _recover_from_online_leader(self) -> None:
        """Recover the cluster from an ONLINE leader.

        A surviving cluster member can stay ONLINE in its local view
        while the cluster has lost quorum (status is UNREACHABLE).
        """
        if not self._helpers.initialized:
            logger.debug("Skipping cluster self-healing: charm is not initialized")
            return

        if not self._manager.fetch_cluster_state() == ClusterStatus.NO_QUORUM:
            logger.debug("Skipping cluster self-healing: cluster has quorum")
            return

        try:
            self._manager.stop_replication()
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.error(f"Failed to recover cluster quorum: {e}")
            self._charm.unit.status = BlockedStatus("Unable to recover cluster")
        else:
            self._charm.unit.status = self._helpers.build_unit_status()
            self._charm.app.status = self._helpers.build_app_status()

    def _recover_from_online_follower(self) -> None:
        """Recover the cluster from an ONLINE follower."""
        if not self._helpers.initialized:
            logger.debug("Skipping cluster self-healing: charm is not initialized")
            return

        if not self._manager.fetch_cluster_state() == ClusterStatus.NO_QUORUM:
            logger.debug("Skipping cluster self-healing: cluster has quorum")
            return

        self._manager.stop_replication()
        self._charm.unit.status = self._helpers.build_unit_status()

    def _recover_from_offline_leader(self) -> None:
        """Recover the cluster from an OFFLINE leader."""
        if not self._helpers.initialized:
            logger.debug("Skipping cluster self-healing: charm is not initialized")
            return

        peer_states = self._collect_peer_states()
        peer_states = set(peer_states)

        if InstanceState.ONLINE in peer_states:
            self._rejoin_instance()
            return

        if not any((
            peer_states == set(),
            peer_states == {InstanceState.OFFLINE},
            peer_states == {"waiting"},
        )):
            return

        if self._manager.fetch_cluster_members() > 0:
            return

        try:
            self._manager.stop_replication()
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.warning(f"Failed to recover cluster quorum: {e}")
            self._manager.recreate_cluster(self._charm.get_unit_label(self._charm.unit))
        else:
            self._charm.unit.status = self._helpers.build_unit_status()
            self._charm.app.status = self._helpers.build_app_status()

    def _recover_from_offline_follower(self) -> None:
        """Recover the cluster from an OFFLINE follower."""
        if not self._helpers.initialized:
            logger.debug("Skipping cluster self-healing: charm is not initialized")
            return

        peer_states = self._collect_peer_states()
        peer_states = set(peer_states)

        if InstanceState.ONLINE in peer_states:
            self._rejoin_instance()
            return

    def _recover_from_unreachable_leader(self) -> None:
        """Recover the cluster from an UNREACHABLE leader."""
        self._charm.service_server.stop()
        self._charm.service_server.start()

    def _recover_from_unreachable_follower(self) -> None:
        """Recover the cluster from an UNREACHABLE follower."""
        self._charm.service_server.stop()
        self._charm.service_server.start()

    def _on_self_healing(self, _: SelfHealingEvent) -> None:
        """Event handler for the self-healing event."""
        if self._charm.refreshing:
            return

        state = self._manager.fetch_instance_state()
        leader = self._charm.unit.is_leader()

        match state, leader:
            case InstanceState.ONLINE, True:
                self._recover_from_online_leader()
            case InstanceState.ONLINE, False:
                self._recover_from_online_follower()
            case InstanceState.OFFLINE, True:
                self._recover_from_offline_leader()
            case InstanceState.OFFLINE, False:
                self._recover_from_offline_follower()
            case InstanceState.UNREACHABLE, True:
                self._recover_from_unreachable_leader()
            case InstanceState.UNREACHABLE, False:
                self._recover_from_unreachable_follower()

        self._manager.update_state()
        self._charm.update_app_labels()
