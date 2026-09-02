# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import logging
import re

from charmlibs.interfaces.tls_certificates import PrivateKey
from charmlibs.pathops import PathProtocol

from ..clients import MySQLClusterClient, MySQLInstanceClient
from ..state import TLSState, TLSType
from ..workload import BaseSystem

logger = logging.getLogger(__name__)


class TLSManager:
    """Class to deal with the TLS operations."""

    ca_file_name = "custom-ca.pem"
    cert_file_name = "custom-server-cert.pem"
    private_key_file_name = "custom-server-key.pem"
    private_key_pattern = r"(-+(BEGIN|END) [A-Z ]+-+)"

    def __init__(
        self,
        state: TLSState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    def get_private_key_uri(self) -> str | None:
        """Get the TLS private key secret URI."""
        return self._state.get_private_key_uri()

    def set_private_key_uri(self, secret_uri: str) -> None:
        """Set the TLS private key secret URI."""
        return self._state.set_private_key_uri(secret_uri)

    def delete_private_key_uri(self) -> None:
        """Delete the TLS private key secret URI."""
        return self._state.delete_private_key_uri()

    def enable(self, ca_path: str, cert_path: str, key_path: str) -> None:
        """Enable the TLS setup."""
        match self._state.type:
            case TLSType.CLIENT:
                self._instance_client.set_client_tls(ca_path, cert_path, key_path, enable=True)
                self._instance_client.kill_client_sessions()
            case TLSType.PEER:
                self._instance_client.set_group_tls(ca_path, cert_path, key_path, enable=True)
            case _:
                raise ValueError("Invalid type of TLS")

    def disable(self) -> None:
        """Disable the TLS setup."""
        match self._state.type:
            case TLSType.CLIENT:
                self._instance_client.set_client_tls("", "", "", enable=False)
                self._instance_client.kill_client_sessions()
            case TLSType.PEER:
                self._instance_client.set_group_tls("", "", "", enable=False)
            case _:
                raise ValueError("Invalid type of TLS")

    def parse_private_key(self, secret_id: str | None) -> PrivateKey | None:
        """Parse the TLS private key from the received secret."""
        if not secret_id:
            return None

        try:
            secret_content = self._state.store.get_secret_content(secret_id)
        except Exception as e:
            logger.error(f"Failed to fetch secret {secret_id} content: {e}")
            return None

        private_key = secret_content.get("private-key")
        if private_key is None:
            logger.error(f"Failed to parse secret {secret_id}")
            return None

        if re.match(self.private_key_pattern, private_key):
            logger.error("Invalid private key format")
            return None

        try:
            private_key = base64.b64decode(private_key).decode("utf-8").strip()
        except Exception as e:
            logger.error(f"Failed to decode secret {secret_id}: {e}")
            return None

        private_key = PrivateKey(raw=private_key)
        if not private_key.is_valid():
            logger.error("Invalid private key format")
            return None

        return private_key

    def save_private_key(self, key: str | None) -> PathProtocol | None:
        """Saves the TLS private key into the filesystem."""
        if not key:
            return

        path = self._system.paths.mysql_data / f"{self._state.type}_{self.private_key_file_name}"
        path.write_text(data=key, mode=0o400, user=self._system.user, group=self._system.group)
        return path

    def save_ca(self, ca: str | None) -> PathProtocol | None:
        """Saves the TLS CA into the filesystem."""
        if not ca:
            return

        path = self._system.paths.mysql_data / f"{self._state.type}_{self.ca_file_name}"
        path.write_text(data=ca, mode=0o400, user=self._system.user, group=self._system.group)
        return path

    def save_cert(self, cert: str | None) -> PathProtocol | None:
        """Saves the TLS CERT into the filesystem."""
        if not cert:
            return

        path = self._system.paths.mysql_data / f"{self._state.type}_{self.cert_file_name}"
        path.write_text(data=cert, mode=0o400, user=self._system.user, group=self._system.group)
        return path
