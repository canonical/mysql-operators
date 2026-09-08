# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from mysql_shell.models import ClusterStatus, InstanceState
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus

from ...core import RELATION_DATABASE, RELATION_PEERS, ServiceRole
from ...managers import SelfHealingManager
from ...services import SelfHealingService
from ...state import LifecycleState
from ..helpers import Helpers

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class SelfHealingEvent(EventBase):
    """Custom event to heal the MySQL cluster."""


class SelfHealingEventHandler(Object):
    """Class to deal with the self-healing events."""

    self_healing = EventSource(SelfHealingEvent)

    def __init__(
        self,
        charm: Operator,
        manager: SelfHealingManager,
        service: SelfHealingService,
        helpers: Helpers,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "self-healing")
        self._charm = charm
        self._manager = manager
        self._service = service
        self._helpers = helpers

        self.framework.observe(self._charm.on.self_healing, self._on_self_healing)

    def _collect_peer_states(self) -> list[str] | None:
        """Collect all peer unit states."""
        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return None

        peer_states = []
        for unit in peers_relation.units:
            unit_state = LifecycleState(self._charm.model, peers_relation, unit)
            peer_state = unit_state.get_instance_state() or "UNKNOWN"
            peer_states.append(peer_state)

        return peer_states

    def _recover_online_instance(self) -> None:
        """Recover the cluster from an ONLINE instance.

        A surviving cluster member can stay ONLINE in its local view
        while the cluster has lost quorum (status is UNREACHABLE).
        """
        if not self._manager.fetch_cluster_state() == ClusterStatus.NO_QUORUM:
            return
        if not self._charm.unit.is_leader():
            return

        try:
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.error(f"Failed to recover cluster quorum: {e}")
            self._charm.set_unit_status(BlockedStatus("Unable to recover cluster"))

    def _recover_offline_instance(self) -> None:
        """Recover the cluster from an OFFLINE instance."""
        peer_states = self._collect_peer_states()
        if not peer_states:
            return

        if set(peer_states) != {InstanceState.ONLINE}:
            return

        try:
            self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.error(f"Failed to recover cluster quorum: {e}")
            self._charm.set_unit_status(BlockedStatus("Unable to recover cluster"))

    def _recover_waiting_instance(self) -> None:
        """Recover the cluster from a WAITING instance."""
        peer_states = self._collect_peer_states()
        if not peer_states:
            return

        if set(peer_states) != {"waiting"}:
            return

        try:
            return self._manager.recover_cluster_quorum()
        except RuntimeError as e:
            logger.warning(f"Failed to recover cluster quorum: {e}")

        if set(peer_states) == {"waiting"}:
            self._manager.recreate_cluster(self._charm.get_unit_label(self._charm.unit))
            self._charm.set_unit_status(self._charm.build_app_status())
        else:
            self._charm.set_unit_status(BlockedStatus("Failed to recover cluster"))

    def _recover_unreachable_instance(self) -> None:
        """Recover the cluster from an UNREACHABLE instance."""
        self._charm.set_unit_status(BlockedStatus("Unable to recover cluster"))

    def _update_service(self, service_role: ServiceRole, endpoints: list[str]) -> None:
        """Update a runtime service labels."""
        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return None

        unit_state = LifecycleState(self._charm.model, peers_relation, self._charm.unit)
        unit_cluster = f"{unit_state.get_cluster_name()}"

        self._manager.update_labels(
            addresses=endpoints,
            labels={
                "application-name": self._charm.app.name,
                "cluster-name": unit_cluster,
                "role": service_role,
            },
        )

    def _on_self_healing(self, _: SelfHealingEvent) -> None:
        """Event handler for the self-healing event."""
        state = self._manager.fetch_instance_state()

        match state:
            case InstanceState.ONLINE:
                self._recover_online_instance()
            case InstanceState.OFFLINE:
                self._recover_offline_instance()
            case InstanceState.UNREACHABLE:
                self._recover_unreachable_instance()
            case "waiting":
                self._recover_waiting_instance()

        if not self._charm.model.get_relation(RELATION_DATABASE):
            logger.warning(f"Skipping service update: missing {RELATION_DATABASE} relation")
            return

        endpoints = self._helpers.build_cluster_endpoints(RELATION_DATABASE)

        logger.debug("Updating service labels")
        self._update_service("primary", endpoints[0])
        self._update_service("replicas", endpoints[1])
        self._update_service("offline", endpoints[2])
