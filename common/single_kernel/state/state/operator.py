# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Model, Relation, Unit

from ..secrets import JujuSecretStore


class OperatorState:
    """Class to deal with the operator state."""

    topology_timestamp_key = "topology-change-timestamp"

    def __init__(self, model: Model, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._secrets = JujuSecretStore(model, relation)
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def secrets(self) -> JujuSecretStore:
        """Return the secret store."""
        return self._secrets

    def get_topology_timestamp(self) -> int | None:
        """Get the MySQL cluster topology change timestamp."""
        timestamp = self._relation_data.get(self.topology_timestamp_key)
        if not timestamp:
            return None

        return int(timestamp)

    def set_topology_timestamp(self, timestamp: int) -> None:
        """Set the MySQL cluster topology change timestamp."""
        self._relation_data.update({self.topology_timestamp_key: str(timestamp)})
