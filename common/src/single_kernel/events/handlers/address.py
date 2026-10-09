# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import socket
import typing

from ops.charm import RelationEvent
from ops.framework import EventBase, Object

from ...core import RELATION_PEERS
from ...managers import AddressResolutionManager, MachineHost
from ...services import AddressResolutionService
from ...state import PeerStateUnit
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class AddressChangeEvent(EventBase):
    """Custom event to resolve IP address changes."""


class AddressEventHandler(Object):
    """Class to deal with the IP address events."""

    def __init__(
        self,
        charm: BaseCharm,
        helpers: EventHelpers,
        manager: AddressResolutionManager,
        service: AddressResolutionService,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "ip-address")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager
        self._service = service

        self.framework.observe(
            self._charm.on.address_changed,
            self._on_address_change,
        )
        self.framework.observe(
            self._charm.on[RELATION_PEERS].relation_joined,
            self._on_relation_event,
        )
        self.framework.observe(
            self._charm.on[RELATION_PEERS].relation_changed,
            self._on_relation_event,
        )
        self.framework.observe(
            self._charm.on[RELATION_PEERS].relation_departed,
            self._on_relation_event,
        )

        if self._helpers.initialized:
            self._service.start(self._charm.unit.name, self._charm.charm_dir)

    def _collect_peer_hostnames(self) -> list[dict]:
        """Collect all peer unit hostnames."""
        peer_hostnames = []

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return peer_hostnames

        for unit in peers_relation.units:
            unit_state = PeerStateUnit(peers_relation.data[unit])
            if peer_hostname := unit_state.get_address_hostname():
                peer_hostnames.append(peer_hostname)

        return peer_hostnames

    def _update_hostname(self) -> None:
        """Update the hostname details."""
        host = MachineHost(
            address=self._charm.get_unit_address(self._charm.unit),
            names=[
                socket.gethostname(),
                socket.getfqdn(),
            ],
        )

        self._manager.set_hostname(host)

    def _on_address_change(self, event: AddressChangeEvent) -> None:
        """Event handler for the address-changed event."""
        if not self._charm.system.ready:
            logger.debug("Deferring /etc/hosts update: system not ready")
            event.defer()
            return

        self._update_hostname()
        self._charm.service_server.stop()
        self._charm.service_server.start()

    def _on_relation_event(self, _: RelationEvent) -> None:
        """Event handler for any relation event.

        This is a work-around to quickly react upon topology changes when
        there is no good detection mechanism. It targets the situation when
        there are scale-up / scale-down operations and all units need to be notified.
        """
        if not self._charm.system.ready:
            logger.debug("Skipping /etc/hosts update: system not ready")
            return

        peer_hostnames = self._collect_peer_hostnames()
        if not peer_hostnames:
            logger.debug("Skipping /etc/hosts update: no hostname in peer databags")
            return

        self._manager.cleanup_hosts()
        self._manager.update_hosts([MachineHost.from_dict(host) for host in peer_hostnames])
