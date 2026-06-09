# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""TLS Handler."""

import base64
import binascii
import logging
import re
import socket
from typing import TYPE_CHECKING

from charmlibs.interfaces.tls_certificates import (
    CertificateRequestAttributes,
    PrivateKey,
    TLSCertificatesRequiresV4,
)
from charms.mysql.v0.async_replication import (
    RELATION_CONSUMER,
    RELATION_OFFER,
)
from charms.mysql.v0.mysql import MySQLTLSSetupError
from mysql_shell.models import InstanceState
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus, MaintenanceStatus, SecretNotFoundError
from ops.pebble import ConnectionError as PebbleConnectionError
from ops.pebble import PathError, ProtocolError

from constants import (
    DB_RELATION_NAME,
    MYSQL_DATA_DIR,
    PEER,
    TLS_CLIENT_RELATION,
    TLS_PEER_RELATION,
    TLS_SSL_CA_FILE,
    TLS_SSL_CERT_FILE,
    TLS_SSL_KEY_FILE,
)

if TYPE_CHECKING:
    from charm import MySQLOperatorCharm

logger = logging.getLogger(__name__)


class RefreshTLSCertificatesEvent(EventBase):
    """Event for refreshing TLS certificates."""


class TLS(Object):
    """In this class we manage certificates relation."""

    client_certificates_refresh_event = EventSource(RefreshTLSCertificatesEvent)
    peer_certificates_refresh_event = EventSource(RefreshTLSCertificatesEvent)

    def __init__(self, charm: "MySQLOperatorCharm"):
        super().__init__(charm, "certificates")
        self.charm = charm
        self.unit_name = charm.unit.name.replace("/", "-")
        self.unit_endpoints = f"{self.unit_name}.{charm.app.name}-endpoints"

        self._common_hosts = {
            self.unit_name,
            self.unit_endpoints,
        }
        if fqdn := socket.getfqdn():
            self._common_hosts.add(fqdn)

        self.client_certificate = TLSCertificatesRequiresV4(
            self.charm,
            TLS_CLIENT_RELATION,
            certificate_requests=[
                CertificateRequestAttributes(
                    common_name=self._get_client_common_name(),
                    sans_dns={
                        *self._common_hosts,
                        *self._get_client_addresses(),
                    },
                ),
            ],
            private_key=self._parse_client_private_key(),
            refresh_events=[self.client_certificates_refresh_event],
        )
        self.peer_certificate = TLSCertificatesRequiresV4(
            self.charm,
            TLS_PEER_RELATION,
            certificate_requests=[
                CertificateRequestAttributes(
                    common_name=self._get_peer_common_name(),
                    sans_dns={
                        *self._common_hosts,
                        *self._get_peer_addresses(),
                    },
                ),
            ],
            private_key=self._parse_peer_private_key(),
            refresh_events=[self.peer_certificates_refresh_event],
        )

        self.framework.observe(
            self.client_certificate.on.certificate_available, self._on_client_certificate_available
        )
        self.framework.observe(
            self.peer_certificate.on.certificate_available, self._on_peer_certificate_available
        )
        self.framework.observe(
            self.charm.on[TLS_CLIENT_RELATION].relation_broken, self._on_client_relation_broken
        )
        self.framework.observe(
            self.charm.on[TLS_PEER_RELATION].relation_broken, self._on_peer_relation_broken
        )

    def _get_common_name(self) -> str:
        """Get a common name for the certificate attributes."""
        if len(self.unit_endpoints) > 64:
            return f"*.{self.charm.app.name}-endpoints"

        return self.unit_endpoints

    def _get_client_common_name(self) -> str:
        """Get a common name for the client certificate attributes."""
        return self._get_common_name()

    def _get_peer_common_name(self) -> str:
        """Get a common name for the peer certificate attributes."""
        return self._get_common_name()

    def _try_get_unit_address(self, relation_name: str) -> str:
        """Get fqdn/address for a unit, or "" if DNS not propagated yet."""
        try:
            return self.charm.get_unit_address(self.charm.unit, relation_name)
        except RuntimeError:
            return ""

    def _get_client_addresses(self) -> set[str]:
        """Get a set of client connection addresses for the certificate attributes."""
        client_addresses = set()
        if addr := self._try_get_unit_address(DB_RELATION_NAME):
            client_addresses.add(addr)

        return client_addresses

    def _get_peer_addresses(self) -> set[str]:
        """Get a set of peer connection addresses for the certificate attributes."""
        peer_addresses = set()
        for relation_name in (RELATION_CONSUMER, RELATION_OFFER, PEER):
            if addr := self._try_get_unit_address(relation_name):
                peer_addresses.add(addr)

        return peer_addresses

    def _get_client_tls_files(self) -> tuple[str | None, str | None, str | None]:
        """Prepare TLS files in special MySQL way.

        MySQL needs three files:
        - CA file should have a full chain.
        - Key file should have private key.
        - Certificate file should have certificate without certificate chain.
        """
        ca_file = None
        cert_file = None
        key_file = None

        certs, private_key = self.client_certificate.get_assigned_certificates()
        if private_key:
            key_file = str(private_key)
        if certs:
            cert_file = str(certs[0].certificate)
            ca_file = str(certs[0].ca)

        return key_file, ca_file, cert_file

    def _get_peer_tls_files(self) -> tuple[str | None, str | None, str | None]:
        """Prepare TLS files in special MySQL way.

        MySQL needs three files:
        - CA file should have a full chain.
        - Key file should have private key.
        - Certificate file should have certificate without certificate chain.
        """
        ca_file = None
        cert_file = None
        key_file = None

        certs, private_key = self.peer_certificate.get_assigned_certificates()
        if private_key:
            key_file = str(private_key)
        if certs:
            cert_file = str(certs[0].certificate)
            ca_file = str(certs[0].ca)

        return key_file, ca_file, cert_file

    def _parse_private_key(self, secret_id: str | None) -> PrivateKey | None:
        """Parse the received private key."""
        if not secret_id:
            return None

        try:
            secret_content = self.charm.model.get_secret(id=secret_id).get_content(refresh=True)
        except SecretNotFoundError as e:
            logger.error(e)
            return None

        private_key = secret_content.get("private-key")
        if private_key is None:
            logger.error(f"Secret {secret_id} does not contain a private key.")
            return None

        if re.match(r"(-+(BEGIN|END) [A-Z ]+-+)", private_key):
            logger.error(f"Secret {secret_id} must be base64 encoded.")
            return None

        try:
            private_key = base64.b64decode(private_key).decode("utf-8").strip()
        except (UnicodeDecodeError, binascii.Error) as e:
            logger.error(e)
            return None

        private_key = PrivateKey(raw=private_key)
        if not private_key.is_valid():
            logger.error("Invalid private key format.")
            return None

        return private_key

    def _parse_client_private_key(self) -> PrivateKey | None:
        """Parse the client private key from the config."""
        return self._parse_private_key(self.charm.config.tls_client_private_key)

    def _parse_peer_private_key(self) -> PrivateKey | None:
        """Parse the peer private key from the config."""
        return self._parse_private_key(self.charm.config.tls_peer_private_key)

    def _on_client_certificate_available(self, event: EventBase) -> None:
        """Handler for the certificate available event."""
        state = self.charm._mysql.get_member_state()
        if state != InstanceState.ONLINE:
            logger.debug("Unit not initialized yet, deferring client TLS configuration.")
            event.defer()
            return

        self.charm.unit.status = MaintenanceStatus("Enabling client TLS")

        try:
            self._push_tls_files_to_workload()
        except (PebbleConnectionError, PathError, ProtocolError) as e:
            logger.error(f"Cannot push TLS certificates: {e}")
            event.defer()
            return

        try:
            self.charm._mysql.setup_client_tls(
                ca_path=f"{MYSQL_DATA_DIR}/client_{TLS_SSL_CA_FILE}",
                key_path=f"{MYSQL_DATA_DIR}/client_{TLS_SSL_KEY_FILE}",
                cert_path=f"{MYSQL_DATA_DIR}/client_{TLS_SSL_CERT_FILE}",
                require_tls=True,
            )
            self.charm._mysql.kill_client_sessions()
        except MySQLTLSSetupError as e:
            logger.error(f"Failed to enable client TLS: {e}")
            self.charm.unit.status = BlockedStatus("Failed to enable client TLS.")
            return

        self.charm.unit.status = self.charm.build_unit_workload_status()

    def _on_peer_certificate_available(self, event: EventBase) -> None:
        """Handler for the peer certificate available event."""
        state = self.charm._mysql.get_member_state()
        if state != InstanceState.ONLINE:
            logger.debug("Unit not initialized yet, deferring peer TLS configuration.")
            event.defer()
            return

        self.charm.unit.status = MaintenanceStatus("Enabling peer TLS")

        try:
            self._push_tls_files_to_workload()
        except (PebbleConnectionError, PathError, ProtocolError) as e:
            logger.error(f"Cannot push TLS certificates: {e}")
            event.defer()
            return

        try:
            self.charm._mysql.setup_group_tls(
                ca_path=f"{MYSQL_DATA_DIR}/peer_{TLS_SSL_CA_FILE}",
                key_path=f"{MYSQL_DATA_DIR}/peer_{TLS_SSL_KEY_FILE}",
                cert_path=f"{MYSQL_DATA_DIR}/peer_{TLS_SSL_CERT_FILE}",
                require_tls=True,
            )
            self.charm.rolling_ops.request_async_lock(callback_id="replication")
        except MySQLTLSSetupError as e:
            logger.error(f"Failed to enable peer TLS: {e}")
            self.charm.unit.status = BlockedStatus("Failed to enable peer TLS.")
            return

    def _on_client_relation_broken(self, _: EventBase) -> None:
        """Handler for the client relation broken event."""
        if self.charm.removing_unit:
            logger.debug("Unit is being removed, skipping client TLS cleanup.")
            return

        self.charm.unit.status = MaintenanceStatus("Disabling client TLS")

        try:
            self.charm._mysql.setup_client_tls()
            self.charm._mysql.kill_client_sessions()
        except MySQLTLSSetupError as e:
            logger.error(f"Failed to disable client TLS: {e}")
            self.charm.unit.status = BlockedStatus("Failed to disable client TLS.")
            return

        if self.charm.unit.is_leader():
            del self.charm.app_peer_data["client-private-key"]

        self.charm.unit.status = self.charm.build_unit_workload_status()

    def _on_peer_relation_broken(self, _: EventBase) -> None:
        """Handler for the peer relation broken event."""
        if self.charm.removing_unit:
            logger.debug("Unit is being removed, skipping peer TLS cleanup.")
            return

        self.charm.unit.status = MaintenanceStatus("Disabling peer TLS")

        try:
            self.charm._mysql.setup_group_tls()
            self.charm.rolling_ops.request_async_lock(callback_id="replication")
        except MySQLTLSSetupError as e:
            logger.error(f"Failed to disable peer TLS: {e}")
            self.charm.unit.status = BlockedStatus("Failed to disable peer TLS.")
            return

        if self.charm.unit.is_leader():
            del self.charm.app_peer_data["peer-private-key"]

    def _push_tls_files_to_workload(self) -> None:
        """Push TLS files to unit."""
        key, ca, cert = self._get_client_tls_files()
        if key:
            self.charm._mysql.write_content_to_file(
                f"{MYSQL_DATA_DIR}/client_{TLS_SSL_KEY_FILE}", key, permission=0o400
            )
        if ca:
            self.charm._mysql.write_content_to_file(
                f"{MYSQL_DATA_DIR}/client_{TLS_SSL_CA_FILE}", ca, permission=0o400
            )
        if cert:
            self.charm._mysql.write_content_to_file(
                f"{MYSQL_DATA_DIR}/client_{TLS_SSL_CERT_FILE}", cert, permission=0o400
            )

        key, ca, cert = self._get_peer_tls_files()
        if key:
            self.charm._mysql.write_content_to_file(
                f"{MYSQL_DATA_DIR}/peer_{TLS_SSL_KEY_FILE}", key, permission=0o400
            )
        if ca:
            self.charm._mysql.write_content_to_file(
                f"{MYSQL_DATA_DIR}/peer_{TLS_SSL_CA_FILE}", ca, permission=0o400
            )
        if cert:
            self.charm._mysql.write_content_to_file(
                f"{MYSQL_DATA_DIR}/peer_{TLS_SSL_CERT_FILE}", cert, permission=0o400
            )
