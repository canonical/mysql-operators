# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for MySQL class."""

import os
import subprocess
import unittest
from unittest.mock import MagicMock, Mock, call, mock_open, patch

from charms.mysql.v0.mysql import (
    MySQLExecError,
    MySQLGetAutoTuningParametersError,
    MySQLGetAvailableMemoryError,
    MySQLStartMySQLDError,
    MySQLStopMySQLDError,
)
from mysql_shell.executors.errors import ExecutionError
from tenacity import Retrying, stop_after_attempt

from constants import (
    CHARMED_MYSQL_SNAP_NAME,
    CHARMED_MYSQLD_SERVICE,
    MYSQLD_CONFIG_DIRECTORY,
    MYSQLD_CUSTOM_CONFIG_FILE,
    MYSQLD_SOCK_FILE,
)
from mysql_vm_helpers import (
    MySQL,
    MySQLCreateCustomMySQLDConfigError,
    MySQLExporterConnectError,
    MySQLFlushHostCacheError,
    MySQLInstallError,
    MySQLServiceNotRunningError,
    MySQLSetOperatorUserAndStartMySQLDError,
    SnapServiceOperationError,
    instance_hostname,
    is_volume_mounted,
    snap_service_operation,
)


class StubConfig:
    def __init__(self):
        self.max_connections = None
        self.plugin_audit_enabled = True
        self.profile = "production"
        self.profile_limit_memory = None
        self.plugin_audit_strategy = "async"
        self.binlog_retention_days = 7
        self.logs_audit_policy = "logins"


class StubCharm:
    def __init__(self):
        self.config = StubConfig()
        self.charm_dir = "/some/charm/dir"
        self.unit = Mock(name="mysql/0")


