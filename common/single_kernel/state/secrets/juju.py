# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import (
    Model,
    Relation,
    Secret,
    SecretNotFoundError,
)

from .base import BaseSecretStore


class JujuSecretStore(BaseSecretStore):
    """Class to deal with the Juju secrets store."""

    def __init__(self, model: Model, relation: Relation):
        """Initialize the class attributes."""
        self._model = model
        self._relation = relation

    def _get_secret(self, secret_id: str | None = None, secret_label: str | None = None) -> Secret:
        """Get a Juju secret.

        In case of failure, it must raise an exception that is common across secret stores.
        Therefore, the Juju specific exceptions are wrapped in order to raise builtin ones.
        """
        try:
            return self._model.get_secret(id=secret_id, label=secret_label)
        except SecretNotFoundError as e:
            raise ValueError(f"Secret not found: {e}")

    def create_secret(self, content: dict[str, str]) -> str:
        """Create a Juju secret."""
        secret = self._model.app.add_secret(content)
        secret.grant(self._relation)

        return str(secret.id)

    def delete_secret(self, secret_id: str) -> None:
        """Delete a Juju secret."""
        secret = self._get_secret(secret_id=secret_id)
        secret.remove_all_revisions()

    def get_secret_content(self, secret_id: str) -> dict[str, str]:
        """Get a Juju secret content."""
        secret = self._get_secret(secret_id=secret_id)
        content = secret.peek_content()

        return content

    def set_secret_content_by_id(self, secret_id: str, content: dict[str, str]) -> None:
        """Set a Juju secret content by ID."""
        secret = self._get_secret(secret_id=secret_id)
        secret.set_content(content)

    def set_secret_content_by_label(self, secret_label: str, content: dict[str, str]) -> None:
        """Set a Juju secret content by label."""
        secret = self._get_secret(secret_label=secret_label)
        secret.set_content(content)
