# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ...state import AddressResolutionState
from ...workload import BaseSystem
from ..base import BaseOperatorService


class AddressResolutionService(BaseOperatorService):
    """Class to deal with the address-resolution service."""

    name = "IP address"

    def __init__(self, state: AddressResolutionState, system: BaseSystem):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

    @property
    def state(self) -> AddressResolutionState:
        """Return the relation state."""
        return self._state
