# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from abc import ABC, abstractmethod

from charmlibs.interfaces.tls_certificates import (
    CertificateAvailableEvent,
    CertificateRequestAttributes,
    PrivateKey,
    TLSCertificatesRequiresV4,
)
from ops.charm import RelationBrokenEvent
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus, MaintenanceStatus
from ops.pebble import Error

from ...core import RELATION_TLS_CLIENT, RELATION_TLS_PEER
from ...managers import TLSManager
from ..helpers import Helpers

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class TLSRefreshCertificatesEvent(EventBase):
    """Event for refreshing TLS certificates."""


class TLSEventHandler(Object, ABC):
    """Class to deal with the TLS events."""

    refresh_event = EventSource(TLSRefreshCertificatesEvent)

    def __init__(self, charm: Operator, manager: TLSManager, helpers: Helpers, relation: str):
        """Initialize the class attributes."""
        super().__init__(charm, relation)
        self._charm = charm
        self._manager = manager
        self._helpers = helpers

        cert_common = f"{charm.unit.name}.{charm.app.name}"
        cert_request = CertificateRequestAttributes(cert_common)

        self._requirer = TLSCertificatesRequiresV4(
            charm=charm,
            relationship_name=relation,
            certificate_requests=[cert_request],
            refresh_events=[self.refresh_event],
            private_key=self.parse_private_key(),
        )

        self.framework.observe(
            self._requirer.on.certificate_available,
            self._on_certificate_available,
        )
        self.framework.observe(
            self._charm.on[relation].relation_broken,
            self._on_relation_broken,
        )

    @abstractmethod
    def parse_private_key(self) -> PrivateKey | None:
        """Parse the private key from the config."""
        raise NotImplementedError()

    @abstractmethod
    def rotate_private_key(self) -> None:
        """Rotate the private key."""
        raise NotImplementedError()

    def _get_tls_data(self) -> tuple[str | None, str | None, str | None]:
        """Get the TLS data from the certificate provider ."""
        ca = None
        cert = None
        key = None

        certificates, private_key = self._requirer.get_assigned_certificates()

        if certificates:
            ca = str(certificates[0].ca)
            cert = str(certificates[0].certificate)
        if private_key:
            key = str(private_key)

        return ca, cert, key

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Event handler for the certificate-available event."""
        try:
            self._manager.check_instance()
        except RuntimeError as e:
            logger.warning(f"Deferring TLS configuration: {e}")
            event.defer()
            return

        self._charm.set_unit_status(MaintenanceStatus("Enabling TLS"))
        ca, cert, key = self._get_tls_data()

        try:
            ca_path = self._manager.save_ca(ca)
            cert_path = self._manager.save_cert(cert)
            key_path = self._manager.save_private_key(key)
        except Error as e:
            logger.error(f"Cannot write TLS certificates: {e}")
            event.defer()
            return

        try:
            self._manager.enable(str(ca_path), str(cert_path), str(key_path))
        except RuntimeError as e:
            self._charm.set_unit_status(BlockedStatus("Failed to enable TLS"))
            logger.error(e)
            return

    def _on_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Event handler for the relation-broken event."""
        self._charm.set_unit_status(MaintenanceStatus("Disabling TLS"))

        try:
            self._manager.disable()
        except RuntimeError as e:
            self._charm.set_unit_status(BlockedStatus("Failed to disable TLS"))
            logger.error(e)
            return

        if self._charm.unit.is_leader():
            self._manager.delete_private_key_uri()

        self._charm.set_unit_status(self._charm.build_unit_status())


class TLSClientEventHandler(TLSEventHandler):
    """Class to deal with the TLS events."""

    def __init__(self, charm: Operator, manager: TLSManager):
        """Initialize the class attributes."""
        super().__init__(charm, manager, RELATION_TLS_CLIENT)

    def parse_private_key(self) -> PrivateKey | None:
        """Parse the private key from the config."""
        return self._manager.parse_private_key(self._charm.config.tls_client_private_key)

    def rotate_private_key(self) -> None:
        """Rotate the private key."""
        new_uri = self._charm.config.tls_client_private_key
        old_uri = self._manager.get_private_key_uri()

        if new_uri != old_uri:
            self.refresh_event.emit()
            if self._charm.unit.is_leader():
                self._manager.set_private_key_uri(new_uri)

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Event handler for the certificate-available event."""
        super()._on_certificate_available(event)


class TLSPeerEventHandler(TLSEventHandler):
    """Class to deal with the TLS events."""

    def __init__(self, charm: Operator, manager: TLSManager):
        """Initialize the class attributes."""
        super().__init__(charm, manager, RELATION_TLS_PEER)

    def parse_private_key(self) -> PrivateKey | None:
        """Parse the private key from the config."""
        return self._manager.parse_private_key(self._charm.config.tls_peer_private_key)

    def rotate_private_key(self) -> None:
        """Rotate the private key."""
        new_uri = self._charm.config.tls_peer_private_key
        old_uri = self._manager.get_private_key_uri()

        if new_uri != old_uri:
            self.refresh_event.emit()
            if self._charm.unit.is_leader():
                self._manager.set_private_key_uri(new_uri)

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Event handler for the certificate-available event."""
        super()._on_certificate_available(event)
        self._helpers.rolling.callbacks.request_async_lock(callback_id="replication")
