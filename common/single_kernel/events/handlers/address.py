# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import ConfigChangedEvent
from ops.framework import EventBase, EventSource, Object

from ...managers import AddressResolutionManager
from ...services import AddressResolutionService
from ..helpers import Helpers

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class IPAddressChangeEvent(EventBase):
    """Custom event to resolve IP address changes."""


class IPAddressEventHandler(Object):
    """Class to deal with the IP address events."""

    address_changed = EventSource(IPAddressChangeEvent)

    def __init__(
        self,
        charm: Operator,
        manager: AddressResolutionManager,
        service: AddressResolutionService,
        helpers: Helpers,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "ip-address")
        self._charm = charm
        self._manager = manager
        self._service = service
        self._helpers = helpers

        self.framework.observe(self._charm.on.config_changed, self._on_update_config)
        self.framework.observe(self._charm.on.address_changed, self._on_ip_address_change)

    def _update_hostnames(self) -> None:
        """Update the hostname details."""
        address = self._charm.get_unit_address(self._charm.unit)
        _______ = self._manager.update_details(address)

    def _on_update_config(self, _: ConfigChangedEvent) -> None:
        """Event handler for the config-changed event."""
        self._update_hostnames()

    def _on_ip_address_change(self, _: IPAddressChangeEvent) -> None:
        """Event handler for the address-changed event."""
        self._update_hostnames()
        self._charm._service_server.stop()
        self._charm._service_server.start()
