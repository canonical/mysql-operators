# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ...state import PeerState
from ...workload import BaseSystem
from ..base import BaseOperatorService


class SelfHealingService(BaseOperatorService):
    """Class to deal with the self-healing service."""

    name = "self-healing"

    def __init__(self, state: PeerState, system: BaseSystem):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

    def get_process_id(self) -> int | None:
        """Get the self-healing process ID."""
        return self._state.unit.get_self_healing_pid()

    def set_process_id(self, pid: int) -> None:
        """Set the self-healing process ID."""
        self._state.unit.set_self_healing_pid(pid)

    def delete_process_id(self) -> None:
        """Delete the self-healing process ID."""
        self._state.unit.delete_self_healing_pid()
