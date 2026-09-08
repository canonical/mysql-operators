# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from abc import ABC, abstractmethod
from datetime import datetime

from object_storage.s3 import S3Requirer
from ops.charm import ActionEvent
from ops.framework import Object
from ops.model import MaintenanceStatus

from ...core import (
    PASSWORD_KEY_BACKUPS,
    RELATION_BACKUPS,
    USERNAME_BACKUPS,
)
from ...managers import BaseBackupManager, S3BackupManager
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class BackupEventHandler(Object, ABC):
    """Abstract class to deal with the database backup events."""

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: BaseBackupManager):
        """Initialize the class attributes."""
        super().__init__(charm, "backups")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager

        self.framework.observe(self._charm.on.create_backup_action, self._on_create_backup)
        self.framework.observe(self._charm.on.list_backups_action, self._on_list_backups)
        self.framework.observe(self._charm.on.restore_action, self._on_restore_backup)

    @abstractmethod
    def _configure(self) -> None:
        """Configure the backup storage."""
        raise NotImplementedError()

    def _build_backup_metadata(self, request_time: str) -> str:
        """Build the backup metadata."""
        return (
            f"Date Backup Requested: {request_time}\n"
            f"Model Name: {self._charm.model.name}\n"
            f"App Name: {self._charm.model.app.name}\n"
            f"Unit Name: {self._charm.unit.name}\n"
            f"Juju Version: {self._charm.model.juju_version}\n"
        )

    def _on_create_backup(self, event: ActionEvent) -> None:
        """Event handler for the create-backup action."""
        if not self._charm.model.get_relation(RELATION_BACKUPS):
            event.fail(f"Skipping backup creation: missing {RELATION_BACKUPS} relation")
            return
        if not self._helpers.initialized:
            event.fail(f"Skipping backup creation: charm is not initialized")
            return
        if self._charm.refreshing:
            event.fail(f"Skipping backup creation: charm is refreshing")
            return

        force = event.params.get("force", False)

        try:
            self._manager.check_cluster()
            self._manager.check_instance()
        except RuntimeError as e:
            if not force:
                logger.error(f"Backup cannot be created: {e}")
                event.fail(f"Backup cannot be created: {e}")
                return

        request_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        backup_path = f"{self._manager._storage.bucket_path}/{request_time}"
        backup_meta = self._build_backup_metadata(request_time)

        try:
            self._manager.upload_file(backup_meta, f"{backup_path}.metadata")
        except Exception as e:
            logger.error(f"Failed to upload metadata: {e}")
            event.fail(f"Failed to upload metadata: {e}")
            return

        with self._manager.isolate_instance(revert=True):
            username = USERNAME_BACKUPS
            password = self._charm.secret_store.get_value(
                secret_label=self._charm.secret_label,
                secret_key=PASSWORD_KEY_BACKUPS,
            )

            try:
                _________ = self._charm.unit.status = MaintenanceStatus("Creating backup")
                output, _ = self._manager.create_backup(backup_path, username, password)
            except (OSError, RuntimeError) as e:
                logger.error(f"Failed to create backup: {e}")
                event.fail(f"Failed to create backup: {e}")
                return

            try:
                self._manager.upload_file(output, f"{backup_path}.backup.log")
                self._manager.remove_backup()
            except RuntimeError as e:
                logger.error(f"Failed to upload backup logs: {e}")
                event.fail(f"Failed to upload backup logs: {e}")
                return

        logger.info(f"Created backup with ID {request_time}")
        event.set_results({"backup-id": request_time})

    def _on_list_backups(self, event: ActionEvent) -> None:
        """Event handler for the list-backups action."""
        if not self._charm.model.get_relation(RELATION_BACKUPS):
            event.fail(f"Skipping backup listing: missing {RELATION_BACKUPS} relation")
            return

        logger.info("Retrieving backup parameters")

        try:
            backups = self._manager.list_backups()
            event.set_results({"backups": backups})
        except Exception as e:
            logger.error(f"Failed to retrieve backups: {e}")
            event.fail(f"Failed to retrieve backups: {e}")

    def _on_restore_backup(self, event: ActionEvent) -> None:
        """Event handler for the restore-backup action."""
        if not self._charm.model.get_relation(RELATION_BACKUPS):
            event.fail(f"Skipping backup restoration: missing {RELATION_BACKUPS} relation")
            return
        if not self._helpers.initialized:
            event.fail(f"Skipping backup restoration: charm is not initialized")
            return
        if self._charm.refreshing:
            event.fail(f"Skipping backup restoration: charm is refreshing")
            return
        if self._charm.app.planned_units() > 1:
            event.fail(f"Skipping backup restoration: charm has more than one unit")
            return

        backup_id = event.params.get("backup-id", "")
        backup_id = backup_id.strip().strip("/")
        if not backup_id:
            event.fail("Skipping backup restoration: missing ID")
            return

        backup_path = f"{self._manager._storage.bucket_path}/{backup_id}.md5"
        buffer_pool = self._helpers.config.calculate_buffer_pool()

        try:
            self._manager.check_backup(backup_path)
        except Exception as e:
            logger.error(f"Failed to check for backup existence: {e}")
            event.fail(f"Failed to check for backup existence: {e}")
            return

        with self._manager.isolate_instance(revert=False):
            try:
                ____________ = self._charm.unit.status = MaintenanceStatus("Downloading backup")
                output, path = self._manager.download_backup(backup_id)
                ____________ = self._manager.prepare_backup(path, buffer_pool)
            except RuntimeError as e:
                logger.error(f"Failed to download backup: {e}")
                event.fail(f"Failed to download backup: {e}")
                return

            try:
                self._charm.unit.status = MaintenanceStatus("Restoring backup")
                self._manager.reset_data_dir()
                self._manager.reset_logs_dir()
                self._manager.restore_backup(path)
                self._manager.reset_temp_dir()
            except RuntimeError as e:
                logger.error(f"Failed to restore backup: {e}")
                event.fail(f"Failed to restore backup: {e}")
                return

        try:
            self._manager.recreate_cluster(self._charm.get_unit_label(self._charm.unit))
        except RuntimeError as e:
            logger.error(f"Failed to recreate cluster: {e}")
            event.fail(f"Failed to recreate cluster: {e}")
            return

        logger.info(f"Restored backup with ID {backup_id}")
        event.set_results({"completed": "ok"})


class BackupS3EventHandler(BackupEventHandler):
    """Class to deal with the database backup events."""

    def __init__(self, charm: BaseCharm, helpers: EventHelpers, manager: S3BackupManager):
        """Initialize the class attributes."""
        super().__init__(charm, helpers, manager)
        self._configure()

    def _configure(self) -> None:
        """Configure the backup storage."""
        requirer = S3Requirer(self._charm, RELATION_BACKUPS)
        config = requirer.get_storage_connection_info()
        if not config:
            logger.warning(f"Skipping backup configuration: relation {RELATION_BACKUPS} missing")
            return

        self._manager.configure(config)
