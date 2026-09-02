# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import logging
import re
from abc import ABC, abstractmethod

from charmlibs.interfaces.tls_certificates import PrivateKey
from charmlibs.pathops import PathProtocol
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import InstanceState

from ...state import PeerState
from ...workload import BaseSystem
from ..clients import Clients

logger = logging.getLogger(__name__)


class BaseTLSManager(ABC):
    """Abstract class to deal with TLS operations."""

    ca_file_name = "custom-ca.pem"
    cert_file_name = "custom-server-cert.pem"
    private_key_file_name = "custom-server-key.pem"
    private_key_pattern = r"(-+(BEGIN|END) [A-Z ]+-+)"

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients

    @property
    @abstractmethod
    def type(self) -> str:
        """Return the type of the TLS manager."""
        raise NotImplementedError()

    @abstractmethod
    def enable(self, ca_path: str, cert_path: str, key_path: str) -> None:
        """Enable the TLS setup."""
        raise NotImplementedError()

    @abstractmethod
    def disable(self) -> None:
        """Disable the TLS setup."""
        raise NotImplementedError()

    def get_private_key_uri(self) -> str | None:
        """Get the TLS private key secret URI."""
        return self._state.app.get_private_key_uri(self.type)

    def set_private_key_uri(self, secret_uri: str) -> None:
        """Set the TLS private key secret URI."""
        return self._state.app.set_private_key_uri(self.type, secret_uri)

    def delete_private_key_uri(self) -> None:
        """Delete the TLS private key secret URI."""
        return self._state.app.delete_private_key_uri(self.type)

    def check_instance(self) -> None:
        """Check the MySQL instance health."""
        try:
            state = self._clients.instance.fetch_state()
        except ExecutionError as e:
            raise RuntimeError("Failed to fetch instance state") from e

        if state != InstanceState.ONLINE:
            raise RuntimeError("Instance is not healthy")

    def parse_private_key(self, private_key: str) -> PrivateKey | None:
        """Parse and validate a TLS private key."""
        if re.match(self.private_key_pattern, private_key):
            logger.error("Invalid private key format")
            return None

        try:
            raw_key = base64.b64decode(private_key).decode("utf-8").strip()
        except Exception as e:
            logger.error(f"Failed to decode private key: {e}")
            return None

        private_key = PrivateKey(raw=raw_key)
        if not private_key.is_valid():
            logger.error("Invalid private key format")
            return None

        return private_key

    def save_private_key(self, key: str | None) -> PathProtocol | None:
        """Saves the TLS private key into the filesystem."""
        if not key:
            return

        path = self._system.paths.mysql_data / f"{self.type}_{self.private_key_file_name}"
        path.write_text(data=key, mode=0o400, user=self._system.user, group=self._system.group)
        return path

    def save_ca(self, ca: str | None) -> PathProtocol | None:
        """Saves the TLS CA into the filesystem."""
        if not ca:
            return

        path = self._system.paths.mysql_data / f"{self.type}_{self.ca_file_name}"
        path.write_text(data=ca, mode=0o400, user=self._system.user, group=self._system.group)
        return path

    def save_cert(self, cert: str | None) -> PathProtocol | None:
        """Saves the TLS CERT into the filesystem."""
        if not cert:
            return

        path = self._system.paths.mysql_data / f"{self.type}_{self.cert_file_name}"
        path.write_text(data=cert, mode=0o400, user=self._system.user, group=self._system.group)
        return path


class ClientTLSManager(BaseTLSManager):
    """Class to deal with the client TLS operations."""

    @property
    def type(self) -> str:
        """Return the type of the TLS manager."""
        return "client"

    def enable(self, ca_path: str, cert_path: str, key_path: str) -> None:
        """Enable the TLS setup."""
        try:
            self._clients.instance.set_client_tls(ca_path, cert_path, key_path, enable=True)
            self._clients.instance.kill_client_sessions()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to enable {self.type} TLS") from e

    def disable(self) -> None:
        """Disable the TLS setup."""
        try:
            self._clients.instance.set_client_tls("", "", "", enable=False)
            self._clients.instance.kill_client_sessions()
        except ExecutionError as e:
            raise RuntimeError(f"Failed to disable {self.type} TLS") from e


class PeerTLSManager(BaseTLSManager):
    """Class to deal with the peer TLS operations."""

    @property
    def type(self) -> str:
        """Return the type of the TLS manager."""
        return "peer"

    def enable(self, ca_path: str, cert_path: str, key_path: str) -> None:
        """Enable the TLS setup."""
        try:
            self._clients.instance.set_group_tls(ca_path, cert_path, key_path, enable=True)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to enable {self.type} TLS") from e

    def disable(self) -> None:
        """Disable the TLS setup."""
        try:
            self._clients.instance.set_group_tls("", "", "", enable=False)
        except ExecutionError as e:
            raise RuntimeError(f"Failed to disable {self.type} TLS") from e
