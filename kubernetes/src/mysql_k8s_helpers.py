#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper class to manage the MySQL InnoDB cluster lifecycle with MySQL Shell."""

import logging
from collections import deque
from collections.abc import Iterable
from typing import TYPE_CHECKING

import jinja2
from charms.mysql.v0.mysql import (
    ADMIN_PORT,
    Error,
    MySQLBase,
    MySQLExecError,
    MySQLGetClusterEndpointsError,
    MySQLServiceNotRunningError,
    MySQLStartMySQLDError,
    MySQLStopMySQLDError,
)
from ops.model import Container
from ops.pebble import APIError, ChangeError, ExecError, PathError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_fixed,
)

from constants import (
    CHARMED_MYSQL_XBCLOUD_LOCATION,
    CHARMED_MYSQL_XBSTREAM_LOCATION,
    CHARMED_MYSQL_XTRABACKUP_LOCATION,
    CONTAINER_NAME,
    LOG_ROTATE_CONFIG_FILE,
    MYSQL_ARCHIVE_DIR,
    MYSQL_BINLOGS_COLLECTOR_SERVICE,
    MYSQL_DATA_DIR,
    MYSQL_LOG_ERROR,
    MYSQL_LOGS_DIR,
    MYSQL_SYSTEM_GROUP,
    MYSQL_SYSTEM_USER,
    MYSQL_TEMP_DIR,
    MYSQLD_DEFAULTS_CONFIG_FILE,
    MYSQLD_INIT_CONFIG_FILE,
    MYSQLD_LOCATION,
    MYSQLD_SERVICE,
    MYSQLD_SOCK_FILE,
    MYSQLSH_LOCATION,
    PEER,
    XTRABACKUP_PLUGIN_DIR,
)
from k8s_helpers import KubernetesClientError, KubernetesHelpers
from mysql_k8s_executor import ContainerExecutor, ExecutionError
from utils import any_memory_to_bytes

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from charm import MySQLOperatorCharm


class MySQLInitialiseMySQLDError(Error):
    """Exception raised when there is an issue initialising an instance."""


class MySQLWaitUntilUnitRemovedFromClusterError(Error):
    """Exception raised when there is an issue checking if a unit is removed from the cluster."""


class MySQLExecuteBackupCommandsError(Error):
    """Exception raised when there is an error executing the backup commands.

    The backup commands are executed in the workload container using the pebble API.
    """


class MySQLRetrieveBackupWithXBCloudError(Error):
    """Exception raised when there is an error retrieving a backup from S3 with xbcloud."""


class MySQLPrepareBackupForRestoreError(Error):
    """Exception raised when there is an error preparing a backup for restore."""


class MySQLRestoreBackupError(Error):
    """Exception raised when there is an error restoring a backup."""


class MySQLDeleteTempBackupDirectoryError(Error):
    """Exception raised when there is an error deleting the temp backup directory."""


