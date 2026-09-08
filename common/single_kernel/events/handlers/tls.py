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
from ops import ConfigChangedEvent
from ops.charm import RelationBrokenEvent
from ops.framework import EventBase, EventSource, Object
from ops.model import BlockedStatus, MaintenanceStatus
from ops.pebble import Error

from ...core import RELATION_TLS_CLIENT, RELATION_TLS_PEER
from ...managers import BaseTLSManager, ClientTLSManager, PeerTLSManager
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class TLSRefreshCertificatesEvent(EventBase):
    """Event for refreshing TLS certificates."""


class TLSEventHandler(Object, ABC):
    """Class to deal with the TLS events."""

    refresh_event = EventSource(TLSRefreshCertificatesEvent)
    relation_name: str

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: BaseTLSManager):
        """Initialize the class attributes."""
        super().__init__(charm, self.relation_name)
        self._charm = charm
        self._helpers = helpers
        self._manager = manager

        cert_common = f"{charm.unit.name}.{charm.app.name}"
        cert_request = CertificateRequestAttributes(cert_common)

        self._requirer = TLSCertificatesRequiresV4(
            charm=charm,
            relationship_name=self.relation_name,
            certificate_requests=[cert_request],
            refresh_events=[self.refresh_event],
            private_key=self._parse_private_key(),
        )

        self.framework.observe(
            self._charm.on.config_changed,
            self._on_config_changed,
        )
        self.framework.observe(
            self._requirer.on.certificate_available,
            self._on_certificate_available,
        )
        self.framework.observe(
            self._charm.on[self.relation_name].relation_broken,
            self._on_relation_broken,
        )

    @abstractmethod
    def _parse_private_key(self) -> PrivateKey | None:
        """Parse the private key from the config."""
        raise NotImplementedError()

    @abstractmethod
    def _on_config_changed(self, event: ConfigChangedEvent):
        """Event handler for the config-changed event."""
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

        self._charm.unit.status = MaintenanceStatus("Enabling TLS")
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
            self._charm.unit.status = BlockedStatus("Failed to enable TLS")
            logger.error(e)
            return

    def _on_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Event handler for the relation-broken event."""
        self._charm.unit.status = MaintenanceStatus("Disabling TLS")

        try:
            self._manager.disable()
        except RuntimeError as e:
            self._charm.unit.status = BlockedStatus("Failed to disable TLS")
            logger.error(e)
            return

        if self._charm.unit.is_leader():
            self._manager.delete_private_key_uri()

        self._charm.unit.status = self._helpers.build_unit_status()


class TLSClientEventHandler(TLSEventHandler):
    """Class to deal with the TLS events."""

    relation_name = RELATION_TLS_CLIENT

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: ClientTLSManager):
        """Initialize the class attributes."""
        super().__init__(charm, helpers, manager)

    def _parse_private_key(self) -> PrivateKey | None:
        """Parse the private key from the config."""
        if not self._charm.config.tls_client_private_key:
            return

        try:
            private_key = self._charm.secret_store.get_value(
                secret_id=self._charm.config.tls_client_private_key,
                secret_key="private-key",
            )
        except ValueError as e:
            logger.warning(f"Failed to fetch secret: {e}")
            return

        return self._manager.parse_private_key(private_key)

    def _on_config_changed(self, event: ConfigChangedEvent):
        """Event handler for the config-changed event."""
        new_uri = self._charm.config.tls_client_private_key
        old_uri = self._manager.get_private_key_uri()

        if new_uri == old_uri:
            return

        if self._charm.refreshing:
            logger.debug(f"Deferring {self._manager.type} TLS rotation: charm is refreshing")
            event.defer()
            return

        self.refresh_event.emit()
        if self._charm.unit.is_leader():
            self._manager.set_private_key_uri(new_uri)

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Event handler for the certificate-available event."""
        super()._on_certificate_available(event)


class TLSPeerEventHandler(TLSEventHandler):
    """Class to deal with the TLS events."""

    relation_name = RELATION_TLS_PEER

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: PeerTLSManager):
        """Initialize the class attributes."""
        super().__init__(charm, helpers, manager)

    def _parse_private_key(self) -> PrivateKey | None:
        """Parse the private key from the config."""
        if not self._charm.config.tls_peer_private_key:
            return

        try:
            private_key = self._charm.secret_store.get_value(
                secret_id=self._charm.config.tls_peer_private_key,
                secret_key="private-key",
            )
        except ValueError as e:
            logger.warning(f"Failed to fetch secret: {e}")
            return

        return self._manager.parse_private_key(private_key)

    def _on_config_changed(self, event: ConfigChangedEvent):
        """Event handler for the config-changed event."""
        new_uri = self._charm.config.tls_peer_private_key
        old_uri = self._manager.get_private_key_uri()

        if new_uri == old_uri:
            return

        if self._charm.refreshing:
            logger.debug(f"Deferring {self._manager.type} TLS rotation: charm is refreshing")
            event.defer()
            return

        self.refresh_event.emit()
        if self._charm.unit.is_leader():
            self._manager.set_private_key_uri(new_uri)

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Event handler for the certificate-available event."""
        super()._on_certificate_available(event)
        self._helpers.rolling.callbacks.request_async_lock(callback_id="replication")
