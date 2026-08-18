# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json

from ._base import BaseData


class AddressData(BaseData):
    """Class to deal with the address resolution."""

    hostname_key = "hostname-details"
    manager_pid_key = "ip-address-manager-pid"

    def get_hostname_details(self) -> dict | None:
        """Get the hostname details dictionary."""
        details = self._data.get(self.hostname_key)
        if not details:
            return None

        return json.loads(details)

    def get_address_pid(self) -> int | None:
        """Get the address resolution process ID."""
        manager_pid = self._data.get(self.manager_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def set_hostname_details(self, details: dict) -> None:
        """Set the hostname details dictionary."""
        self._data.update({self.hostname_key: json.dumps(details)})

    def set_address_pid(self, manager_pid: int) -> None:
        """Set the address resolution process ID."""
        self._data.update({self.manager_pid_key: str(manager_pid)})

    def delete_address_pid(self) -> None:
        """Delete the address resolution process ID."""
        self._data.pop(self.manager_pid_key, None)
