# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ._base import BaseData


class TLSData(BaseData):
    """Class to deal with the TLS encryption state."""

    @staticmethod
    def _build_secret_uri_key(prefix: str) -> str:
        """Secret key to use in the Juju databag."""
        return f"{prefix}-private-key"

    def get_private_key_uri(self, prefix: str) -> str | None:
        """Get the private key secret URI."""
        secret_key = self._build_secret_uri_key(prefix)
        secret_uri = self._data.get(secret_key)
        if not secret_uri:
            return None

        return secret_uri

    def set_private_key_uri(self, prefix: str, secret_uri: str) -> None:
        """Set the private key secret URI."""
        secret_key = self._build_secret_uri_key(prefix)
        __________ = self._data.update({secret_key: str(secret_uri)})

    def delete_private_key_uri(self, prefix: str) -> None:
        """Delete the private key secret URI."""
        secret_key = self._build_secret_uri_key(prefix)
        __________ = self._data.pop(secret_key, None)
