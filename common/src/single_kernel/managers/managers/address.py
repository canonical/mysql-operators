# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from mysql_shell.executors.errors import ExecutionError

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients
from ..models import MachineHost

logger = logging.getLogger(__name__)


class AddressResolutionManager:
    """Class to deal with the address-resolution operations."""

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    def set_hostname(self, host: MachineHost) -> None:
        """Update the databag host details."""
        self._state.unit.set_address_hostname(host.into_dict())

    def cleanup_hosts(self) -> None:
        """Cleanup the machine host list."""
        logger.debug("Cleaning /etc/hosts")
        self._system.runtime.remove_hosts()

    def update_hosts(self, hosts: list[MachineHost]) -> None:
        """Update the machine host list."""
        logger.debug("Updating /etc/hosts")

        for host in hosts:
            self._system.runtime.update_hosts(
                address=host.address,
                names=host.names,
            )

        try:
            self._clients.instance.flush_host_cache()
        except ExecutionError as e:
            logger.warning(f"Failed to flush MySQL host cache: {e}")
