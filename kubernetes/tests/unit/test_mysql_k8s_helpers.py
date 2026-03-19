# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, call, patch

import tenacity
from ops.pebble import ExecError, PathError

from constants import PEER
from mysql_k8s_helpers import (
    MySQL,
    MySQLInitialiseMySQLDError,
    MySQLServiceNotRunningError,
    MySQLWaitUntilUnitRemovedFromClusterError,
)

GET_CLUSTER_STATUS_RETURN = {
    "defaultReplicaSet": {
        "status": "no_quorum",
        "topology": {
            "mysql-0": {
                "status": "ONLINE",
                "address": "mysql-0.mysql-endpoints",
            },
            "mysql-2": {
                "status": "UNREACHABLE",
                "address": "mysql-2.mysql-endpoints",
            },
            "mysql-1": {
                "status": "(MISSING)",
                "address": "mysql-1.mysql-endpoints",
            },
        },
    },
}


class TestMySQL(unittest.TestCase):
    def setUp(self):
        self.mock_executor_cls = MagicMock()
        self.mock_executor = self.mock_executor_cls.return_value
        self.mysql = MySQL(
            "127.0.0.1",
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
            None,
            None,
            None,
        )
        self.mysql.executor_class = self.mock_executor_cls

    @patch("ops.pebble.ExecProcess")
    @patch("ops.model.Container")
    def test_initialise_mysqld(self, _container, _process):
        """Test a successful execution of bootstrap_instance."""
        _container.exec.return_value = _process
        self.mysql.container = _container

        self.mysql.initialise_mysqld()

        _container.exec.assert_called_once_with(
            command=["/usr/sbin/mysqld", "--initialize", "-u", "mysql"],
            user="mysql",
            group="mysql",
        )

        _process.wait_output.assert_called_once()

    @patch("ops.model.Container")
    def test_initialise_mysqld_exception(self, _container):
        """Test a failing execution of bootstrap_instance."""
        self.mysql.initialise_mysqld.retry.retry = tenacity.retry_if_not_result(lambda x: True)
        _container.exec.side_effect = ExecError(
            command=["mysqld"], exit_code=1, stdout=b"", stderr=b"Error"
        )
        self.mysql.container = _container

        with self.assertRaises(MySQLInitialiseMySQLDError):
            self.mysql.initialise_mysqld()

    @patch("ops.model.Container")
    def test_wait_until_mysql_connection(self, _container):
        """Test wait_until_mysql_connection."""
        self.mysql.wait_until_mysql_connection.retry.retry = tenacity.retry_if_not_result(
            lambda x: True
        )
        _container.exists.return_value = True
        self.mysql.container = _container

        self.assertTrue(not self.mysql.wait_until_mysql_connection(check_port=False))

    @patch("mysql_k8s_helpers.MySQL.get_cluster_status", return_value=GET_CLUSTER_STATUS_RETURN)
    def test_wait_until_unit_removed_from_cluster(self, _get_cluster_status):
        """Test the successful execution of _wait_until_unit_removed_from_cluster."""
        self.mysql._wait_until_unit_removed_from_cluster("mysql-3.mysql-endpoints")

        self.assertEqual(_get_cluster_status.call_count, 1)

    @patch("mysql_k8s_helpers.MySQL.get_cluster_status", return_value=GET_CLUSTER_STATUS_RETURN)
    def test_wait_until_unit_removed_from_cluster_exception(self, _get_cluster_status):
        """Test an exception while executing _wait_until_unit_removed_from_cluster."""
        # disable tenacity retry
        self.mysql._wait_until_unit_removed_from_cluster.retry.retry = (
            tenacity.retry_if_not_result(lambda x: True)
        )

        with self.assertRaises(MySQLWaitUntilUnitRemovedFromClusterError):
            self.mysql._wait_until_unit_removed_from_cluster("mysql-0.mysql-endpoints")

        self.assertEqual(_get_cluster_status.call_count, 1)

        _get_cluster_status.reset_mock()
        _get_cluster_status.return_value = None

        with self.assertRaises(MySQLWaitUntilUnitRemovedFromClusterError):
            self.mysql._wait_until_unit_removed_from_cluster("mysql-0.mysql-endpoints")

    @patch("ops.model.Container")
    def test_log_rotate_config(self, _container):
        """Test log_rotate_config."""
        rendered_logrotate_config = (
            "# Create dedicated subdirectory for rotated files\n"
            "createolddir 770 mysql mysql\n\n"
            "# Frequency of logs rotation\n"
            "hourly\n"
            "maxage 1\n"
            "rotate 1440\n\n"
            "# Compression settings\n\n"
            "nocompress\n\n\n"
            "# Naming of rotated files should be in the format:\n"
            "dateext\n"
            "dateformat -%Y%m%d_%H%M\n\n"
            "# Settings to prevent misconfigurations and unwanted behaviours\n"
            "ifempty\n"
            "missingok\n"
            "nomail\n"
            "nosharedscripts\n"
            "nocopytruncate\n\n\n"
            "/var/log/mysql/error.log {\n"
            "    olddir archive_error\n"
            "}\n\n"
            "/var/log/mysql/general.log {\n"
            "    olddir archive_general\n"
            "}\n\n"
            "/var/log/mysql/slowquery.log {\n"
            "    olddir archive_slowquery\n"
            "}\n\n"
            "/var/log/mysql/audit.log {\n"
            "    olddir archive_audit\n"
            "}\n"
        )

        self.mysql.container = _container
        self.mysql.setup_logrotate_config(1, ["error", "general", "slowquery", "audit"], False)

        self.mysql.container.push.assert_called_once_with(
            "/etc/logrotate.d/flush_mysql_logs",
            rendered_logrotate_config,
            permissions=416,
            user="mysql",
            group="mysql",
        )

    def test_update_endpoints(self):
        """Test the successful execution of update_endpoints."""
        _label_pod = MagicMock()
        _mock_k8s_helper = MagicMock()
        _mock_k8s_helper.label_pod = _label_pod

        _mock_charm = MagicMock()
        _mock_charm.get_cluster_endpoints.return_value = (
            "mysql-0.mysql-endpoints",
            "mysql-1.mysql-endpoints,mysql-2.mysql-endpoints",
            "mysql-3.mysql-endpoints",
        )

        self.mysql.k8s_helper = _mock_k8s_helper
        self.mysql.charm = _mock_charm

        calls = [
            call("primary", "mysql-0"),
            call("replicas", "mysql-1"),
            call("replicas", "mysql-2"),
            call("offline", "mysql-3"),
        ]

        self.mysql.update_endpoints(PEER)
        self.mysql.charm.get_cluster_endpoints.assert_called_once()

        _label_pod.assert_has_calls(calls)

    @patch("ops.model.Container")
    @patch("mysql_k8s_helpers.MySQL.wait_until_mysql_connection")
    def test_set_operator_user_and_start_mysqld(self, _wait_until_mysql_connection, _container):
        """Test for reset_root_password_and_start_mysqld()."""
        self.mysql.container = _container
        self.mysql.set_operator_user_and_start_mysqld()

        self.mysql.container.push.assert_has_calls([
            call(
                "/create-operator-user.sql",
                (
                    "CREATE USER 'charmed-operator'@'%' IDENTIFIED BY 'charmed-operatorpassword';\n"
                    "GRANT ALL ON *.* TO 'charmed-operator'@'%' WITH GRANT OPTION;\n"
                    "FLUSH PRIVILEGES;"
                ),
                encoding="utf-8",
                permissions=384,
                user="mysql",
                group="mysql",
            ),
            call(
                "/etc/mysql/mysql.conf.d/z-custom-init-file.cnf",
                "[mysqld]\ninit_file = /create-operator-user.sql",
                encoding="utf-8",
                permissions=384,
                user="mysql",
                group="mysql",
            ),
        ])
        self.mysql.container.restart.assert_called_once_with("mysqld")
        _wait_until_mysql_connection.assert_called_once_with(check_port=False)
        self.mysql.container.remove_path.assert_has_calls([
            call("/create-operator-user.sql"),
            call("/etc/mysql/mysql.conf.d/z-custom-init-file.cnf"),
        ])

    @patch("ops.model.Container")
    @patch("mysql_k8s_helpers.MySQL.wait_until_mysql_connection")
    def test_set_operator_user_and_start_mysqld_error(
        self, _wait_until_mysql_connection, _container
    ):
        """Test exceptions in reset_root_password_and_start_mysqld()."""
        self.mysql.container = _container
        _container.push.side_effect = [
            None,
            PathError("not-found", "Should be a pebble exception"),
        ]

        with self.assertRaises(PathError):
            self.mysql.set_operator_user_and_start_mysqld()

        self.mysql.container.push.assert_has_calls([
            call(
                "/create-operator-user.sql",
                (
                    "CREATE USER 'charmed-operator'@'%' IDENTIFIED BY 'charmed-operatorpassword';\n"
                    "GRANT ALL ON *.* TO 'charmed-operator'@'%' WITH GRANT OPTION;\n"
                    "FLUSH PRIVILEGES;"
                ),
                encoding="utf-8",
                permissions=384,
                user="mysql",
                group="mysql",
            ),
        ])
        self.mysql.container.remove_path.assert_called_once_with("/create-operator-user.sql")
        _wait_until_mysql_connection.assert_not_called()

        _container.push.side_effect = [None, None]
        _container.push.reset_mock()
        _container.remove_path.reset_mock()

        _wait_until_mysql_connection.side_effect = [
            MySQLServiceNotRunningError("mysqld not running")
        ]

        with self.assertRaises(MySQLServiceNotRunningError):
            self.mysql.set_operator_user_and_start_mysqld()

        self.mysql.container.push.assert_has_calls([
            call(
                "/create-operator-user.sql",
                (
                    "CREATE USER 'charmed-operator'@'%' IDENTIFIED BY 'charmed-operatorpassword';\n"
                    "GRANT ALL ON *.* TO 'charmed-operator'@'%' WITH GRANT OPTION;\n"
                    "FLUSH PRIVILEGES;"
                ),
                encoding="utf-8",
                permissions=384,
                user="mysql",
                group="mysql",
            ),
            call(
                "/etc/mysql/mysql.conf.d/z-custom-init-file.cnf",
                "[mysqld]\ninit_file = /create-operator-user.sql",
                encoding="utf-8",
                permissions=384,
                user="mysql",
                group="mysql",
            ),
        ])
        self.mysql.container.restart.assert_called_once_with("mysqld")
        self.mysql.container.remove_path.assert_has_calls([
            call("/create-operator-user.sql"),
            call("/etc/mysql/mysql.conf.d/z-custom-init-file.cnf"),
        ])
