# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Model, Relation, Unit

from ...libs import DatabaseProviderData
from ..secrets import JujuSecretStore


class DatabaseState:
    """Class to deal with the database state."""

    def __init__(self, model: Model, relation: Relation, _: Unit | Application):
        """Initialize the class attributes."""
        self._secrets = JujuSecretStore(model, relation)
        self._relation = relation
        self._relation_data = DatabaseProviderData(model, relation.name)

    @property
    def secrets(self) -> JujuSecretStore:
        """Return the secret store."""
        return self._secrets

    def get_database_password(self) -> str | None:
        """Get the database password."""
        return self._relation_data.fetch_my_relation_field(self._relation.id, "password")

    def set_database_name(self, name: str) -> None:
        """Set the database name."""
        self._relation_data.set_database(self._relation.id, name)

    def set_credentials(self, username: str, password: str) -> None:
        """Set the database credentials."""
        self._relation_data.set_credentials(self._relation.id, username, password)

    def set_rw_endpoints(self, endpoints: list[str]) -> None:
        """Set the database read-write endpoints."""
        self._relation_data.set_endpoints(self._relation.id, ",".join(endpoints))

    def set_ro_endpoints(self, endpoints: list[str]) -> None:
        """Set the database read-only endpoints."""
        self._relation_data.set_read_only_endpoints(self._relation.id, ",".join(endpoints))

    def set_version(self, version: str) -> None:
        """Set the database version."""
        self._relation_data.set_version(self._relation.id, version)
