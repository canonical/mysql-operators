# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from random import choice
from string import ascii_lowercase
from tempfile import NamedTemporaryFile
from typing import Iterator

from botocore.exceptions import ClientError
from charmlibs.pathops import PathProtocol
from mysql_shell import ClusterStatus, ExecutionError

from ...clients import MySQLClusterClient, MySQLInstanceClient
from ...state import BackupState
from ...workload import BaseSystem
from .backup_list import BackupListHelper
from .storage import BaseBackupStorage

logger = logging.getLogger(__name__)


class BackupManager:
    """Class to deal with the MySQL server backups."""

    backup_dir_prefix = "xtra_backup"
    state_dir_prefix = "#mysql_sst"

    def __init__(
        self,
        state: BackupState,
        system: BaseSystem,
        storage: BaseBackupStorage,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system
        self._storage = storage

        self._cluster_helper = cluster_client
        self._instance_helper = instance_client
        self._list_helper = BackupListHelper()

    def _create_temporary_ca(self) -> PathProtocol | None:
        """Create a temporary CA file and returns its location."""
        ca_chain = self._storage.ca_chain
        if not ca_chain:
            return

        temp_dir = self._create_temporary_dir(self._storage.certs_dir_name)
        temp_file = temp_dir / self._storage.certs_file_name
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

    def check_cluster(self) -> None:
        """Check the MySQL cluster health."""
        status = self._cluster_helper.fetch_status()

        if status not in (ClusterStatus.OK, ClusterStatus.OK_PARTIAL):
            raise RuntimeError("Cluster is not in a healthy state")

    def check_instances(self) -> None:
        """Check the MySQL instances health."""
        instances = self._cluster_helper.fetch_instances()

        selectors = [
            lambda i: "Instance has offline_mode enabled" in i.get("instanceErrors", ""),
            lambda i: i.get("hiddenFromRouter"),
        ]

        for instance in instances.values():
            for selector in selectors:
                if not selector(instance):
                    raise RuntimeError("Instances are not in a healthy state")

    def build_backup_path(self) -> str:
        """Build the backup path."""
        datetime_now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        backup_path = f"{self._storage.bucket_path}/{datetime_now}"

        return backup_path

    def check_backup(self, backup_path: str) -> None:
        """Check the backup file existence."""
        logger.info(f"Checking backup file at {self._storage.bucket_name}:{backup_path}")

        with self._temporary_file(self._storage.ca_chain) as ca_chain_file:
            client = self._storage.build_backup_client(ca_chain_file)

            try:
                client.get_object(
                    Bucket=self._storage.bucket_name,
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

        upload_args = self._storage.build_backup_args(ca_chain_path)
        upload_env = self._storage.build_backup_env()

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
            f"--parallel=10",
            f"--md5",
            f"--storage={self._storage.name}",
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

        download_args = self._storage.build_backup_args(ca_chain_path)
        download_env = self._storage.build_backup_env()

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
            f"--parallel=10",
            f"--storage={self._storage.name}",
            *download_args,
            f"{self._storage.bucket_path}/{backup_id}",
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
        logger.info(f"Listing backups in {self._storage.bucket_name}:{self._storage.bucket_path}")

        with self._temporary_file(self._storage.ca_chain) as ca_chain_file:
            client = self._storage.build_backup_client(ca_chain_file)

            try:
                pages = client.get_paginator("list_objects_v2").paginate(
                    Bucket=self._storage.bucket_name,
                    Prefix=self._storage.bucket_path,
                    Delimiter="/",
                )
            except ClientError as e:
                logger.error(f"Failed to list backups: {e}")
                raise

            backups = self._list_helper.collect_backups(self._storage.bucket_path, pages)
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

    def prepare_instance(self, setup: bool) -> None:
        """Prepare the MySQL instance for backup (setup / teardown)."""
        instances = self._cluster_helper.fetch_instances()
        if len(instances) == 1:
            return

        if setup:
            setup_flag = str(True).lower()
            clean_flag = str(False).lower()
            offline_flag = "ON"
        else:
            setup_flag = str(False).lower()
            clean_flag = str(True).lower()
            offline_flag = "OFF"

        self._cluster_helper.set_instance_option("tag:_hidden", setup_flag)

        try:
            logger.info("Setting instance offline")
            self._instance_helper.update_variable("offline_mode", offline_flag)
        except ExecutionError:
            self._cluster_helper.set_instance_option("tag:_hidden", clean_flag)
            raise

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

    def upload_file(self, contents: str, path: str) -> None:
        """Upload the contents to the provided bucket path."""
        logger.info(f"Uploading file to {self._storage.bucket_name}:{path}")

        with (
            self._temporary_file(self._storage.ca_chain) as ca_chain_file,
            self._temporary_file(contents) as contents_file,
        ):
            client = self._storage.build_backup_client(ca_chain_file)

            try:
                client.upload_file(
                    Bucket=self._storage.bucket_name,
                    Filename=contents_file,
                    Key=path,
                )
            except ClientError as e:
                logger.error(f"Failed to upload file: {e}")
                raise
