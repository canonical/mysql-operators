# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import enum
from abc import ABC, abstractmethod

from ops.model import Application, Model, Relation, Unit

from ..secrets import JujuSecretStore


class TLSType(enum.StrEnum):
    """Type of TLS state."""

    CLIENT = "client"
    PEER = "peer"


class TLSState(ABC):
    """Abstract class to deal with the TLS encryption state."""

    def __init__(self, model: Model, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._secrets = JujuSecretStore(model, relation)
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    @abstractmethod
    def type(self) -> str:
        """Type of state."""
        raise NotImplementedError()

    @property
    def _secret_uri_key(self) -> str:
        """Secret key to use in the Juju databag."""
        return f"{self.type}-private-key"

    @property
    def secrets(self) -> JujuSecretStore:
        """Return the secret store."""
        return self._secrets

    def get_private_key_uri(self) -> str | None:
        """Get the private key secret URI."""
        secret_uri = self._relation_data.get(self._secret_uri_key)
        if not secret_uri:
            return None

        return secret_uri

    def set_private_key_uri(self, secret_uri: str) -> None:
        """Set the private key secret URI."""
        self._relation_data.update({self._secret_uri_key: str(secret_uri)})

    def delete_private_key_uri(self) -> None:
        """Delete the private key secret URI."""
        self._relation_data.pop(self._secret_uri_key, None)


class TLSClientState(TLSState):
    """Class to deal with the client TLS encryption state."""

    @property
    def type(self) -> str:
        """Type of TLS state."""
        return TLSType.CLIENT


class TLSPeerState(TLSState):
    """Class to deal with the peers TLS encryption state."""

    @property
    def type(self) -> str:
        """Type of TLS state."""
        return TLSType.PEER
