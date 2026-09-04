# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, PropertyMock, patch

from mysql_shell import LogType
from ops.testing import Harness

from charm import MySQLOperatorCharm


class TestRotateMySQLLogsObserver(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.observer = self.charm.log_rotate_observer

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_skip_when_no_peers(self, _mysql):
        """No-op when there is no peer relation."""
        self.observer._rotate_mysql_logs(None)
        _mysql.return_value.is_mysqld_running.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_skip_when_not_initialized(self, _mysql):
        """No-op when unit not initialized."""
        self.harness.add_relation("database-peers", "mysql")
        with patch.object(self.charm, "unit_initialized", return_value=False):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.is_mysqld_running.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_skip_when_mysqld_not_running(self, _mysql, _):
        """No-op when mysqld is not running."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = False
        self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_logs.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_skip_when_refresh_none(self, _mysql, _):
        """No-op when refresh is None."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = True
        with patch.object(self.charm, "_refresh", None):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_logs.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_skip_when_refresh_in_progress(self, _mysql, _):
        """No-op when a refresh is in progress."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = True
        with patch.object(self.charm, "_refresh", mock_refresh):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_logs.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_flush_audit_log(self, _mysql, _):
        """AUDIT logs type flushes the audit log."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = False
        with (
            patch.object(self.charm, "_refresh", mock_refresh),
            patch.dict("os.environ", {"LOGS_TYPE": "AUDIT"}),
        ):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_audit_log.assert_called_once()
        _mysql.return_value.flush_mysql_logs.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_invalid_logs_type(self, _mysql, _):
        """Invalid logs type (raising KeyError) is a no-op."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = False
        with (
            patch.object(self.charm, "_refresh", mock_refresh),
            patch.dict("os.environ", {"LOGS_TYPE": "BOGUS"}),
            patch(
                "services.observers.log_rotate_observer.LogType",
                side_effect=KeyError,
            ),
        ):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_logs.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_flush_valid_logs_type(self, _mysql, _):
        """A valid logs type flushes the corresponding mysql logs."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = False
        with (
            patch.object(self.charm, "_refresh", mock_refresh),
            patch.dict("os.environ", {"LOGS_TYPE": "ERROR"}),
        ):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_logs.assert_called_once_with(LogType.ERROR)

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_default_logs_type_when_env_unset(self, _mysql, _):
        """Missing LOGS_TYPE env results in an invalid type no-op."""
        self.harness.add_relation("database-peers", "mysql")
        _mysql.return_value.is_mysqld_running.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = False
        with (
            patch.object(self.charm, "_refresh", mock_refresh),
            patch.dict("os.environ", {}, clear=True),
            patch(
                "services.observers.log_rotate_observer.LogType",
                side_effect=KeyError,
            ),
        ):
            self.observer._rotate_mysql_logs(None)
        _mysql.return_value.flush_mysql_logs.assert_not_called()


class TestSelfHealingMySQLObserver(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.observer = self.charm.self_healing_observer

    @patch("charm.MySQLOperatorCharm._on_update_status")
    def test_heal_mysql_cluster(self, _update_status):
        """_heal_mysql_cluster triggers update status and endpoint refresh."""
        with patch.object(self.charm, "update_endpoints") as _update_endpoints:
            self.observer._heal_mysql_cluster(None)
        _update_status.assert_called_once()
        _update_endpoints.assert_called_once()
