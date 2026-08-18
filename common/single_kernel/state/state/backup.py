# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Model, Relation, Unit

from ..secrets import JujuSecretStore


class BackupState:
    """Class to deal with the backup state."""

    def __init__(self, model: Model, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._secrets = JujuSecretStore(model, relation)
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def secrets(self) -> JujuSecretStore:
        """Return the secret store."""
        return self._secrets
