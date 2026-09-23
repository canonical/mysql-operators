# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Any, TypedDict, Unpack

from ops.model import Model, Relation, Secret, SecretNotFoundError


class SecretKwargs(TypedDict, total=False):
    """Class to group the secret helper args."""

    secret_id: str
    secret_label: str


class SecretStore:
    """Class to deal with the secrets store."""

    def __init__(self, model: Model):
        """Initialize the class attributes."""
        self._model = model

    def _get_secret(self, **kwargs: Unpack[SecretKwargs]) -> Secret:
        """Get a Juju secret."""
        secret_id = kwargs.get("secret_id")
        secret_label = kwargs.get("secret_label")

        if not secret_id and not secret_label:
            raise ValueError(f"Secret ID or label needs to be provided")

        try:
            return self._model.get_secret(id=secret_id, label=secret_label)
        except SecretNotFoundError as e:
            raise ValueError(f"Secret not found: {e}")

    def create(self, content: dict[str, str], relation: Relation) -> str:
        """Create a Juju secret."""
        secret = self._model.app.add_secret(content)
        secret.grant(relation)

        return str(secret.id)

    def delete(self, **kwargs: Unpack[SecretKwargs]) -> None:
        """Delete a Juju secret."""
        secret = self._get_secret(**kwargs)
        secret.remove_all_revisions()

    def get_value(self, secret_key: str, **kwargs: Unpack[SecretKwargs]) -> Any:
        """Get a Juju secret value."""
        secret = self._get_secret(**kwargs)
        content = secret.peek_content()

        value = content.get(secret_key)
        if not value:
            raise ValueError(f"Failed to get secret key {secret_key}")

        return value

    def get_content(self, **kwargs: Unpack[SecretKwargs]) -> dict[str, Any]:
        """Get a Juju secret content."""
        secret = self._get_secret(**kwargs)
        content = secret.peek_content()

        return content

    def set_content(self, content: dict[str, Any], **kwargs: Unpack[SecretKwargs]) -> None:
        """Set a Juju secret content."""
        secret = self._get_secret(**kwargs)
        secret.set_content(content)