class TestMySQL(unittest.TestCase):
    def setUp(self):
        self.mysql = MySQL(
            "127.0.0.1",
            MYSQLD_SOCK_FILE,
            "test_cluster",
            "test_cluster_set",
            "charmed-operator",
            "charmed-operatorpassword",
            "charmed-replication",
            "charmed-replicationpassword",
            "charmed-stats",
            "monitoringpassword",
            "backups",
            "backupspassword",
            StubCharm(),  # type: ignore
        )

    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection.retry.stop", return_value=1)
    @patch("os.path.exists", return_value=False)
    def test_wait_until_mysql_connection(self, _exists, _stop):
        """Test a failed execution of wait_until_mysql_connection."""
        with self.assertRaises(MySQLServiceNotRunningError):
            self.mysql.wait_until_mysql_connection()

    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.check_output")
    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection")
    def test_set_operator_user_and_start_mysqld(
        self,
        _wait_until_mysql_connection,
        _snap_service_operation,
        _check_output,
        _named_temporary_file,
    ):
        """Test a successful execution of reset_root_password_and_start_mysqld."""
        self.mysql.set_operator_user_and_start_mysqld()

        self.assertEqual(2, _named_temporary_file.call_count)
        self.assertEqual(2, _check_output.call_count)
        self.assertEqual(1, _snap_service_operation.call_count)
        self.assertEqual(1, _wait_until_mysql_connection.call_count)

    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.check_output")
    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection")
    def test_set_user_operator_and_start_mysqld_exception(
        self,
        _wait_until_mysql_connection,
        _snap_service_operation,
        _check_output,
        _named_temporary_file,
    ):
        """Test a failed execution of reset_root_password_and_start_mysqld."""
        _check_output.side_effect = subprocess.CalledProcessError(cmd="", returncode=-1)

        with self.assertRaises(MySQLSetOperatorUserAndStartMySQLDError):
            self.mysql.set_operator_user_and_start_mysqld()

        self.assertEqual(2, _named_temporary_file.call_count)
        self.assertEqual(1, _check_output.call_count)
        self.assertEqual(0, _snap_service_operation.call_count)
        self.assertEqual(0, _wait_until_mysql_connection.call_count)

        _named_temporary_file.reset_mock()
        _check_output.reset_mock()
        _snap_service_operation.reset_mock()
        _wait_until_mysql_connection.reset_mock()

        _check_output.side_effect = None
        _snap_service_operation.side_effect = SnapServiceOperationError()

        with self.assertRaises(MySQLSetOperatorUserAndStartMySQLDError):
            self.mysql.set_operator_user_and_start_mysqld()

        self.assertEqual(2, _named_temporary_file.call_count)
        self.assertEqual(2, _check_output.call_count)
        self.assertEqual(1, _snap_service_operation.call_count)
        self.assertEqual(0, _wait_until_mysql_connection.call_count)

        _named_temporary_file.reset_mock()
        _check_output.reset_mock()
        _snap_service_operation.reset_mock()
        _wait_until_mysql_connection.reset_mock()

        _check_output.side_effect = None
        _snap_service_operation.side_effect = None
        _wait_until_mysql_connection.side_effect = MySQLServiceNotRunningError()

        with self.assertRaises(MySQLSetOperatorUserAndStartMySQLDError):
            self.mysql.set_operator_user_and_start_mysqld()

        self.assertEqual(2, _named_temporary_file.call_count)
        self.assertEqual(2, _check_output.call_count)
        self.assertEqual(1, _snap_service_operation.call_count)
        self.assertEqual(1, _wait_until_mysql_connection.call_count)

    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_snap_service_operation(self, _snap_cache):
        """Test a successful execution of function snap_service_operation."""
        _charmed_mysql_mock = MagicMock()
        _cache = {CHARMED_MYSQL_SNAP_NAME: _charmed_mysql_mock}
        _snap_cache.return_value.__getitem__.side_effect = _cache.__getitem__

        # Test start operation
        snap_service_operation(CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "start")

        _snap_cache.assert_called_once()
        _charmed_mysql_mock.start.assert_called_once()
        _charmed_mysql_mock.restart.assert_not_called()
        _charmed_mysql_mock.stop.assert_not_called()

        # Test restart operation
        _snap_cache.reset_mock()
        _charmed_mysql_mock.reset_mock()

        snap_service_operation(CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "restart")

        _snap_cache.assert_called_once()
        _charmed_mysql_mock.start.assert_not_called()
        _charmed_mysql_mock.restart.assert_called_once()
        _charmed_mysql_mock.stop.assert_not_called()

        # Test stop operation
        _snap_cache.reset_mock()
        _charmed_mysql_mock.reset_mock()

        snap_service_operation(CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "stop")

        _snap_cache.assert_called_once()
        _charmed_mysql_mock.start.assert_not_called()
        _charmed_mysql_mock.restart.assert_not_called()
        _charmed_mysql_mock.stop.assert_called_once()

    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_snap_service_operation_exception(self, _snap_cache):
        """Test failure in execution of function snap_service_operation."""
        _charmed_mysql_mock = MagicMock()
        _cache = {CHARMED_MYSQL_SNAP_NAME: _charmed_mysql_mock}
        _snap_cache.return_value.__getitem__.side_effect = _cache.__getitem__

        with self.assertRaises(SnapServiceOperationError):
            snap_service_operation(CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "nonsense")

        _snap_cache.assert_not_called()

    @patch("shutil.chown")
    @patch("os.chmod")
    @patch("mysql_vm_helpers.MySQL.get_available_memory", return_value=16475447296)
    @patch(
        "mysql_vm_helpers.MySQL.get_innodb_buffer_pool_parameters",
        return_value=(1234, 5678, None),
    )
    @patch("mysql_vm_helpers.MySQL.get_max_connections", return_value=111)
    @patch("pathlib.Path")
    @patch("builtins.open")
    def test_write_mysqld_config(
        self,
        _open,
        _path,
        _get_innodb_buffer_pool_parameters,
        _get_max_connections,
        _get_available_memory,
        _chmod,
        _chown,
    ):
        """Test successful execution of create_custom_mysqld_config."""
        self.maxDiff = None
        _path_mock = MagicMock()
        _path.return_value = _path_mock

        _open_mock = unittest.mock.mock_open()
        _open.side_effect = _open_mock

        self.mysql.write_mysqld_config()

        config = "\n".join((
            "[mysqld]",
            "datadir = /var/snap/charmed-mysql/common/var/lib/mysql/data",
            "bind_address = 0.0.0.0",
            "mysqlx_bind_address = 0.0.0.0",
            "admin_address = 127.0.0.1",
            "report_host = 127.0.0.1",
            "max_connections = 111",
            "innodb_buffer_pool_size = 1234",
            "innodb_log_group_home_dir = /var/snap/charmed-mysql/common/var/lib/mysql/logs",
            "innodb_temp_tablespaces_dir = /var/snap/charmed-mysql/common/var/lib/mysql/temp",
            "innodb_undo_directory = /var/snap/charmed-mysql/common/var/lib/mysql/logs",
            "log_bin = /var/snap/charmed-mysql/common/var/lib/mysql/logs/binlog",
            "log_bin_index = /var/snap/charmed-mysql/common/var/lib/mysql/logs/binlog.index",
            "log_error_services = log_filter_internal;log_sink_internal",
            "log_error = /var/snap/charmed-mysql/common/var/lib/mysql/logs/error.log",
            "general_log = OFF",
            "general_log_file = /var/snap/charmed-mysql/common/var/lib/mysql/logs/general.log",
            "loose-group_replication_paxos_single_leader = ON",
            "slow_query_log_file = /var/snap/charmed-mysql/common/var/lib/mysql/logs/slow.log",
            "binlog_expire_logs_seconds = 604800",
            "gtid_mode = ON",
            "enforce_gtid_consistency = ON",
            "activate_all_roles_on_login = ON",
            "max_connect_errors = 10000",
            "loose-validate_password.check_user_name = ON",
            "loose-validate_password.length = 12",
            "loose-validate_password.mixed_case_count = 1",
            "loose-validate_password.number_count = 1",
            "loose-validate_password.policy = MEDIUM",
            "loose-validate_password.special_char_count = 0",
            "loose-audit_log_filter.file = /var/snap/charmed-mysql/common/var/lib/mysql/logs/audit.log",
            "loose-audit_log_filter.format = JSON",
            "loose-audit_log_filter.policy = LOGINS",
            "loose-audit_log_filter.strategy = ASYNCHRONOUS",
            "innodb_buffer_pool_chunk_size = 5678",
            "\n",
        ))

        _get_max_connections.assert_called_once()
        _get_innodb_buffer_pool_parameters.assert_called_once()
        _path_mock.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)
        _open.assert_called_once_with(MYSQLD_CUSTOM_CONFIG_FILE, "w", encoding="utf-8")
        _get_available_memory.assert_called_once()

        assert call().write(config) in _open_mock.mock_calls

        # Test `testing` profile
        self.mysql.charm.config.profile = "testing"
        _open_mock.reset_mock()
        self.mysql.write_mysqld_config()

        self.assertTrue(
            call(f"{MYSQLD_CONFIG_DIRECTORY}/z-custom-mysqld.cnf", "w", encoding="utf-8")
            in _open_mock.mock_calls
        )

    @patch(
        "mysql_vm_helpers.MySQL.get_innodb_buffer_pool_parameters",
        return_value=(1234, 5678),
    )
    @patch("pathlib.Path")
    @patch("builtins.open")
    def test_create_custom_mysqld_config_exception(
        self, _open, _path, _get_innodb_buffer_pool_parameters
    ):
        """Test failure in execution of create_custom_mysqld_config."""
        _get_innodb_buffer_pool_parameters.side_effect = MySQLGetAutoTuningParametersError

        _path_mock = MagicMock()
        _path.return_value = _path_mock

        _open_mock = unittest.mock.mock_open()
        _open.side_effect = _open_mock

        self.mysql.charm.config = MagicMock()  # type: ignore

        with self.assertRaises(MySQLCreateCustomMySQLDConfigError):
            self.mysql.write_mysqld_config()

    @patch("subprocess.Popen")
    def test_execute_commands(self, _popen):
        """Test a successful execution of _execute_commands."""
        process = MagicMock()
        _popen.return_value = process
        process.wait.return_value = 0
        self.mysql._execute_commands(
            ["ls", "-la", "|", "wc", "-l"],
            bash=True,
            user="test_user",
            group="test_group",
            env_extra={"envA": "valueA"},
        )
        env = os.environ.copy()
        env.update({"envA": "valueA"})
        _popen.assert_called_once_with(
            ["bash", "-c", "set -o pipefail; ls -la | wc -l"],
            user="test_user",
            group="test_group",
            env=env,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @patch("subprocess.Popen")
    def test_execute_commands_exception(self, _popen):
        """Test a failure in execution of _execute_commands."""
        process = MagicMock()
        _popen.return_value = process
        process.wait.return_value = -1

        with self.assertRaises(MySQLExecError):
            self.mysql._execute_commands(
                ["ls", "-la"],
                bash=True,
                user="test_user",
                group="test_group",
                env_extra={"envA": "valueA"},
            )

    @patch("os.path.exists", return_value=True)
    def test_is_mysqld_running(self, _path_exists):
        """Test execution of is_mysqld_running()."""
        self.assertTrue(self.mysql.is_mysqld_running())

        _path_exists.return_value = False
        self.assertFalse(self.mysql.is_mysqld_running())

    @patch("mysql_vm_helpers.snap_service_operation")
    def test_stop_mysqld(self, _snap_service_operation):
        """Test execution of stop_mysqld()."""
        self.mysql.stop_mysqld()

        _snap_service_operation.assert_called_once_with(
            CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "stop"
        )

    @patch("mysql_vm_helpers.MySQL.kill_client_sessions")
    @patch("mysql_vm_helpers.snap_service_operation")
    def test_stop_mysqld_failure(self, _snap_service_operation, _):
        """Test failure of stop_mysqld()."""
        _snap_service_operation.side_effect = SnapServiceOperationError("failure")

        with self.assertRaises(MySQLStopMySQLDError):
            self.mysql.stop_mysqld()

    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection")
    def test_start_mysqld(
        self,
        _wait_until_mysql_connection,
        _snap_service_operation,
    ):
        """Test execution of start_mysqld()."""
        self.mysql.start_mysqld()

        _snap_service_operation.assert_called_once_with(
            CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "start"
        )
        _wait_until_mysql_connection.assert_called_once()

    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection")
    def test_start_mysqld_failure(
        self,
        _wait_until_mysql_connection,
        _snap_service_operation,
    ):
        """Test failure of start_mysqld()."""
        _snap_service_operation.side_effect = SnapServiceOperationError("failure")

        with self.assertRaises(MySQLStartMySQLDError):
            self.mysql.start_mysqld()

        _snap_service_operation.reset_mock()
        _wait_until_mysql_connection.side_effect = MySQLServiceNotRunningError

        with self.assertRaises(MySQLStartMySQLDError):
            self.mysql.start_mysqld()

    @patch("os.system")
    @patch("pathlib.Path.touch")
    @patch("pathlib.Path.owner")
    @patch("pathlib.Path.exists")
    @patch("subprocess.run")
    @patch("os.path.exists", return_value=True)
    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_install_snap(
        self,
        _cache,
        _path_exists,
        _run,
        _pathlib_exists,
        _pathlib_owner,
        _touch,
        _system,
    ):
        """Test execution of install_snap()."""
        _mysql_snap = MagicMock()
        _cache.return_value = {CHARMED_MYSQL_SNAP_NAME: _mysql_snap}

        _mysql_snap.present = False
        _path_exists.return_value = False
        _pathlib_exists.return_value = False
        _pathlib_owner.return_value = None

        self.mysql.install_and_configure_mysql_dependencies()

        assert _mysql_snap.alias.call_count == 7
        _mysql_snap.alias.assert_any_call("mysql")
        _mysql_snap.alias.assert_any_call("mysqlrouter")
        _mysql_snap.alias.assert_any_call("mysqlsh")
        _mysql_snap.alias.assert_any_call("xbcloud")
        _mysql_snap.alias.assert_any_call("xbstream")
        _mysql_snap.alias.assert_any_call("xtrabackup")
        _mysql_snap.alias.assert_any_call("mysqlbinlog")

    def test_get_available_memory(self):
        meminfo = (
            "MemTotal:       16089488 kB"
            "MemFree:          799284 kB"
            "MemAvailable:    3926924 kB"
            "Buffers:          187232 kB"
            "Cached:          4445936 kB"
            "SwapCached:       156012 kB"
            "Active:         11890336 kB"
        )

        with patch("builtins.open", mock_open(read_data=meminfo)):
            self.assertEqual(self.mysql.get_available_memory(), 16475635712)

        with (
            patch("builtins.open", mock_open(read_data="")),
            self.assertRaises(MySQLGetAvailableMemoryError),
        ):
            self.mysql.get_available_memory()

    @patch("shutil.chown")
    @patch("pathlib.Path.walk", return_value=iter([]))
    def test_reset_data_dir(self, _walk, _chown):
        self.mysql.reset_data_dir()
        _walk.assert_called_once()
        _chown.assert_called_once()

    @patch("mysql_vm_helpers.MySQL.reset_data_dir")
    @patch("subprocess.run")
    def test_initialise_mysqld(self, _subprocess_run, _reset_data_dir):
        """Test successful execution of initialise_mysqld()."""
        self.mysql.initialise_mysqld()

        _reset_data_dir.assert_called_once()
        _subprocess_run.assert_called_once_with(
            [
                "/usr/bin/sudo",
                "/snap/bin/charmed-mysql.mysqld-initialize",
                "--datadir",
                "/var/snap/charmed-mysql/common/var/lib/mysql/data",
                "--innodb-log-group-home-dir",
                "/var/snap/charmed-mysql/common/var/lib/mysql/logs",
                "--innodb-undo-directory",
                "/var/snap/charmed-mysql/common/var/lib/mysql/logs",
                "--innodb-temp-tablespaces-dir",
                "/var/snap/charmed-mysql/common/var/lib/mysql/temp",
            ],
            check=True,
        )

    @patch("mysql_vm_helpers.MySQL.reset_data_dir")
    @patch("subprocess.run")
    def test_initialise_mysqld_exception(self, _subprocess_run, _reset_data_dir):
        """Test failing execution of initialise_mysqld()."""
        from mysql_vm_helpers import MySQLInitialiseMySQLDError

        _subprocess_run.side_effect = subprocess.CalledProcessError(1, "mysqld")

        with self.assertRaises(MySQLInitialiseMySQLDError):
            self.mysql.initialise_mysqld()

        _reset_data_dir.assert_called_once()


class TestMySQLVMHelpers(unittest.TestCase):
    def setUp(self):
        self.mysql = MySQL(
            "127.0.0.1",
            MYSQLD_SOCK_FILE,
            "test_cluster",
            "test_cluster_set",
            "charmed-operator",
            "charmed-operatorpassword",
            "charmed-replication",
            "charmed-replicationpassword",
            "charmed-stats",
            "monitoringpassword",
            "backups",
            "backupspassword",
            StubCharm(),
        )

    # ---- is_volume_mounted ----

    @patch("subprocess.run")
    def test_is_volume_mounted_success(self, _run):
        self.assertTrue(is_volume_mounted())

    @patch("mysql_vm_helpers.Retrying", return_value=Retrying(stop=stop_after_attempt(1)))
    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "mountpoint"))
    def test_is_volume_mounted_failure(self, _run, _retrying):
        self.assertFalse(is_volume_mounted())

    # ---- instance_hostname ----

    @patch("subprocess.check_output", return_value=b"test-hostname\n")
    def test_instance_hostname_success(self, _check_output):
        self.assertEqual(instance_hostname(), "test-hostname")

    @patch("mysql_vm_helpers.logger")
    @patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "hostname"))
    def test_instance_hostname_failure(self, _check_output, _logger):
        self.assertIsNone(instance_hostname())

    # ---- snap_service_operation ----

    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_snap_service_operation_snap_not_present(self, _snap_cache):
        _selected_snap = MagicMock()
        _selected_snap.present = False
        _snap_cache.return_value.__getitem__ = Mock(return_value=_selected_snap)
        with self.assertRaises(SnapServiceOperationError):
            snap_service_operation(CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "start")

    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_snap_service_operation_snap_error(self, _snap_cache):
        _selected_snap = MagicMock()
        _selected_snap.present = True
        from charmlibs import snap

        _selected_snap.start.side_effect = snap.SnapError("fail")
        _snap_cache.return_value.__getitem__ = Mock(return_value=_selected_snap)
        with self.assertRaises(SnapServiceOperationError):
            snap_service_operation(CHARMED_MYSQL_SNAP_NAME, CHARMED_MYSQLD_SERVICE, "start")

    # ---- install_and_configure_mysql_dependencies ----

    @patch("mysql_vm_helpers.snap.SnapCache")
    @patch("pathlib.Path.exists")
    def test_install_snap_already_installed_not_by_charm(self, _path_exists, _snap_cache):
        _charmed_mysql = MagicMock()
        _charmed_mysql.present = True
        _snap_cache.return_value.__getitem__ = Mock(return_value=_charmed_mysql)
        _path_exists.return_value = False
        with self.assertRaisesRegex(Exception, "Multiple.*snap install.*not supported"):
            MySQL.install_and_configure_mysql_dependencies()

    @patch("mysql_vm_helpers.snap.SnapCache")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.touch")
    @patch("subprocess.check_call")
    def test_install_snap_with_revision(self, _check_call, _touch, _path_exists, _snap_cache):
        _charmed_mysql = MagicMock()
        _charmed_mysql.present = False
        _charmed_mysql.held = False
        _snap_cache.return_value.__getitem__ = Mock(return_value=_charmed_mysql)
        _path_exists.return_value = True
        MySQL.install_and_configure_mysql_dependencies(revision="243")
        _charmed_mysql.ensure.assert_called_once()
        _charmed_mysql.hold.assert_called_once()

    @patch("mysql_vm_helpers.snap.SnapCache")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.touch")
    @patch("subprocess.check_call")
    def test_install_snap_creates_common_dir(self, _check_call, _touch, _path_exists, _snap_cache):
        _charmed_mysql = MagicMock()
        _charmed_mysql.present = False
        _charmed_mysql.held = True
        _snap_cache.return_value.__getitem__ = Mock(return_value=_charmed_mysql)
        _path_exists.return_value = False
        MySQL.install_and_configure_mysql_dependencies(revision="243")
        _check_call.assert_called_once()

    @patch("mysql_vm_helpers.snap.SnapCache")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.touch")
    def test_install_snap_snap_error(self, _touch, _path_exists, _snap_cache):
        from charmlibs import snap

        _charmed_mysql = MagicMock()
        _charmed_mysql.present = False
        _charmed_mysql.held = True
        _charmed_mysql.ensure.side_effect = snap.SnapError("fail")
        _snap_cache.return_value.__getitem__ = Mock(return_value=_charmed_mysql)
        _path_exists.return_value = True
        with self.assertRaises(snap.SnapError):
            MySQL.install_and_configure_mysql_dependencies(revision="243")

    @patch("mysql_vm_helpers.snap.SnapCache")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.touch")
    def test_install_snap_other_error(self, _touch, _path_exists, _snap_cache):
        _charmed_mysql = MagicMock()
        _charmed_mysql.present = False
        _charmed_mysql.held = True
        _charmed_mysql.ensure.side_effect = RuntimeError("fail")
        _snap_cache.return_value.__getitem__ = Mock(return_value=_charmed_mysql)
        _path_exists.return_value = True
        with self.assertRaises(MySQLInstallError):
            MySQL.install_and_configure_mysql_dependencies(revision="243")

    # ---- setup_logrotate_and_cron ----

    @patch("mysql_vm_helpers.MySQL.write_content_to_file")
    @patch("builtins.open", mock_open(read_data="{{ test }}"))
    def test_setup_logrotate_and_cron(self, _write):
        self.mysql.setup_logrotate_and_cron(7, ["error", "audit"])
        self.assertEqual(_write.call_count, 3)

    # ---- flush_host_cache ----

    @patch("os.path.exists", return_value=False)
    def test_flush_host_cache_not_running(self, _exists):
        self.mysql.flush_host_cache()

    @patch("os.path.exists", return_value=True)
    @patch("mysql_vm_helpers.MySQL._build_instance_tcp_executor")
    def test_flush_host_cache_success(self, _build_executor, _exists):
        executor = Mock()
        _build_executor.return_value = executor
        self.mysql.flush_host_cache()
        executor.execute_sql.assert_called_once_with(
            "TRUNCATE TABLE performance_schema.host_cache"
        )

    @patch("os.path.exists", return_value=True)
    @patch("mysql_vm_helpers.MySQL._build_instance_tcp_executor")
    def test_flush_host_cache_error(self, _build_executor, _exists):
        executor = Mock()
        executor.execute_sql.side_effect = ExecutionError("fail")
        _build_executor.return_value = executor
        with self.assertRaises(MySQLFlushHostCacheError):
            self.mysql.flush_host_cache()

    # ---- connect_mysql_exporter ----

    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_connect_mysql_exporter_success(self, _snap_cache, _snap_service):
        _mysqld_snap = MagicMock()
        _snap_cache.return_value.__getitem__ = Mock(return_value=_mysqld_snap)
        self.mysql.connect_mysql_exporter()
        _mysqld_snap.set.assert_called_once()

    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.snap.SnapCache")
    def test_connect_mysql_exporter_error(self, _snap_cache, _snap_service):
        from charmlibs import snap

        _mysqld_snap = MagicMock()
        _mysqld_snap.set.side_effect = snap.SnapError("fail")
        _snap_cache.return_value.__getitem__ = Mock(return_value=_mysqld_snap)
        with self.assertRaises(MySQLExporterConnectError):
            self.mysql.connect_mysql_exporter()

    # ---- stop_mysql_exporter ----

    @patch("mysql_vm_helpers.snap_service_operation")
    def test_stop_mysql_exporter_success(self, _snap_service):
        self.mysql.stop_mysql_exporter()

    @patch("mysql_vm_helpers.snap_service_operation")
    def test_stop_mysql_exporter_error(self, _snap_service):
        from charmlibs import snap

        _snap_service.side_effect = snap.SnapError("fail")
        with self.assertRaises(MySQLExporterConnectError):
            self.mysql.stop_mysql_exporter()

    # ---- restart_mysql_exporter ----

    @patch("mysql_vm_helpers.MySQL.connect_mysql_exporter")
    @patch("mysql_vm_helpers.MySQL.stop_mysql_exporter")
    def test_restart_mysql_exporter(self, _stop, _connect):
        self.mysql.restart_mysql_exporter()
        _stop.assert_called_once()
        _connect.assert_called_once()

    # ---- is_data_dir_initialised ----

    @patch("os.listdir")
    def test_is_data_dir_initialised_true(self, _listdir):
        _listdir.return_value = [
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
        ]
        self.assertTrue(self.mysql.is_data_dir_initialised())

    @patch("os.listdir")
    def test_is_data_dir_initialised_false(self, _listdir):
        _listdir.return_value = ["some_file"]
        self.assertFalse(self.mysql.is_data_dir_initialised())

    @patch("os.listdir", side_effect=FileNotFoundError)
    def test_is_data_dir_initialised_not_found(self, _listdir):
        self.assertFalse(self.mysql.is_data_dir_initialised())

    # ---- write_content_to_file ----

    @patch("os.chmod")
    @patch("shutil.chown")
    @patch("builtins.open", mock_open())
    def test_write_content_to_file(self, _chown, _chmod):
        self.mysql.write_content_to_file("/test/path", "content")
        _chown.assert_called_once()
        _chmod.assert_called_once()

    # ---- read_file_content ----

    @patch("os.path.exists", return_value=False)
    def test_read_file_content_not_exists(self, _exists):
        self.assertIsNone(self.mysql.read_file_content("/test/path"))

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data="file content"))
    def test_read_file_content_success(self, _exists):
        self.assertEqual(self.mysql.read_file_content("/test/path"), "file content")

    # ---- fetch_error_log ----

    @patch("os.path.exists", return_value=False)
    def test_fetch_error_log_not_exists(self, _exists):
        self.assertIsNone(MySQL.fetch_error_log())

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data="error log content"))
    def test_fetch_error_log_success(self, _exists):
        self.assertEqual(MySQL.fetch_error_log(), "error log content")

    # ---- reset_data_dir ----

    @patch("shutil.chown")
    @patch("pathlib.Path.walk", return_value=iter([]))
    def test_reset_data_dir(self, _walk, _chown):
        MySQL.reset_data_dir()
        _walk.assert_called_once()
        _chown.assert_called_once()

    # ---- is_server_connectable ----

    def test_is_server_connectable(self):
        self.assertTrue(self.mysql.is_server_connectable())

    # ---- _execute_commands with stream_output ----

    @patch("subprocess.Popen")
    def test_execute_commands_stream_stderr(self, _popen):
        process = MagicMock()
        _popen.return_value = process
        process.stderr.readline.side_effect = ["line1\n", ""]
        process.stdout = None
        process.wait.return_value = 0
        stdout, stderr = self.mysql._execute_commands(["ls"], stream_output="stderr")
        self.assertIn("line1", stderr)

    @patch("subprocess.Popen")
    def test_execute_commands_stream_stdout(self, _popen):
        process = MagicMock()
        _popen.return_value = process
        process.stdout.readline.side_effect = ["line1\n", ""]
        process.stderr = None
        process.wait.return_value = 0
        stdout, stderr = self.mysql._execute_commands(["ls"], stream_output="stdout")
        self.assertIn("line1", stdout)

    @patch("subprocess.Popen")
    def test_execute_commands_wrapped_command(self, _popen):
        process = MagicMock()
        _popen.return_value = process
        process.wait.return_value = 0
        process.stdout.read.return_value = ""
        process.stderr.read.return_value = ""
        from constants import CHARMED_MYSQL_XTRABACKUP_LOCATION

        self.mysql._execute_commands([CHARMED_MYSQL_XTRABACKUP_LOCATION, "--backup"])
        _popen.assert_called_once()
        _, kwargs = _popen.call_args
        self.assertEqual(kwargs["user"], "root")
        self.assertEqual(kwargs["group"], "root")

    # ---- execute_backup_commands (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.execute_backup_commands")
    def test_execute_backup_commands(self, _super):
        _super.return_value = ("stdout", "stderr")
        result = self.mysql.execute_backup_commands("s3_path", {"bucket": "test"})
        self.assertEqual(result, ("stdout", "stderr"))

    # ---- delete_temp_backup_directory (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.delete_temp_backup_directory")
    def test_delete_temp_backup_directory(self, _super):
        self.mysql.delete_temp_backup_directory()
        _super.assert_called_once()

    # ---- retrieve_backup_with_xbcloud (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.retrieve_backup_with_xbcloud")
    def test_retrieve_backup_with_xbcloud(self, _super):
        _super.return_value = ("stdout", "stderr", "backup_id")
        result = self.mysql.retrieve_backup_with_xbcloud("backup_id", {"bucket": "test"})
        self.assertEqual(result, ("stdout", "stderr", "backup_id"))

    # ---- prepare_backup_for_restore (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.prepare_backup_for_restore")
    def test_prepare_backup_for_restore(self, _super):
        _super.return_value = ("stdout", "stderr")
        result = self.mysql.prepare_backup_for_restore("/backup/location")
        self.assertEqual(result, ("stdout", "stderr"))

    # ---- empty_data_files (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.empty_data_files")
    def test_empty_data_files(self, _super):
        self.mysql.empty_data_files()
        _super.assert_called_once()

    @patch("charms.mysql.v0.mysql.MySQLBase.empty_data_files")
    def test_empty_data_files_with_extra_dirs(self, _super):
        self.mysql.empty_data_files(extra_dirs=["/extra/dir"])
        _super.assert_called_once()

    # ---- restore_backup (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.restore_backup")
    def test_restore_backup(self, _super):
        _super.return_value = ("stdout", "stderr")
        result = self.mysql.restore_backup("/backup/location")
        self.assertEqual(result, ("stdout", "stderr"))

    # ---- delete_temp_restore_directory (delegates to super) ----

    @patch("charms.mysql.v0.mysql.MySQLBase.delete_temp_restore_directory")
    def test_delete_temp_restore_directory(self, _super):
        self.mysql.delete_temp_restore_directory()
        _super.assert_called_once()

    # ---- start_mysqld exception with MySQLServiceNotRunningError ----

    @patch("mysql_vm_helpers.snap_service_operation")
    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection")
    def test_start_mysqld_service_not_running(self, _wait, _snap_service):
        _wait.side_effect = MySQLServiceNotRunningError("not running")
        from charms.mysql.v0.mysql import MySQLStartMySQLDError

        with self.assertRaises(MySQLStartMySQLDError):
            self.mysql.start_mysqld()

    # ---- stop_mysqld with MySQLKillSessionError ----

    @patch("mysql_vm_helpers.snap_service_operation")
    def test_stop_mysqld_kill_session_error(self, _snap_service):
        from charms.mysql.v0.mysql import MySQLKillSessionError, MySQLStopMySQLDError

        _snap_service.side_effect = MySQLKillSessionError("fail")
        with self.assertRaises(MySQLStopMySQLDError):
            self.mysql.stop_mysqld()
