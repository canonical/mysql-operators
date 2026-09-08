# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ...state import SelfHealingState
from ...workload import BaseSystem
from ..base import BaseOperatorService


class SelfHealingService(BaseOperatorService):
    """Class to deal with the self-healing service."""

    name = "self-healing"

    def __init__(self, state: SelfHealingState, system: BaseSystem):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

    @property
    def state(self) -> SelfHealingState:
        """Return the relation state."""
        return self._state
