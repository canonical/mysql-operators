# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
import unittest
from unittest.mock import MagicMock, Mock, mock_open, patch

from mysql_shell.executors.errors import ExecutionError

from constants import (
    CHARMED_MYSQL_SNAP_NAME,
    CHARMED_MYSQLD_SERVICE,
    MYSQLD_SOCK_FILE,
)
from mysql_vm_helpers import (
    MySQL,
    MySQLExporterConnectError,
    MySQLFlushHostCacheError,
    MySQLInstallError,
    MySQLServiceNotRunningError,
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

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "mountpoint"))
    def test_is_volume_mounted_failure(self, _run):
        self.assertFalse(is_volume_mounted())

    # ---- instance_hostname ----

    @patch("subprocess.check_output", return_value=b"test-hostname\n")
    def test_instance_hostname_success(self, _check_output):
        self.assertEqual(instance_hostname(), "test-hostname")

    @patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "hostname"))
    def test_instance_hostname_failure(self, _check_output):
        with patch("mysql_vm_helpers.logger"):
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


if __name__ == "__main__":
    unittest.main()
