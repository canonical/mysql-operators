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
from ops.model import ActiveStatus, BlockedStatus, ModelError, Unit, WaitingStatus

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

        self.framework.observe(self._charm.on.install, self._on_install)
        self.framework.observe(self._charm.on.start, self._on_start)
        self.framework.observe(self._charm.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self._charm.on.leader_settings_changed, self._on_leader_changed)
        self.framework.observe(self._charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self._charm.on.update_status, self._on_update_status)

        self.framework.observe(self._charm.on.archive_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self._charm.on.data_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self._charm.on.logs_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self._charm.on.temp_storage_detaching, self._on_storage_detaching)

    def _create_passwords(self) -> None:
        """Create the application passwords."""
        password_keys = USERNAME_TO_PASSWORD_KEY.values()

        logger.info("Creating application passwords")
        self._charm.secret_store.create(
            content={key: self._manager.create_system_password() for key in password_keys},
            secret_label=self._charm.secret_label,
        )

    def _fetch_passwords(self) -> dict[str, str]:
        """Fetch the application passwords."""
        try:
            passwords = self._charm.secret_store.get_content(secret_label=self._charm.secret_label)
        except ValueError as e:
            logger.warning(f"Failed to fetch application passwords: {e}")
            passwords = {}

        return passwords

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

    def _init_server_service(self) -> None:
        """Initialize the MySQL Server workload service."""
        if self._charm.config.plugin_audit_enabled:
            self._manager.install_system_components(["audit_log_filter"])
        else:
            self._manager.install_system_components([])

    def _start_server_service(self, passwords: dict[str, str]) -> None:
        """Start the MySQL Server workload service."""
        logger.info("Starting MySQL Server service")
        if self._charm.service_server.initialized:
            self._charm.service_server.start()
            self._init_server_service()
            return

        self._charm.service_server.setup(USERNAME_OPERATOR, passwords[PASSWORD_KEY_OPERATOR])
        self._charm.service_server.start()
        self._init_server_service()

        logger.info("Configuring MySQL Server auth options")
        self._manager.create_system_roles(ROLENAME_ROUTER)
        self._manager.create_system_users([
            SystemUser(USERNAME_BACKUPS, passwords[PASSWORD_KEY_BACKUPS], [ROLENAME_BACKUPS]),
            SystemUser(USERNAME_MONITOR, passwords[PASSWORD_KEY_MONITOR], [ROLENAME_MONITOR]),
        ])

        replication_label = self._charm.get_unit_label(self._charm.unit)
        replication_username = USERNAME_REPLICATION
        replication_password = passwords[PASSWORD_KEY_REPLICATION]

        logger.info("Configuring MySQL Server cluster options")
        if self._charm.unit.is_leader():
            self._manager.configure_instance(replication_username, replication_password)
            self._manager.recreate_cluster(replication_label)
        else:
            self._manager.configure_instance(replication_username, replication_password)

    def _start_exporter_service(self, passwords: dict[str, str]) -> None:
        """Start the MySQL Exporter workload service."""
        logger.info("Starting MySQL Exporter service")
        self._charm.service_exporter.setup(USERNAME_MONITOR, passwords[PASSWORD_KEY_MONITOR])
        self._charm.service_exporter.start()

    def _update_state(self) -> None:
        """Update the unit state depending on the unit role."""
        if self._charm.unit.is_leader():
            self._manager.update_state("PRIMARY", "ONLINE")
            self._charm.unit.status = ActiveStatus("Primary")
        else:
            self._manager.update_state("SECONDARY", "waiting")
            self._charm.unit.status = WaitingStatus("Waiting to join the cluster")

        try:
            self._charm.unit.set_ports(self._charm.service_server.port)
        except ModelError as e:
            logger.warning(f"Failed to open the unit ports: {e}")
            return

    def _on_install(self, _: InstallEvent) -> None:
        """Event handler for the install event."""
        try:
            self._charm.service_server.install()
            self._charm.service_exporter.install()
        except Exception:
            self._charm.unit.status = BlockedStatus("Failed to install MySQL")
        else:
            self._charm.unit.status = WaitingStatus("Waiting to start MySQL")

    def _on_start(self, event: StartEvent) -> None:
        """Event handler for the start event."""
        if not self._charm.system.ready:
            logger.debug("Deferring operator start: system not ready")
            event.defer()
            return

        passwords = self._fetch_passwords()
        if not passwords:
            logger.debug("Deferring operator start: passwords not ready")
            event.defer()
            return

        # Create the services as early as possible in the charm lifecycle so that
        # runtime issues (e.g. a missing `juju trust`) surface before the workload is initialized.
        if self._charm.unit.is_leader():
            if not self._charm.create_app_services():
                self._charm.unit.status = BlockedStatus("Run `juju trust <app-name>`")
                event.defer()
                return

        self._helpers.config.save_config()
        self._start_server_service(passwords)
        self._start_exporter_service(passwords)
        self._update_state()

    def _on_leader_elected(self, _: LeaderElectedEvent) -> None:
        """Event handler for the leader-elected event."""
        passwords = self._fetch_passwords()
        if not passwords:
            self._create_passwords()

        self._manager.set_leader_flag(True)
        self._manager.set_cluster_name(self._charm.config.cluster_name)
        self._manager.set_cluster_set_name(self._charm.config.cluster_set_name)

    def _on_leader_changed(self, _: LeaderSettingsChangedEvent) -> None:
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

        self._manager.update_state()
        self._charm.update_app_labels()
        self._charm.unit.status = self._helpers.build_unit_status()

    def _on_storage_detaching(self, _: StorageDetachingEvent) -> None:
        """Event handler for the storage-detaching event."""
        if not self._helpers.initialized:
            logger.debug("Skipping storage detaching: charm is not initialized")
            return

        leader_unit = self._find_leader_unit()
        leader_host = self._charm.get_unit_address(leader_unit or self._charm.unit)

        try:
            # Preemptively switch primary to the leader
            if self._manager.is_cluster_primary:
                self._manager.promote_instance(leader_host)
        except RuntimeError as e:
            logger.debug(f"Skipping storage detaching: {e}")
            return

        instance_host = self._charm.get_unit_address(self._charm.unit)
        instance_label = self._charm.get_unit_label(self._charm.unit)

        self._manager.remove_instance(
            instance_label=instance_label,
            instance_host=instance_host,
            addrs=[leader_host],
        )
