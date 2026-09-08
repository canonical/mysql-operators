# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ...state import PeerState
from ...workload import BaseSystem
from ..base import BaseOperatorService


class AddressResolutionService(BaseOperatorService):
    """Class to deal with the address-resolution service."""

    name = "IP address"

    def __init__(self, state: PeerState, system: BaseSystem):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

    def get_process_id(self) -> int | None:
        """Get the address resolution process ID."""
        return self._state.unit.get_address_pid()

    def set_process_id(self, pid: int) -> None:
        """Set the address resolution process ID."""
        self._state.unit.set_address_pid(pid)

    def delete_process_id(self) -> None:
        """Delete the address resolution process ID."""
        self._state.unit.delete_address_pid()
