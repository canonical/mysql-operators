# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod

from ...clients import MySQLClusterClient, MySQLClusterSetClient, MySQLInstanceClient
from ...state import ReplicationState
from ...workload import BaseSystem
from .replication_status import ReplicationStatus


class BaseReplicationManager(ABC):
    """Abstract class to deal with the MySQL server replication."""

    def __init__(
        self,
        state_local: ReplicationState,
        state_remote: ReplicationState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        cluster_set_client: MySQLClusterSetClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state_local = state_local
        self._state_remote = state_remote
        self._system = system

        self._cluster_client = cluster_client
        self._cluster_set_client = cluster_set_client
        self._instance_client = instance_client

    @abstractmethod
    def get_status(self, target_members: int) -> ReplicationStatus:
        """Return the status of the replication relation."""
        raise NotImplementedError()

    def get_ready_flag(self) -> bool | None:
        """Get the cluster ready flag."""
        return self._state_local.get_ready_flag()

    def set_ready_flag(self, flag: bool) -> None:
        """Set the cluster ready flag."""
        return self._state_local.set_ready_flag(flag)

    def delete_ready_flag(self) -> None:
        """Delete the cluster ready flag."""
        return self._state_local.delete_ready_flag()
