# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Relation, Unit

from .secrets import BaseSecretStore


class DatabaseState:
    """Class to deal with the database state."""

    def __init__(self, store: BaseSecretStore, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._store = store
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def store(self) -> BaseSecretStore:
        """Return the secrets store."""
        return self._store
