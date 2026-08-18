# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ._base import BaseData


class LogrotateData(BaseData):
    """Class to deal with the log-rotation."""

    manager_pid_key = "log-rotate-manager-pid"
    synchronization_key = "logs-synced"

    def get_logrotate_pid(self) -> int | None:
        """Get the log-rotation process ID."""
        manager_pid = self._data.get(self.manager_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def get_sync_flag(self) -> bool | None:
        """Get the log-rotation synchronization flag."""
        flag = self._data.get(self.synchronization_key)
        if not flag:
            return None

        return flag == "true"

    def set_logrotate_pid(self, manager_pid: int) -> None:
        """Set the log-rotation process ID."""
        self._data.update({self.manager_pid_key: str(manager_pid)})

    def set_sync_flag(self, flag: bool) -> None:
        """Set the log-rotation synchronization flag."""
        self._data.update({self.synchronization_key: str(flag).lower()})

    def delete_logrotate_pid(self) -> None:
        """Delete the log-rotation process ID."""
        self._data.pop(self.manager_pid_key, None)

    def delete_sync_flag(self) -> None:
        """Delete the log-rotation synchronization flag."""
        self._data.pop(self.synchronization_key, None)
