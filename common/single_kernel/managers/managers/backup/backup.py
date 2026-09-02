# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager, suppress
from pathlib import Path
from random import choice
from string import ascii_lowercase
from tempfile import NamedTemporaryFile
from typing import Iterator

from botocore.exceptions import ClientError
from charmlibs.pathops import PathProtocol
from mysql_shell.executors.errors import ExecutionError
from mysql_shell.models import ClusterStatus, InstanceRole, InstanceState

from ....state import PeerState
from ....workload import BaseSystem
from ...clients import Clients
from .backup_list import BackupListHelper
from .storage import BaseBackupStorage, S3BackupStorage

logger = logging.getLogger(__name__)


class BaseBackupManager(ABC):
    """Abstract class to deal with the backup classes."""

    backup_dir_prefix = "xtra_backup"
    state_dir_prefix = "#mysql_sst"

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._clients = clients
        self._list_helper = BackupListHelper()

    @property
    @abstractmethod
    def storage(self) -> BaseBackupStorage:
        """Return the backup storage."""
        raise NotImplementedError()

    @abstractmethod
    def configure(self, config: dict[str, str]) -> None:
        """Configure the backup storage."""
        raise NotImplementedError()

    def _create_temporary_ca(self) -> PathProtocol | None:
        """Create a temporary CA file and returns its location."""
        ca_chain = self.storage.ca_chain
        if not ca_chain:
            return

        temp_dir = self._create_temporary_dir(self.storage.certs_dir_name)
        temp_file = temp_dir / self.storage.certs_file_name
        temp_file.write_text(
            data=ca_chain,
            user=self._system.user,
            group=self._system.group,
        )

        return temp_file

    def _create_temporary_dir(self, prefix: str) -> PathProtocol:
        """Create a temporary directory and returns its location."""
        suffix = "".join(choice(ascii_lowercase) for _ in range(4))

        temp_dir = self._system.paths.mysql_temp / f"{prefix}_{suffix}"
        temp_dir.mkdir(
            exist_ok=True,
            user=self._system.user,
            group=self._system.group,
        )

        return temp_dir

    @contextmanager
    def _temporary_file(self, contents: str | None) -> Iterator[str | None]:
        """Create a temporary file with the provided contents."""
        if not contents:
            yield None
            return

        with NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(contents.encode())
            temp_file.flush()

        try:
            yield temp_file.name
        finally:
            Path(temp_file.name).unlink(missing_ok=True)

    @contextmanager
    def isolate_instance(self, revert: bool) -> Iterator[None]:
        """Wraps the desired operation in an isolated instance."""
        instances = self._clients.cluster.fetch_instances()
        if len(instances) == 1:
            return

        try:
            self._clients.cluster.set_instance_option("tag:_hidden", True)
            self._clients.instance.update_variable("offline_mode", "ON")
        except ExecutionError as e:
            logger.error(f"Failed to make instance isolated: {e}")
            return

        with suppress(Exception):
            yield
        if not revert:
            return

        try:
            self._clients.instance.update_variable("offline_mode", "OFF")
            self._clients.cluster.set_instance_option("tag:_hidden", False)
        except ExecutionError as e:
            logger.error(f"Failed to make instance accessible: {e}")
            return

    def check_cluster(self) -> None:
        """Check the MySQL cluster health."""
        instances = self._clients.cluster.fetch_instances()
        state = self._clients.cluster.fetch_state()

        if state not in [ClusterStatus.OK, ClusterStatus.OK_PARTIAL]:
            raise RuntimeError("Cluster is not in a healthy state")

        selectors = [
            lambda i: "Instance has offline_mode enabled" in i.get("instanceErrors", ""),
            lambda i: i.get("hiddenFromRouter"),
        ]

        for label, info in instances.keys():
            if all(selector(info) for selector in selectors):
                raise RuntimeError(f"Backup already in progress in instance {label}")

    def check_instance(self) -> None:
        """Check the MySQL instance health."""
        try:
            role = self._clients.instance.fetch_role()
            state = self._clients.instance.fetch_state()
            members = self._clients.instance.count_cluster_members()
        except ExecutionError as e:
            raise RuntimeError("Failed to check instance health") from e

        if role == InstanceRole.PRIMARY and members > 1:
            raise RuntimeError("Instance is the cluster primary")
        if state != InstanceState.ONLINE:
            raise RuntimeError("Instance is not in a healthy state")

    def check_backup(self, backup_path: str) -> None:
        """Check the backup file existence."""
        logger.info(f"Checking backup file at {self.storage.bucket_name}:{backup_path}")

        with self._temporary_file(self.storage.ca_chain) as ca_chain_file:
            client = self.storage.build_backup_client(ca_chain_file)

            try:
                client.get_object(
                    Bucket=self.storage.bucket_name,
                    Key=backup_path,
                    Range="0-1",
                )
            except ClientError as e:
                logger.error(f"Failed to check for backup existence: {e}")
                raise

    def create_backup(self, backup_path: str, username: str, password: str) -> tuple[str, str]:
        """Create a backup file and returns the output + path."""
        cores_num = self._system.runtime.get_cores()

        try:
            ca_chain_path = self._create_temporary_ca()
            temp_dir_path = self._create_temporary_dir(self.backup_dir_prefix)
        except (OSError, RuntimeError) as e:
            logger.error(f"Failed to create backup: {e}")
            raise

        upload_args = self.storage.build_backup_args(ca_chain_path)
        upload_env = self.storage.build_backup_env()

        backup_command = [
            f"{self._system.paths.binary('xtrabackup')}",
            f"--defaults-file={self._system.paths.mysql_config_default}",
            f"--defaults-group=mysqld",
            f"--parallel={cores_num}",
            f"--user={username}",
            f"--password={password}",
            f"--socket={self._system.paths.mysql_socket}",
            f"--lock-ddl",
            f"--backup",
            f"--stream=xbstream",
            f"--xtrabackup-plugin-dir={self._system.paths.backup_plugins}",
            f"--target-dir={temp_dir_path}",
            f"--no-version-check",
            f"--no-server-version-check",
        ]

        upload_command = [
            f"{self._system.paths.binary('xbcloud')}",
            f"put",
            f"--curl-retriable-errors=7",
            f"--insecure",
            f"--parallel={cores_num}",
            f"--md5",
            f"--storage={self.storage.name}",
            *upload_args,
            backup_path,
        ]

        logger.info(f"Creating backup in {temp_dir_path}")

        try:
            with (
                self._system.shell.execute_async(backup_command) as backup,
                self._system.shell.execute_async(upload_command, upload_env, backup) as upload,
            ):
                output = upload.read()
                upload.close()
                backup.close()
        except RuntimeError as e:
            logger.error(f"Failed to create backup: {e}")
            raise
        else:
            return output, str(temp_dir_path)

    def download_backup(self, backup_id: str) -> tuple[str, str]:
        """Download a backup file and returns the output + path."""
        cores_num = self._system.runtime.get_cores()

        try:
            ca_chain_path = self._create_temporary_ca()
            temp_dir_path = self._create_temporary_dir(self.state_dir_prefix)
        except (OSError, RuntimeError) as e:
            logger.error(f"Failed to download backup: {e}")
            raise

        download_args = self.storage.build_backup_args(ca_chain_path)
        download_env = self.storage.build_backup_env()

        decompress_command = [
            f"{self._system.paths.binary('xbstream')}",
            f"--decompress",
            f"-x",
            f"--directory={temp_dir_path}",
            f"--parallel={cores_num}",
        ]

        download_command = [
            f"{self._system.paths.binary('xbcloud')}",
            f"get",
            f"--curl-retriable-errors=7",
            f"--parallel={cores_num}",
            f"--storage={self.storage.name}",
            *download_args,
            f"{self.storage.bucket_path}/{backup_id}",
        ]

        logger.info(f"Downloading backup in {temp_dir_path}")

        try:
            with (
                self._system.shell.execute_async(download_command, download_env) as download,
                self._system.shell.execute_async(decompress_command, {}, download) as decompress,
            ):
                output = decompress.read()
                decompress.close()
                download.close()
        except RuntimeError as e:
            logger.error(f"Failed to download backup: {e}")
            raise
        else:
            return output, str(temp_dir_path)

    def list_backups(self) -> str:
        """List all available backups."""
        logger.info(f"Listing backups in {self.storage.bucket_name}:{self.storage.bucket_path}")

        with self._temporary_file(self.storage.ca_chain) as ca_chain_file:
            client = self.storage.build_backup_client(ca_chain_file)

            try:
                pages = client.get_paginator("list_objects_v2").paginate(
                    Bucket=self.storage.bucket_name,
                    Prefix=self.storage.bucket_path,
                    Delimiter="/",
                )
            except ClientError as e:
                logger.error(f"Failed to list backups: {e}")
                raise

            backups = self._list_helper.collect_backups(self.storage.bucket_path, pages)
            backups = self._list_helper.format_backups(backups)
            return backups

    def prepare_backup(self, backup_path: str, pool_size: int) -> str:
        """Prepare the backup for restore."""
        logger.info(f"Preparing backup in {backup_path}")

        prepare_command = [
            f"{self._system.paths.binary('xtrabackup')}",
            f"--prepare",
            f"--use-memory={pool_size}",
            f"--rollback-prepared-trx",
            f"--xtrabackup-plugin-dir={self._system.paths.backup_plugins}",
            f"--target-dir={backup_path}",
            f"--no-version-check",
        ]

        try:
            return self._system.shell.execute_sync(prepare_command)
        except RuntimeError as e:
            logger.error(f"Failed to prepare backup: {e}")
            raise

    def recreate_cluster(self, instance_label: str) -> None:
        """Recreate cluster."""
        self._clients.configure_instance()
        self._clients.recreate_cluster(instance_label)

    def restore_backup(self, backup_path: str) -> str:
        """Restore the backup."""
        logger.info(f"Restoring backup from {backup_path}")

        restore_command = [
            f"{self._system.paths.binary('xtrabackup')}",
            f"--defaults-file={self._system.paths.mysql_config_default}",
            f"--defaults-group=mysqld",
            f"--datadir={self._system.paths.mysql_data}",
            f"--move-back",
            f"--force-non-empty-directories",
            f"--xtrabackup-plugin-dir={self._system.paths.backup_plugins}",
            f"--target-dir={backup_path}",
            f"--no-version-check",
        ]

        try:
            return self._system.shell.execute_sync(restore_command)
        except RuntimeError as e:
            logger.error(f"Failed to restore backup: {e}")
            raise

    def remove_backup(self) -> None:
        """Remove backup from the temp directory."""
        logger.info("Removing backup temp directory")

        try:
            self._system.shell.execute_sync([
                f"find",
                f"{self._system.paths.mysql_temp}",
                f"-name {self.backup_dir_prefix}_*",
                f"-maxdepth 1",
                f"-delete",
            ])
        except RuntimeError as e:
            logger.error(f"Failed to remove backup temp directory: {e}")
            raise

    def reset_data_dir(self) -> None:
        """Reset the MySQL data directory."""
        logger.info(f"Resetting data directory")

        try:
            self._system.shell.execute_sync([
                "find",
                f"{self._system.paths.mysql_data}",
                f"-not -path {self.state_dir_prefix}_*",
                f"-maxdepth 1",
                f"-delete",
            ])
        except RuntimeError as e:
            logger.error(f"Failed to reset data directory: {e}")
            raise

    def reset_logs_dir(self) -> None:
        """Reset the MySQL logs directory."""
        logger.info(f"Resetting logs directory")

        try:
            self._system.shell.execute_sync([
                "find",
                f"{self._system.paths.mysql_logs}",
                f"-maxdepth 1",
                f"-delete",
            ])
        except RuntimeError as e:
            logger.error(f"Failed to reset logs directory: {e}")
            raise

    def reset_temp_dir(self) -> None:
        """Reset the MySQL temp directory."""
        logger.info(f"Resetting temp directory")

        try:
            self._system.shell.execute_sync([
                "find",
                f"{self._system.paths.mysql_temp}",
                f"-maxdepth 1",
                f"-delete",
            ])
        except RuntimeError as e:
            logger.error(f"Failed to reset temp directory: {e}")
            raise

    def upload_file(self, contents: str, path: str) -> None:
        """Upload the contents to the provided bucket path."""
        logger.info(f"Uploading file to {self.storage.bucket_name}:{path}")

        with (
            self._temporary_file(self.storage.ca_chain) as ca_chain_file,
            self._temporary_file(contents) as contents_file,
        ):
            client = self.storage.build_backup_client(ca_chain_file)

            try:
                client.upload_file(
                    Bucket=self.storage.bucket_name,
                    Filename=contents_file,
                    Key=path,
                )
            except ClientError as e:
                logger.error(f"Failed to upload file: {e}")
                raise


class S3BackupManager(BaseBackupManager):
    """Class to deal with the S3 backup classes."""

    def __init__(self, state: PeerState, system: BaseSystem, clients: Clients):
        """Initialize the class attributes."""
        super().__init__(state, system, clients)
        self._storage = None

    @property
    def storage(self) -> S3BackupStorage:
        """Configure the backup storage."""
        if not self._storage:
            raise RuntimeError("The backup storage is not configured")

        return self._storage

    def configure(self, config: dict[str, str]) -> None:
        """Configure the backup storage."""
        self._storage = S3BackupStorage(config)
