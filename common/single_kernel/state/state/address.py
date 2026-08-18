# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json

from ops.model import Application, Model, Relation, Unit

from ..secrets import JujuSecretStore


class AddressResolutionState:
    """Class to deal with the address resolution state."""

    hostname_key = "hostname-details"
    manager_pid_key = "ip-address-manager-pid"

    def __init__(self, model: Model, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._secrets = JujuSecretStore(model, relation)
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def secrets(self) -> JujuSecretStore:
        """Return the secret store."""
        return self._secrets

    def get_hostname_details(self) -> dict | None:
        """Get the hostname details dictionary."""
        details = self._relation_data.get(self.hostname_key)
        if not details:
            return None

        return json.loads(details)

    def get_manager_pid(self) -> int | None:
        """Get the address resolution process ID."""
        manager_pid = self._relation_data.get(self.manager_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def set_hostname_details(self, details: dict) -> None:
        """Set the hostname details dictionary."""
        self._relation_data.update({self.hostname_key: json.dumps(details)})

    def set_manager_pid(self, manager_pid: int) -> None:
        """Set the address resolution process ID."""
        self._relation_data.update({self.manager_pid_key: str(manager_pid)})

    def delete_manager_pid(self) -> None:
        """Delete the address resolution process ID."""
        self._relation_data.pop(self.manager_pid_key, None)
