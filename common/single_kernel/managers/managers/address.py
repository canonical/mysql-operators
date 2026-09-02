# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import socket
from typing import Mapping, Sequence

from mysql_shell import ExecutionError

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients

logger = logging.getLogger(__name__)


class AddressResolutionManager:
    """Class to deal with the address-resolution operations."""

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def update_details(self, address: str) -> None:
        """Update the hostname details for the given address."""
        details = {
            "address": address,
            "names": [
                socket.gethostname(),
                socket.getfqdn(),
            ],
        }

        self._state.unit.set_hostname_details(details)

    def update_hosts(self, addresses: Sequence[str], names: Mapping[str, list]) -> None:
        """Update hosts."""
        logger.debug("Updating address hosts")

        self._system.runtime.remove_hosts()
        for address in addresses:
            self._system.runtime.update_hosts(address, names[address])

        try:
            self._clients.instance.flush_host_cache()
        except ExecutionError as e:
            logger.warning(f"Failed to flush MySQL host cache: {e}")
