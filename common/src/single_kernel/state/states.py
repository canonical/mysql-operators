# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from .peers import PeerStateApp, PeerStateUnit
from .replication import ReplicationAppState


class PeerState:
    """Class to deal with the peer state."""

    def __init__(self, app_state: PeerStateApp, unit_state: PeerStateUnit):
        """Initialize the class attributes."""
        self._app_state = app_state
        self._unit_state = unit_state

    @property
    def app(self) -> PeerStateApp:
        """Return the app state."""
        return self._app_state

    @property
    def unit(self) -> PeerStateUnit:
        """Return the unit state."""
        return self._unit_state


class ReplicationState:
    """Class to deal with the replication state."""

    def __init__(self, app_state: ReplicationAppState):
        """Initialize the class attributes."""
        self._app_state = app_state

    @property
    def app(self) -> ReplicationAppState:
        """Return the app state."""
        return self._app_state
