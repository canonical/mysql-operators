# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ._base import BaseData


class SelfHealingData(BaseData):
    """Class to deal with the self-healing."""

    manager_pid_key = "self-healing-manager-pid"

    def get_self_healing_pid(self) -> int | None:
        """Get the self-healing process ID."""
        manager_pid = self._data.get(self.manager_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def set_self_healing_pid(self, manager_pid: int) -> None:
        """Set the self-healing process ID."""
        self._data.update({self.manager_pid_key: str(manager_pid)})

    def delete_self_healing_pid(self) -> None:
        """Delete the self-healing process ID."""
        self._data.pop(self.manager_pid_key, None)
