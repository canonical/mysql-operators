# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""TLS Handler."""

import logging
import socket
from typing import TYPE_CHECKING

from charmlibs.interfaces.tls_certificates import (
    CertificateRequestAttributes,
    TLSCertificatesRequiresV4,
)
from charms.mysql.v0.mysql import MySQLTLSSetupError
from mysql_shell.models import InstanceState
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus, MaintenanceStatus
from ops.pebble import ConnectionError as PebbleConnectionError
from ops.pebble import PathError, ProtocolError

from constants import (
    DB_RELATION_NAME,
    MYSQL_DATA_DIR,
    TLS_CLIENT_RELATION,
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

    refresh_tls_certificates_event = EventSource(RefreshTLSCertificatesEvent)

    def __init__(self, charm: "MySQLOperatorCharm"):
        super().__init__(charm, "certificates")
        self.charm = charm
        self.unit_name = charm.unit.name.replace("/", "-")

        self._common_hosts = {
            self.unit_name,
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
            refresh_events=[self.refresh_tls_certificates_event],
        )

        self.framework.observe(
            self.client_certificate.on.certificate_available, self._on_certificate_available
        )
        self.framework.observe(
            self.charm.on[TLS_CLIENT_RELATION].relation_broken, self._on_relation_broken
        )

    def _get_client_common_name(self) -> str:
        """Get a common name for the certificate attributes."""
        return self.charm.get_unit_address(self.charm.unit, DB_RELATION_NAME) or self.unit_name

    def _get_client_addresses(self) -> set[str]:
        """Get a set of client connection addresses for the certificate attributes."""
        client_addresses = set()
        if addr := self.charm.get_unit_address(self.charm.unit, DB_RELATION_NAME):
            client_addresses.add(addr)

        return client_addresses

    def _get_client_tls_files(self) -> tuple[str | None, str | None, str | None]:
        """Prepare TLS files in special MySQL way.

        MySQL needs three files:
        — CA file should have a full chain.
        — Key file should have private key.
        — Certificate file should have certificate without certificate chain.
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

    def _on_certificate_available(self, event: EventBase) -> None:
        """Handler for the certificate available event."""
        state = self.charm._mysql.get_member_state()
        if state != InstanceState.ONLINE:
            logger.debug("Unit not initialized yet, deferring TLS configuration.")
            event.defer()
            return

        self.charm.unit.status = MaintenanceStatus("Enabling TLS")

        try:
            self._push_tls_files_to_workload()
        except (PebbleConnectionError, PathError, ProtocolError) as e:
            logger.error("Cannot push TLS certificates: %r", e)
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
        except MySQLTLSSetupError:
            logger.error("Failed to enable TLS configuration.")
            self.charm.unit.status = BlockedStatus("Failed to enable TLS configuration.")
            return

        self.charm.unit.status = self.charm.build_unit_workload_status()

    def _on_relation_broken(self, _: EventBase) -> None:
        """Handler for the relation broken event."""
        if self.charm.removing_unit:
            logger.debug("Unit is being removed, skipping TLS cleanup.")
            return

        self.charm.unit.status = MaintenanceStatus("Disabling TLS")

        try:
            self.charm._mysql.setup_client_tls()
            self.charm._mysql.kill_client_sessions()
        except MySQLTLSSetupError:
            logger.error("Failed to disable TLS configuration.")
            self.charm.unit.status = BlockedStatus("Failed to disable TLS configuration.")
            return

        self.charm.unit.status = self.charm.build_unit_workload_status()

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
