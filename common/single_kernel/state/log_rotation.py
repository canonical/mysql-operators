# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Relation, Unit

from .secrets import BaseSecretStore


class LogRotationState:
    """Class to deal with the log-rotation state."""

    manager_pid_key = "log-rotate-manager-pid"
    synchronization_key = "logs_synced"

    def __init__(self, store: BaseSecretStore, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._store = store
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def store(self) -> BaseSecretStore:
        """Return the secrets store."""
        return self._store

    def get_manager_pid(self) -> int | None:
        """Return the log-rotation manager process ID."""
        manager_pid = self._relation_data.get(self.manager_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def get_sync_flag(self) -> bool | None:
        """Return the log-rotation synchronization flag."""
        flag = self._relation_data.get(self.synchronization_key)
        if not flag:
            return None

        return flag == "true"

    def set_manager_pid(self, manager_pid: int) -> None:
        """Set the log-rotation manager process ID."""
        self._relation_data.update({self.manager_pid_key: str(manager_pid)})

    def set_sync_flag(self, flag: bool) -> None:
        """Set the log-rotation synchronization flag."""
        self._relation_data.update({self.synchronization_key: str(flag).lower()})

    def delete_manager_pid(self) -> None:
        """Delete the log-rotation manager process ID."""
        self._relation_data.update({self.manager_pid_key: ""})

    def delete_sync_flag(self) -> None:
        """Delete the log-rotation synchronization flag."""
        self._relation_data.update({self.synchronization_key: ""})
