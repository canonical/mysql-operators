# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import (
    ConfigChangedEvent,
    InstallEvent,
    LeaderElectedEvent,
    LeaderSettingsChangedEvent,
    StartEvent,
    StorageDetachingEvent,
    UpdateStatusEvent,
)
from ops.framework import Object
from ops.model import BlockedStatus, ModelError, Unit, WaitingStatus

from ...core import (
    PASSWORD_KEY_BACKUPS,
    PASSWORD_KEY_MONITOR,
    PASSWORD_KEY_OPERATOR,
    PASSWORD_KEY_REPLICATION,
    RELATION_PEERS,
    ROLENAME_BACKUPS,
    ROLENAME_MONITOR,
    ROLENAME_ROUTER,
    USERNAME_BACKUPS,
    USERNAME_MONITOR,
    USERNAME_OPERATOR,
    USERNAME_REPLICATION,
    USERNAME_TO_PASSWORD_KEY,
)
from ...managers import LifecycleManager, SystemUser
from ...state import PeerStateUnit
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class LifecycleEventHandler(Object):
    """Class to deal with the operator lifecycle events."""

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: LifecycleManager):
        """Initialize the class attributes."""
        super().__init__(charm, "lifecycle")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.leader_settings_changed, self._on_leader_settings_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        self.framework.observe(self.on.archive_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.data_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.logs_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.temp_storage_detaching, self._on_storage_detaching)

    def _find_leader_unit(self) -> Unit | None:
        """Find the leader unit."""
        peers_relation = self._charm.model.get_relation(RELATION_PEERS)
        if not peers_relation:
            return None

        for unit in peers_relation.units:
            unit_state = PeerStateUnit(peers_relation.data[unit])
            if unit_state.get_unit_leader_flag():
                return unit

        return None

    def _setup_exporter_service(self) -> None:
        """Set up the MySQL Exporter workload service."""
        monitor_username = USERNAME_MONITOR
        monitor_password = self._charm.secret_store.get_value(
            secret_label=self._charm.secret_label,
            secret_key=PASSWORD_KEY_MONITOR,
        )

        logger.info("Starting MySQL Exporter service")
        self._charm.service_exporter.setup(monitor_username, monitor_password)
        self._charm.service_exporter.start()

    def _setup_server_service(self) -> None:
        """Set up the MySQL Server workload service."""
        backups_username = USERNAME_BACKUPS
        backups_password = self._charm.secret_store.get_value(
            secret_label=self._charm.secret_label,
            secret_key=PASSWORD_KEY_BACKUPS,
        )

        monitor_username = USERNAME_MONITOR
        monitor_password = self._charm.secret_store.get_value(
            secret_label=self._charm.secret_label,
            secret_key=PASSWORD_KEY_MONITOR,
        )

        operator_username = USERNAME_OPERATOR
        operator_password = self._charm.secret_store.get_value(
            secret_label=self._charm.secret_label,
            secret_key=PASSWORD_KEY_OPERATOR,
        )

        replication_username = USERNAME_REPLICATION
        replication_password = self._charm.secret_store.get_value(
            secret_label=self._charm.secret_label,
            secret_key=PASSWORD_KEY_REPLICATION,
        )

        logger.debug("Starting MySQL Server service")
        self._charm.service_server.setup(operator_username, operator_password)
        self._charm.service_server.start()

        logger.debug("Configuring MySQL Server service cluster options")
        self._manager.configure_instance(replication_username, replication_password)

        logger.debug("Configuring MySQL Server service auth options")
        self._manager.install_system_components(self._charm.config.plugin_audit_enabled)
        self._manager.create_system_roles(ROLENAME_ROUTER)
        self._manager.create_system_users([
            SystemUser(backups_username, backups_password, [ROLENAME_BACKUPS]),
            SystemUser(monitor_username, monitor_password, [ROLENAME_MONITOR]),
        ])

    def _update_passwords(self) -> None:
        """Update the application passwords if they do not exist."""
        try:
            passwords = self._charm.secret_store.get_content(secret_label=self._charm.secret_label)
        except ValueError as e:
            logger.warning(f"Failed to fetch application passwords: {e}")
            passwords = {}

        for key in USERNAME_TO_PASSWORD_KEY.values():
            if key not in passwords:
                passwords[key] = self._manager.create_system_password()

        self._charm.secret_store.set_content(passwords, secret_label=self._charm.secret_label)

    def _update_state(self) -> None:
        """Update the unit state depending on the unit role."""
        if self._charm.unit.is_leader():
            self._manager.recreate_cluster(self._charm.get_unit_label(self._charm.unit))
            self._manager.update_state("PRIMARY", "ONLINE")
        else:
            self._charm.unit.status = WaitingStatus("Waiting to join the cluster")
            self._manager.update_state("SECONDARY", "waiting")

        try:
            self._charm.unit.set_ports(3306, 33060)
        except ModelError as e:
            logger.warning(f"Failed to open the unit ports: {e}")
            return

    def _on_install(self, _: InstallEvent) -> None:
        """Event handler for the install event."""
        try:
            self._charm.service_server.install()
            self._charm.service_exporter.install()
        except Exception:
            self._charm.unit.status = BlockedStatus("Failed to install and configure MySQL")
        else:
            self._charm.unit.status = WaitingStatus("Waiting to start MySQL")

    def _on_start(self, event: StartEvent) -> None:
        """Event handler for the start event."""
        if not self._charm.system.ready:
            logger.debug("Deferring operator start: system not ready")
            event.defer()
            return

        # Create the services as early as possible in the charm lifecycle so that
        # runtime issues (e.g. a missing `juju trust`) surface before the workload is initialized.
        if self._charm.unit.is_leader():
            if not self._charm.create_app_services():
                self._charm.unit.status = BlockedStatus("Run `juju trust <app-name>`")
                event.defer()
                return

        if self._charm.service_server.initialized:
            logger.debug("Skipping setup: server is already initialized")
            self._charm.service_server.start()
            self._charm.service_exporter.start()
            self._update_state()
            return

        logger.info("Setting up operator services")
        self._setup_server_service()
        self._setup_exporter_service()
        self._update_state()

    def _on_leader_elected(self, _: LeaderElectedEvent) -> None:
        """Event handler for the leader-elected event."""
        logger.info("Updating system user passwords")
        self._update_passwords()

        self._manager.set_leader_flag(True)
        self._manager.set_cluster_name(self._charm.config.cluster_name)
        self._manager.set_cluster_set_name(self._charm.config.cluster_set_name)

    def _on_leader_settings_changed(self, _: LeaderSettingsChangedEvent) -> None:
        """Event handler for the leader-settings-changed event."""
        self._manager.set_leader_flag(False)

    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Event handler for the config-changed event."""
        if self._charm.refreshing:
            logger.debug("Skipping config change: charm is refreshing")
            return

        self._helpers.apply_config()

    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Event handler for the update-status event."""
        if not self._helpers.initialized:
            logger.debug("Skipping update status: charm not initialized")
            return

        try:
            self._manager.update_state()
        except RuntimeError as e:
            logger.warning(f"Failed to update the unit state: {e}")

        if not isinstance(self._charm.unit.status, BlockedStatus):
            self._charm.unit.status = self._helpers.build_unit_status()
        if not isinstance(self._charm.app.status, BlockedStatus):
            self._charm.app.status = self._helpers.build_app_status()

    def _on_storage_detaching(self, _: StorageDetachingEvent) -> None:
        """Event handler for the storage-detaching event."""
        if not self._helpers.initialized:
            logger.debug("Skipping storage detaching: charm is not initialized")
            return

        leader_unit = self._find_leader_unit()

        try:
            # Preemptively switch primary to the leader
            if leader_unit:
                self._manager.promote_instance(self._charm.get_unit_address(leader_unit))
        except RuntimeError as e:
            logger.warning(f"Skipping storage detaching: {e}")
            return

        instance_host = self._charm.get_unit_address(self._charm.unit)
        instance_label = self._charm.get_unit_label(self._charm.unit)

        self._manager.remove_instance(
            instance_label=instance_label,
            instance_host=instance_host,
        )
