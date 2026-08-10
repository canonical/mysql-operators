# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import PropertyMock, patch

from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import LOG_ROTATE_CONFIG_FILE

APP_NAME = "mysql-k8s"


class TestLogRotateObserver(unittest.TestCase):
    def setUp(self):
        self.patcher = patch("lightkube.core.client.GenericSyncClient")
        self.patcher.start()
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peer_relation_id = self.harness.add_relation("database-peers", "database-peers")
        self.harness.add_relation_unit(self.peer_relation_id, f"{APP_NAME}/1")
        self.harness.update_relation_data(
            self.peer_relation_id,
            APP_NAME,
            {"cluster-name": "test_cluster", "cluster-set-domain-name": "test_cluster_set"},
        )
        self.charm = self.harness.charm
        self.observer = self.charm.log_rotate_observer

    def tearDown(self):
        self.patcher.stop()

    def _patch_running(self, running=True):
        return patch.object(
            type(self.charm),
            "_mysql",
            new_callable=PropertyMock,
        )

    # ------------------------------------------------------------------
    # _rotate_mysql_logs - early returns
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_skips_when_no_peers(self, mock_mysql):
        """Rotate is a no-op when there is no peer relation."""
        with patch.object(type(self.charm), "peers", new=PropertyMock(return_value=None)):
            self.observer._rotate_mysql_logs(None)
        mock_mysql.return_value._execute_commands.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_skips_when_mysqld_not_running(self, mock_mysql):
        """Rotate is a no-op when mysqld is not running."""
        mock_mysql.return_value.is_mysqld_running.return_value = False
        self.observer._rotate_mysql_logs(None)
        mock_mysql.return_value._execute_commands.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_skips_when_not_initialized(self, mock_mysql):
        """Rotate is a no-op when unit not initialized."""
        mock_mysql.return_value.is_mysqld_running.return_value = True
        with patch.object(self.charm, "unit_initialized", return_value=False):
            self.observer._rotate_mysql_logs(None)
        mock_mysql.return_value._execute_commands.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_skips_when_refresh_none(self, mock_mysql):
        """Rotate is a no-op when refresh is None."""
        mock_mysql.return_value.is_mysqld_running.return_value = True
        self.charm._refresh = None
        with patch.object(self.charm, "unit_initialized", return_value=True):
            self.observer._rotate_mysql_logs(None)
        mock_mysql.return_value._execute_commands.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_skips_when_refresh_in_progress(self, mock_mysql):
        """Rotate is a no-op when a refresh is in progress."""
        mock_mysql.return_value.is_mysqld_running.return_value = True
        self.charm._refresh.in_progress = True
        with patch.object(self.charm, "unit_initialized", return_value=True):
            self.observer._rotate_mysql_logs(None)
        mock_mysql.return_value._execute_commands.assert_not_called()

    # ------------------------------------------------------------------
    # _rotate_mysql_logs - happy path & errors
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_executes_logrotate_and_flushes(self, mock_mysql):
        """Rotate executes logrotate and flushes logs (without audit)."""
        mock_mysql.return_value.is_mysqld_running.return_value = True
        mock_mysql.return_value._execute_commands.return_value = None

        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("charm.MySQLOperatorCharm.config", new_callable=PropertyMock) as mock_config,
        ):
            mock_config.return_value.plugin_audit_enabled = False
            self.observer._rotate_mysql_logs(None)

        mock_mysql.return_value._execute_commands.assert_called_once_with([
            "logrotate",
            "-f",
            LOG_ROTATE_CONFIG_FILE,
        ])
        mock_mysql.return_value.flush_mysql_logs.assert_called_once()
        mock_mysql.return_value.flush_mysql_audit_log.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_flushes_audit_when_enabled(self, mock_mysql):
        """Rotate flushes the audit log when audit plugin is enabled."""
        mock_mysql.return_value.is_mysqld_running.return_value = True
        mock_mysql.return_value._execute_commands.return_value = None

        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("charm.MySQLOperatorCharm.config", new_callable=PropertyMock) as mock_config,
        ):
            mock_config.return_value.plugin_audit_enabled = True
            self.observer._rotate_mysql_logs(None)

        mock_mysql.return_value.flush_mysql_logs.assert_called_once()
        mock_mysql.return_value.flush_mysql_audit_log.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_swallows_exec_error(self, mock_mysql):
        """Rotate logs and returns when logrotate command fails."""
        from charms.mysql.v0.mysql import MySQLExecError

        mock_mysql.return_value.is_mysqld_running.return_value = True
        mock_mysql.return_value._execute_commands.side_effect = MySQLExecError

        with patch.object(self.charm, "unit_initialized", return_value=True):
            self.observer._rotate_mysql_logs(None)

        mock_mysql.return_value.flush_mysql_logs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
