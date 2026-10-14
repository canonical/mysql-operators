# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import MutableMapping


class PeerStateApp:
    """Class to deal with the peer application state."""

    cluster_name_key = "cluster-name"
    cluster_set_name_key = "cluster-set-domain-name"
    cluster_removed_key = "removed-from-cluster-set"
    cluster_rejoin_key = "rejoin-secondaries"

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        self._data = data

    @staticmethod
    def _build_secret_uri_key(prefix: str) -> str:
        """Secret key to use in the Juju databag."""
        return f"{prefix}-private-key"

    def get_cluster_name(self) -> str | None:
        """Get the MySQL cluster name."""
        name = self._data.get(self.cluster_name_key)
        if not name:
            return None

        return name

    def get_cluster_set_name(self) -> str | None:
        """Get the MySQL cluster-set name."""
        name = self._data.get(self.cluster_set_name_key)
        if not name:
            return None

        return name

    def get_cluster_removed_flag(self) -> bool | None:
        """Get the MySQL cluster removed flag."""
        flag = self._data.get(self.cluster_removed_key)
        if not flag:
            return None

        return flag == "true"

    def get_cluster_rejoin_flag(self) -> bool | None:
        """Get the MySQL cluster rejoin flag."""
        flag = self._data.get(self.cluster_rejoin_key)
        if not flag:
            return None

        return flag == "true"

    def get_private_key_uri(self, prefix: str) -> str | None:
        """Get the private key secret URI."""
        secret_key = self._build_secret_uri_key(prefix)
        secret_uri = self._data.get(secret_key)
        if not secret_uri:
            return None

        return secret_uri

    def set_cluster_name(self, name: str) -> None:
        """Set the MySQL cluster name."""
        self._data.update({self.cluster_name_key: str(name)})

    def set_cluster_set_name(self, name: str) -> None:
        """Set the MySQL cluster-set name."""
        self._data.update({self.cluster_set_name_key: str(name)})

    def set_cluster_removed_flag(self, flag: bool) -> None:
        """Set the MySQL cluster removed flag."""
        self._data.update({self.cluster_removed_key: str(flag).lower()})

    def set_cluster_rejoin_flag(self, flag: bool) -> None:
        """Set the MySQL cluster rejoin flag."""
        self._data.update({self.cluster_rejoin_key: str(flag).lower()})

    def set_private_key_uri(self, prefix: str, secret_uri: str) -> None:
        """Set the private key secret URI."""
        secret_key = self._build_secret_uri_key(prefix)
        __________ = self._data.update({secret_key: str(secret_uri)})

    def delete_cluster_removed_flag(self) -> None:
        """Delete the MySQL cluster removed flag."""
        self._data.pop(self.cluster_removed_key, None)

    def delete_cluster_rejoin_flag(self) -> None:
        """Delete the MySQL cluster rejoin flag."""
        self._data.pop(self.cluster_rejoin_key, None)

    def delete_private_key_uri(self, prefix: str) -> None:
        """Delete the private key secret URI."""
        secret_key = self._build_secret_uri_key(prefix)
        __________ = self._data.pop(secret_key, None)