class MySQL(MySQLBase):
    """Class to encapsulate all operations related to the MySQL instance and cluster.

    This class handles the configuration of MySQL instances, and also the
    creation and configuration of MySQL InnoDB clusters via Group Replication.
    """

    def __init__(
        self,
        instance_address: str,
        cluster_name: str,
        cluster_set_name: str,
        operator_user: str,
        operator_password: str,
        replication_user: str,
        replication_password: str,
        monitoring_user: str,
        monitoring_password: str,
        backups_user: str,
        backups_password: str,
        container: Container,
        k8s_helper: KubernetesHelpers,
        charm: "MySQLOperatorCharm",
    ):
        """Initialize the MySQL class.

        Args:
            instance_address: address of the targeted instance
            cluster_name: cluster name
            cluster_set_name: cluster set name
            operator_user: user name for the server config user
            operator_password: password for the server config user
            replication_user: user name for the cluster admin user
            replication_password: password for the cluster admin user
            monitoring_user: user name for the monitoring user
            monitoring_password: password for the monitoring user
            backups_user: user name for the backups user
            backups_password: password for the backups user
            container: workload container object
            k8s_helper: KubernetesHelpers object
            charm: charm object
        """
        self.container = container
        self.k8s_helper = k8s_helper
        self.charm = charm

        super().__init__(
            instance_address=instance_address,
            socket_path=MYSQLD_SOCK_FILE,
            cluster_name=cluster_name,
            cluster_set_name=cluster_set_name,
            operator_user=operator_user,
            operator_password=operator_password,
            replication_user=replication_user,
            replication_password=replication_password,
            monitoring_user=monitoring_user,
            monitoring_password=monitoring_password,
            backups_user=backups_user,
            backups_password=backups_password,
            mysqlsh_path=MYSQLSH_LOCATION,
            executor_class=ContainerExecutor,
        )

    def _build_cluster_tcp_executor(self, host: str, port: int = 3306):
        """Build a TCP executor for the cluster operations."""
        executor = super()._build_cluster_tcp_executor(host=host, port=port)
        executor.set_container(self.container)
        return executor

    def _build_instance_tcp_executor(self, host: str, port: int = ADMIN_PORT):
        """Build a TCP executor for the instance operations."""
        executor = super()._build_instance_tcp_executor(host=host, port=port)
        executor.set_container(self.container)
        return executor

    def _build_instance_sock_executor(self):
        """Build a socket executor for the instance operations."""
        executor = super()._build_instance_sock_executor()
        executor.set_container(self.container)
        return executor

    @retry(reraise=True, stop=stop_after_delay(30), wait=wait_fixed(5))
    def initialise_mysqld(self) -> None:
        """Execute instance first run.

        Initialise mysql data directory and create blank password root@localhost user.
        Raises MySQLInitialiseMySQLDError if the instance bootstrap fails.
        """
        bootstrap_command = [
            MYSQLD_LOCATION,
            "--initialize",
            "-u",
            MYSQL_SYSTEM_USER,
            "--datadir",
            MYSQL_DATA_DIR,
            "--innodb-log-group-home-dir",
            MYSQL_LOGS_DIR,
            "--innodb-undo-directory",
            MYSQL_LOGS_DIR,
            "--innodb-temp-tablespaces-dir",
            MYSQL_TEMP_DIR,
        ]

        try:
            self.reset_data_dir()
            process = self.container.exec(
                command=bootstrap_command,
                user=MYSQL_SYSTEM_USER,
                group=MYSQL_SYSTEM_GROUP,
            )
            process.wait_output()
        except (ExecError, ChangeError, PathError, TimeoutError):
            logger.exception("Failed to initialise MySQL data directory")
            # Try to recover logs from the instance
            try:
                error_log_path, error_log_lines = self._recover_error_logs()
                logger.debug("Last lines of %s: \n%s", error_log_path, "".join(error_log_lines))
            except Exception:
                logger.exception("Could not recover contents of error.log")
            # List contents of relevant directories for easier debugging
            try:
                for path in MYSQL_DATA_DIR, MYSQL_LOGS_DIR, MYSQL_TEMP_DIR:
                    logger.debug(
                        "Contents of %s: %s",
                        path,
                        [f.name for f in self.container.list_files(path)],
                    )
            except Exception:
                logger.exception("Could not list contents of %s", path)

            raise MySQLInitialiseMySQLDError from None

    def _recover_error_logs(self, max_lines: int = 10) -> tuple[str, list[str]]:
        for error_log_path in {f"{MYSQL_LOGS_DIR}/error.log", "/var/log/mysql/error.log"}:
            if self.container.exists(error_log_path):
                error_log_reader = self.container.pull(error_log_path, encoding="utf-8")
                lines = deque(maxlen=max_lines)
                for line in error_log_reader:
                    lines.append(line)
            return error_log_path, list(lines)

        raise RuntimeError("No error.log file found in expected locations")

    def set_operator_user_and_start_mysqld(self) -> None:
        """Set the operator user and start mysqld."""
        create_user_queries = [
            f"CREATE USER '{self.operator_user}'@'%' IDENTIFIED BY '{self.operator_password}';",
            f"GRANT ALL ON *.* TO '{self.operator_user}'@'%' WITH GRANT OPTION;",
            "FLUSH PRIVILEGES;",
        ]

        file_path = f"/home/{MYSQL_SYSTEM_USER}/create-operator-user.sql"

        self.container.push(
            file_path,
            "\n".join(create_user_queries),
            encoding="utf-8",
            permissions=0o600,
            user=MYSQL_SYSTEM_USER,
            group=MYSQL_SYSTEM_GROUP,
        )

        try:
            self.container.push(
                MYSQLD_INIT_CONFIG_FILE,
                f"[mysqld]\ninit_file = {file_path}",
                encoding="utf-8",
                permissions=0o600,
                user=MYSQL_SYSTEM_USER,
                group=MYSQL_SYSTEM_GROUP,
            )
        except PathError:
            self.container.remove_path(file_path)
            logger.exception("Failed to write the custom config file for init-file")
            raise

        try:
            self.container.restart(MYSQLD_SERVICE)
            self.wait_until_mysql_connection(check_port=False)
        except (TypeError, MySQLServiceNotRunningError):
            logger.exception("Failed to run init-file and wait for connection")
            raise
        finally:
            self.container.remove_path(file_path)
            self.container.remove_path(MYSQLD_INIT_CONFIG_FILE)

    @retry(reraise=True, stop=stop_after_delay(120), wait=wait_fixed(2))
    def wait_until_mysql_connection(self, check_port: bool = True) -> None:
        """Wait until a connection to MySQL daemon is possible.

        Retry every 2 seconds for 120 seconds if there is an issue obtaining a connection.
        """
        if not self.container.exists(MYSQLD_SOCK_FILE):
            raise MySQLServiceNotRunningError

        try:
            if check_port and not self.check_mysqlsh_connection():
                raise MySQLServiceNotRunningError("Connection with mysqlsh not possible")
        except ExecutionError:
            raise MySQLServiceNotRunningError from None

        logger.debug("MySQL connection possible")

    def setup_logrotate_config(
        self,
        logs_retention_period: int,
        enabled_log_files: Iterable,
        logs_compression: bool,
    ) -> None:
        """Set up logrotate config in the workload container."""
        logger.debug("Creating the logrotate config file")

        # days * minutes/day = amount of rotated files to keep
        logs_rotations = logs_retention_period * 1440

        with open("templates/logrotate.j2") as file:
            template = jinja2.Template(file.read())

        rendered = template.render(
            system_user=MYSQL_SYSTEM_USER,
            system_group=MYSQL_SYSTEM_GROUP,
            log_dir=MYSQL_LOGS_DIR,
            archive_dir=MYSQL_ARCHIVE_DIR,
            logs_retention_period=logs_retention_period,
            logs_rotations=logs_rotations,
            logs_compression_enabled=logs_compression,
            enabled_log_files=enabled_log_files,
        )

        logger.debug("Writing the logrotate config file to the workload container")
        self.write_content_to_file(
            LOG_ROTATE_CONFIG_FILE,
            rendered,
            owner=MYSQL_SYSTEM_USER,
            group=MYSQL_SYSTEM_GROUP,
        )

    def execute_backup_commands(
        self,
        s3_path: str,
        s3_parameters: dict[str, str],
        xtrabackup_location: str = CHARMED_MYSQL_XTRABACKUP_LOCATION,
        xbcloud_location: str = CHARMED_MYSQL_XBCLOUD_LOCATION,
        xtrabackup_plugin_dir: str = XTRABACKUP_PLUGIN_DIR,
        mysqld_socket_file: str = MYSQLD_SOCK_FILE,
        tmp_base_directory: str = MYSQL_TEMP_DIR,
        defaults_config_file: str = MYSQLD_DEFAULTS_CONFIG_FILE,
        user: str | None = MYSQL_SYSTEM_USER,
        group: str | None = MYSQL_SYSTEM_GROUP,
    ) -> tuple[str, str]:
        """Executes commands to create a backup."""
        return super().execute_backup_commands(
            s3_path,
            s3_parameters,
            xtrabackup_location,
            xbcloud_location,
            xtrabackup_plugin_dir,
            mysqld_socket_file,
            tmp_base_directory,
            defaults_config_file,
            user,
            group,
        )

    def delete_temp_backup_directory(
        self,
        tmp_base_directory: str = MYSQL_TEMP_DIR,
        user=MYSQL_SYSTEM_USER,
        group=MYSQL_SYSTEM_GROUP,
    ) -> None:
        """Delete the temp backup directory in the data directory."""
        super().delete_temp_backup_directory(
            tmp_base_directory,
            user,
            group,
        )

    def retrieve_backup_with_xbcloud(
        self,
        backup_id: str,
        s3_parameters: dict[str, str],
        temp_restore_directory: str = MYSQL_TEMP_DIR,
        xbcloud_location: str = CHARMED_MYSQL_XBCLOUD_LOCATION,
        xbstream_location: str = CHARMED_MYSQL_XBSTREAM_LOCATION,
        user: str | None = MYSQL_SYSTEM_USER,
        group: str | None = MYSQL_SYSTEM_GROUP,
    ) -> tuple[str, str, str]:
        """Retrieve the specified backup from S3.

        The backup is retrieved using xbcloud and stored in a temp dir in the
        mysql container.
        """
        return super().retrieve_backup_with_xbcloud(
            backup_id,
            s3_parameters,
            temp_restore_directory,
            xbcloud_location,
            xbstream_location,
            user,
            group,
        )

    def prepare_backup_for_restore(
        self,
        backup_location: str,
        xtrabackup_location: str = CHARMED_MYSQL_XTRABACKUP_LOCATION,
        xtrabackup_plugin_dir: str = XTRABACKUP_PLUGIN_DIR,
        user=MYSQL_SYSTEM_USER,
        group=MYSQL_SYSTEM_GROUP,
    ) -> tuple[str, str]:
        """Prepare the backup in the provided dir for restore."""
        return super().prepare_backup_for_restore(
            backup_location,
            xtrabackup_location,
            xtrabackup_plugin_dir,
            user,
            group,
        )

    def empty_data_files(
        self,
        mysql_data_directory=MYSQL_DATA_DIR,
        user=MYSQL_SYSTEM_USER,
        group=MYSQL_SYSTEM_GROUP,
        extra_dirs: list[str] | None = None,
    ) -> None:
        """Empty the mysql data directory in preparation of backup restore."""
        if extra_dirs is None:
            extra_dirs = [MYSQL_LOGS_DIR]

        super().empty_data_files(
            mysql_data_directory,
            user,
            group,
            extra_dirs,
        )

    def restore_backup(
        self,
        backup_location: str,
        xtrabackup_location: str = CHARMED_MYSQL_XTRABACKUP_LOCATION,
        defaults_config_file: str = MYSQLD_DEFAULTS_CONFIG_FILE,
        mysql_data_directory: str = MYSQL_DATA_DIR,
        xtrabackup_plugin_directory: str = XTRABACKUP_PLUGIN_DIR,
        user=MYSQL_SYSTEM_USER,
        group=MYSQL_SYSTEM_GROUP,
    ) -> tuple[str, str]:
        """Restore the provided prepared backup."""
        return super().restore_backup(
            backup_location,
            xtrabackup_location,
            defaults_config_file,
            mysql_data_directory,
            xtrabackup_plugin_directory,
            user,
            group,
        )

    def delete_temp_restore_directory(
        self,
        temp_restore_directory: str = MYSQL_TEMP_DIR,
        user=MYSQL_SYSTEM_USER,
        group=MYSQL_SYSTEM_GROUP,
    ) -> None:
        """Delete the temp restore directory from the mysql data directory."""
        super().delete_temp_restore_directory(
            temp_restore_directory,
            user,
            group,
        )

    @retry(
        retry=retry_if_exception_type(MySQLWaitUntilUnitRemovedFromClusterError),
        stop=stop_after_attempt(10),
        wait=wait_fixed(60),
    )
    def _wait_until_unit_removed_from_cluster(self, unit_address: str) -> None:
        """Waits until the provided unit is no longer in the cluster.

        Retries every minute for 10 minutes if the unit is still present in the cluster.

        Args:
            unit_address: The address of the unit that was removed
                and needs to be waited until
        """
        cluster_status = self.get_cluster_status()
        if not cluster_status:
            raise MySQLWaitUntilUnitRemovedFromClusterError("Unable to get cluster status")

        members_in_cluster = [
            member["address"]
            for member in cluster_status["defaultReplicaSet"]["topology"].values()
        ]

        if unit_address in members_in_cluster:
            raise MySQLWaitUntilUnitRemovedFromClusterError("Remove member still in cluster")

    def drop_group_replication_metadata_schema(self) -> None:
        """Drop the group replication metadata schema from current unit."""
        executor = self._build_instance_tcp_executor(self.instance_address)

        try:
            executor.execute_py("dba.drop_metadata_schema()")
        except ExecutionError:
            logger.error("Failed to drop group replication metadata schema")
            raise

    def is_mysqld_running(self) -> bool:
        """Returns whether server is connectable and mysqld is running."""
        return self.is_server_connectable() and self.container.exists(MYSQLD_SOCK_FILE)

    def is_server_connectable(self) -> bool:
        """Returns whether the server is connectable."""
        return self.container.can_connect()

    def stop_mysqld(self) -> None:
        """Stops the mysqld process."""
        try:
            # call low-level pebble API to access timeout parameter
            self.container.pebble.stop_services([MYSQLD_SERVICE], timeout=5 * 60)
        except ChangeError:
            error_message = f"Failed to stop service {MYSQLD_SERVICE}"
            logger.exception(error_message)
            raise MySQLStopMySQLDError(error_message) from None

    def start_mysqld(self) -> None:
        """Starts the mysqld process."""
        try:
            self.container.start(MYSQLD_SERVICE)
            self.wait_until_mysql_connection()
        except (
            ChangeError,
            MySQLServiceNotRunningError,
        ):
            error_message = f"Failed to start service {MYSQLD_SERVICE}"
            logger.exception(error_message)
            raise MySQLStartMySQLDError(error_message) from None

    def restart_mysql_exporter(self) -> None:
        """Restarts the mysqld exporter service in pebble."""
        self.charm._reconcile_pebble_layer(self.container)

    def _execute_commands(
        self,
        commands: list[str],
        bash: bool = False,
        user: str | None = MYSQL_SYSTEM_USER,
        group: str | None = MYSQL_SYSTEM_GROUP,
        env_extra: dict | None = None,
        timeout: float | None = None,
        stream_output: str | None = None,
    ) -> tuple[str, str]:
        """Execute commands on the server where MySQL is running."""
        try:
            if bash:
                commands = ["bash", "-c", "set -o pipefail; " + " ".join(commands)]

            process = self.container.exec(
                commands,
                user=user,
                group=group,
                environment=env_extra,
                timeout=timeout,
            )

            if stream_output:
                if stream_output == "stderr" and process.stderr:
                    for line in process.stderr:
                        logger.debug(line.strip())
                if stream_output == "stdout" and process.stdout:
                    for line in process.stdout:
                        logger.debug(line.strip())

            stdout, stderr = process.wait_output()
            return (stdout.strip(), stderr.strip() if stderr else "")
        except ExecError:
            logger.error(
                f"Failed command: commands={self.strip_off_passwords(' '.join(commands))}, {user=}, {group=}"
            )
            raise MySQLExecError from None

    def write_content_to_file(
        self,
        path: str,
        content: str,
        owner: str = MYSQL_SYSTEM_USER,
        group: str = MYSQL_SYSTEM_GROUP,
        permission: int = 0o640,
    ) -> None:
        """Write content to file.

        Args:
            path: filesystem full path (with filename)
            content: string content to write
            owner: file owner
            group: file group
            permission: file permission
        """
        self.container.push(path, content, permissions=permission, user=owner, group=group)

    def read_file_content(self, path: str) -> str | None:
        """Read file content.

        Args:
            path: filesystem full path (with filename)

        Returns:
            file content
        """
        if not self.container.exists(path):
            return None

        content = self.container.pull(path, encoding="utf8")
        return content.read()

    def remove_file(self, path: str) -> None:
        """Remove a file (if it exists) from container workload.

        Args:
            path: Full filesystem path to remove
        """
        if self.container.exists(path):
            self.container.remove_path(path)

    def reset_data_dir(self) -> None:
        """Remove all files from the data directory."""
        content = self.container.list_files(MYSQL_DATA_DIR)
        content_set = {item.name for item in content}
        logger.debug("Resetting MySQL data directory.")
        for item in content_set:
            self.container.remove_path(f"{MYSQL_DATA_DIR}/{item}", recursive=True)

    def get_available_memory(self) -> int:
        """Get available memory for the container in bytes."""
        allocable_memory = self.k8s_helper.get_node_allocable_memory()
        container_limits = self.k8s_helper.get_resources_limits(CONTAINER_NAME)
        if "memory" in container_limits:
            memory_str = container_limits["memory"]
            constrained_memory = any_memory_to_bytes(memory_str)
            if constrained_memory < allocable_memory:
                logger.debug(f"Memory constrained to {memory_str} from resource limit")
                return constrained_memory

        logger.debug("Memory constrained by node allocable memory")
        return allocable_memory

    def is_data_dir_initialised(self) -> bool:
        """Check if data dir is initialised.

        Returns:
            A bool for an initialised and integral data dir.
        """
        try:
            content = self.container.list_files(MYSQL_DATA_DIR)
            content_set = {item.name for item in content}

            # minimal expected content for an integral mysqld data-dir
            expected_content = {
                "auto.cnf",
                "ca-key.pem",
                "ca.pem",
                "client-cert.pem",
                "client-key.pem",
                "ib_buffer_pool",
                "mysql",
                "mysql.ibd",
                "performance_schema",
                "private_key.pem",
                "public_key.pem",
                "server-cert.pem",
                "server-key.pem",
                "sys",
            }
            logger.debug("mysql data dir contents: %s", content_set)

            return expected_content <= content_set
        except (ExecError, APIError):
            return False

    def update_endpoints(self, relation_name: str) -> None:
        """Updates pod labels to reflect role of the unit."""
        logger.debug("Updating pod labels")
        try:
            rw_endpoints, ro_endpoints, offline = self.charm.get_cluster_endpoints(relation_name)

            for endpoints, label in (
                (rw_endpoints, "primary"),
                (ro_endpoints, "replicas"),
                (offline, "offline"),
            ):
                for pod in (p.split(".")[0] for p in endpoints.split(",")):
                    if pod:
                        self.k8s_helper.label_pod(label, pod)
        except MySQLGetClusterEndpointsError:
            logger.exception("Failed to get cluster endpoints")
        except KubernetesClientError:
            logger.exception("Can't update pod labels")

    def set_cluster_primary(self, new_primary_address: str) -> None:
        """Set the cluster primary and update pod labels."""
        super().set_cluster_primary(new_primary_address)
        self.update_endpoints(PEER)

    def fetch_error_log(self) -> str | None:
        """Fetch the MySQL error log."""
        return self.read_file_content(MYSQL_LOG_ERROR)

    def reconcile_binlogs_collection(
        self, force_restart: bool = False, ignore_inactive_error: bool = False
    ) -> bool:
        """Start or stop binlogs collecting service.

        Based on the "binlogs-collecting" app peer data value and unit leadership.

        Args:
            force_restart: whether to restart service even if it's already running.
            ignore_inactive_error: whether to not log an error when the service should be enabled but not active right now.

        Returns: whether the operation was successful.
        """
        if not self.container.can_connect():
            logger.error(
                "Cannot connect to the pebble in the mysql container to check binlogs collector"
            )
            return False

        service = self.container.get_services(MYSQL_BINLOGS_COLLECTOR_SERVICE).get(
            MYSQL_BINLOGS_COLLECTOR_SERVICE
        )
        if not service:
            logger.error("Binlogs collector service does not exist")
            return False

        is_enabled = service.startup == "enabled"
        is_active = service.is_running()
        supposed_to_run = (
            self.charm.unit.is_leader() and "binlogs-collecting" in self.charm.app_peer_data
        )

        if supposed_to_run and is_enabled and not is_active and not ignore_inactive_error:
            logger.error("Binlogs collector is enabled but not running. It will be restarted")

        if is_active and (not supposed_to_run or force_restart):
            self.container.stop(MYSQL_BINLOGS_COLLECTOR_SERVICE)

        self.charm._reconcile_pebble_layer(self.container)
        # Replan anyway as we may need to restart already enabled binlogs collector service (therefore without pebble layers change)
        self.container._pebble.replan_services(timeout=0)

        return True

    def get_cluster_members(self) -> list[str]:
        """Get cluster members in MySQL MEMBER_HOST format.

        Returns: list of cluster members in MySQL MEMBER_HOST format.
        """
        return [self.charm.unit_address] + [
            self.charm.get_unit_address(unit) for unit in self.charm.peers.units
        ]
