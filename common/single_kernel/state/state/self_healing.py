# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Model, Relation, Unit

from ..secrets import JujuSecretStore


class SelfHealingState:
    """Class to deal with the self-healing state."""

    manager_pid_key = "self-healing-manager-pid"

    def __init__(self, model: Model, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._secrets = JujuSecretStore(model, relation)
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def secrets(self) -> JujuSecretStore:
        """Return the secret store."""
        return self._secrets

    def get_manager_pid(self) -> int | None:
        """Get the self-healing process ID."""
        manager_pid = self._relation_data.get(self.manager_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def set_manager_pid(self, manager_pid: int) -> None:
        """Set the self-healing process ID."""
        self._relation_data.update({self.manager_pid_key: str(manager_pid)})

    def delete_manager_pid(self) -> None:
        """Delete the self-healing process ID."""
        self._relation_data.pop(self.manager_pid_key, None)
