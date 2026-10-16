# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod

from ....state import PeerState, ReplicationState
from ....workload import BaseSystem
from ...clients import Clients
from .replication_status import ReplicationStatus


class BaseReplicationManager(ABC):
    """Abstract class to deal with the MySQL server async replication."""

    def __init__(
        self,
        repl_state_local: ReplicationState,
        repl_state_remote: ReplicationState,
        peer_state: PeerState,
        system: BaseSystem,
        clients: Clients,
    ):
        """Initialize the class attributes."""
        self._state_local = repl_state_local
        self._state_remote = repl_state_remote
        self._peer_state = peer_state
        self._system = system
        self._clients = clients

    @abstractmethod
    def get_status(self, target_members: int = 0) -> ReplicationStatus:
        """Return the current status of the replication relation."""
        raise NotImplementedError()

    def get_ready_flag(self) -> bool | None:
        """Return the local replication-ready flag."""
        return self._state_local.app.get_replication_ready_flag()

    def set_ready_flag(self, flag: bool) -> None:
        """Set the local replication-ready flag."""
        self._state_local.app.set_replication_ready_flag(flag)

    def delete_ready_flag(self) -> None:
        """Delete the local replication-ready flag."""
        self._state_local.app.delete_replication_ready_flag()
