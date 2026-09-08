# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import ConfigChangedEvent
from ops.framework import EventBase, EventSource, Object

from ...core import RELATION_PEERS
from ...managers import AddressResolutionManager
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

    address_changed = EventSource(AddressChangeEvent)

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

        self.framework.observe(self._charm.on.config_changed, self._on_update_config)
        self.framework.observe(self._charm.on.address_changed, self._on_ip_address_change)

        # TODO: add database-peers relation-changed handler

    def _collect_peer_hostnames(self) -> list[dict]:
        """Collect all peer unit hostnames."""
        peer_hostnames = []

        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return peer_hostnames

        for unit in peers_relation.units:
            unit_state = PeerStateUnit(peers_relation.data[unit])
            if peer_hostname := unit_state.get_hostname_details():
                peer_hostnames.append(peer_hostname)

        return peer_hostnames

    def _update_hostnames(self) -> None:
        """Update the hostname details."""
        address = self._charm.get_unit_address(self._charm.unit)
        _______ = self._manager.update_details(address)

    def _on_update_config(self, _: ConfigChangedEvent) -> None:
        """Event handler for the config-changed event."""
        self._update_hostnames()

    def _on_ip_address_change(self, _: AddressChangeEvent) -> None:
        """Event handler for the address-changed event."""
        self._update_hostnames()
        self._charm.service_server.stop()
        self._charm.service_server.start()
