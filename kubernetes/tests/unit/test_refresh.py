# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

import charm_refresh
from charms.mysql.v0.mysql import (
    MySQLRescanClusterError,
    MySQLSetClusterPrimaryError,
    MySQLSetVariableError,
)
from ops.testing import Harness

from charm import MySQLOperatorCharm
from refresh import KubernetesMySQLRefresh

APP_NAME = "mysql-k8s"


class TestIsCompatible(unittest.TestCase):
    """Tests for the KubernetesMySQLRefresh.is_compatible classmethod."""

    def _make_version(self, version: str) -> charm_refresh.CharmVersion:
        return charm_refresh.CharmVersion(version)

    @patch("charm_refresh.CharmSpecificKubernetes.is_compatible", return_value=True)
    def test_compatible_same_workload_minor(self, _super):
        """Compatible when charm versions compatible and workload major.minor match."""
        result = KubernetesMySQLRefresh.is_compatible(
            old_charm_version=self._make_version("8/1.0.0"),
            new_charm_version=self._make_version("8/1.0.1"),
            old_workload_version="8.4",
            new_workload_version="8.4",
        )
        self.assertTrue(result)

    @patch("charm_refresh.CharmSpecificKubernetes.is_compatible", return_value=False)
    def test_incompatible_charm_version(self, _super):
        """Incompatible when charm versions incompatible."""
        result = KubernetesMySQLRefresh.is_compatible(
            old_charm_version=self._make_version("8/1.0.0"),
            new_charm_version=self._make_version("9/2.0.0"),
            old_workload_version="8.4",
            new_workload_version="8.4",
        )
        self.assertFalse(result)

    @patch("charm_refresh.CharmSpecificKubernetes.is_compatible", return_value=True)
    def test_incompatible_workload_major(self, _super):
        """Incompatible when workload major version differs."""
        result = KubernetesMySQLRefresh.is_compatible(
            old_charm_version=self._make_version("8/1.0.0"),
            new_charm_version=self._make_version("8/1.0.1"),
            old_workload_version="8.4",
            new_workload_version="9.4",
        )
        self.assertFalse(result)

    @patch("charm_refresh.CharmSpecificKubernetes.is_compatible", return_value=True)
    def test_incompatible_workload_minor(self, _super):
        """Incompatible when workload minor version differs."""
        result = KubernetesMySQLRefresh.is_compatible(
            old_charm_version=self._make_version("8/1.0.0"),
            new_charm_version=self._make_version("8/1.0.1"),
            old_workload_version="8.4",
            new_workload_version="8.5",
        )
        self.assertFalse(result)


class TestRefresh(unittest.TestCase):
    """Tests for KubernetesMySQLRefresh instance methods."""

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
        self.refresh = KubernetesMySQLRefresh.__new__(KubernetesMySQLRefresh)
        self.refresh._charm = self.charm

    def tearDown(self):
        self.patcher.stop()

    # ------------------------------------------------------------------
    # highest_ordinal
    # ------------------------------------------------------------------

    def test_highest_ordinal(self):
        """highest_ordinal returns planned_units - 1."""
        with patch.object(self.charm.app, "planned_units", return_value=5):
            self.assertEqual(self.refresh.highest_ordinal, 4)

    # ------------------------------------------------------------------
    # run_pre_refresh_checks_after_1_unit_refreshed
    # ------------------------------------------------------------------

    def test_run_pre_refresh_checks_after_1_unit_refreshed(self):
        """run_pre_refresh_checks_after_1_unit_refreshed is a no-op."""
        KubernetesMySQLRefresh.run_pre_refresh_checks_after_1_unit_refreshed()

    # ------------------------------------------------------------------
    # run_pre_refresh_checks_before_any_units_refreshed
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.app_units", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.get_unit_address")
    def _run_pre_refresh_checks(self, mock_get_unit_address, mock_app_units, mock_mysql, **kwargs):
        mock_mysql.return_value = mock_mysql
        mock_app_units.return_value = {MagicMock(), MagicMock()}
        mock_get_unit_address.return_value = "1.2.3.4"
        mock_mysql.return_value.rescan_cluster = MagicMock()
        mock_mysql.return_value.get_cluster_status = MagicMock(
            return_value=kwargs.get("cluster_status", {"ok": True})
        )
        mock_mysql.return_value.get_cluster_node_count = MagicMock(
            return_value=kwargs.get("num_online", 2)
        )
        mock_mysql.return_value.get_primary_label = MagicMock(
            return_value=kwargs.get("primary_label", "mysql-k8s-0")
        )
        mock_mysql.return_value.set_cluster_primary = MagicMock()
        mock_mysql.return_value.set_dynamic_variable = MagicMock()

        self.refresh.run_pre_refresh_checks_before_any_units_refreshed()
        return mock_mysql

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_rescan_error(self, mock_mysql):
        """PrecheckFailed raised when rescan_cluster fails."""
        mock_mysql.return_value.rescan_cluster.side_effect = MySQLRescanClusterError

        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_no_status(self, mock_mysql):
        """PrecheckFailed raised when cluster status is empty."""
        mock_mysql.return_value.rescan_cluster = MagicMock()
        mock_mysql.return_value.get_cluster_status.return_value = None

        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_not_all_online(self, mock_mysql):
        """PrecheckFailed raised when fewer online units than planned."""
        mock_mysql.return_value.rescan_cluster = MagicMock()
        mock_mysql.return_value.get_cluster_status.return_value = {"ok": True}
        mock_mysql.return_value.get_cluster_node_count.return_value = 1

        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("refresh.socket.getfqdn", return_value="mysql-k8s-0.fqdn")
    @patch("charm.MySQLOperatorCharm.get_unit_hostname", return_value="mysql-k8s-0")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.app_units", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="1.2.3.4")
    def test_pre_refresh_checks_switchover_and_slow_shutdown(
        self,
        _get_unit_address,
        mock_app_units,
        mock_mysql,
        _get_unit_hostname,
        _getfqdn,
    ):
        """Happy path: switchover to unit 0 and set slow shutdown on all units."""
        mock_mysql.return_value = mock_mysql
        mock_app_units.return_value = {MagicMock(name="unit/0"), MagicMock(name="unit/1")}
        mock_mysql.return_value.rescan_cluster = MagicMock()
        mock_mysql.return_value.get_cluster_status = MagicMock(return_value={"ok": True})
        mock_mysql.return_value.get_cluster_node_count = MagicMock(return_value=2)
        mock_mysql.return_value.get_primary_label = MagicMock(return_value="mysql-k8s-1")
        mock_mysql.return_value.set_cluster_primary = MagicMock()
        mock_mysql.return_value.set_dynamic_variable = MagicMock()

        self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

        mock_mysql.return_value.set_cluster_primary.assert_called_once_with("mysql-k8s-0.fqdn")
        self.assertEqual(mock_mysql.return_value.set_dynamic_variable.call_count, 2)
        for call in mock_mysql.return_value.set_dynamic_variable.call_args_list:
            self.assertEqual(call.kwargs["variable"], "innodb_fast_shutdown")
            self.assertEqual(call.kwargs["value"], 0)

    @patch("refresh.socket.getfqdn", return_value="mysql-k8s-0.fqdn")
    @patch("charm.MySQLOperatorCharm.get_unit_hostname", return_value="mysql-k8s-0")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.app_units", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="1.2.3.4")
    def test_pre_refresh_checks_set_primary_error(
        self,
        _get_unit_address,
        mock_app_units,
        mock_mysql,
        _get_unit_hostname,
        _getfqdn,
    ):
        """PrecheckFailed raised when set_cluster_primary fails."""
        mock_mysql.return_value = mock_mysql
        mock_app_units.return_value = {MagicMock()}
        mock_mysql.return_value.rescan_cluster = MagicMock()
        mock_mysql.return_value.get_cluster_status = MagicMock(return_value={"ok": True})
        mock_mysql.return_value.get_cluster_node_count = MagicMock(return_value=2)
        mock_mysql.return_value.get_primary_label = MagicMock(return_value="mysql-k8s-1")
        mock_mysql.return_value.set_cluster_primary.side_effect = MySQLSetClusterPrimaryError

        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.app_units", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="1.2.3.4")
    def test_pre_refresh_checks_set_variable_error(
        self,
        _get_unit_address,
        mock_app_units,
        mock_mysql,
    ):
        """PrecheckFailed raised when set_dynamic_variable fails."""
        mock_mysql.return_value = mock_mysql
        mock_app_units.return_value = {MagicMock()}
        mock_mysql.return_value.rescan_cluster = MagicMock()
        mock_mysql.return_value.get_cluster_status = MagicMock(return_value={"ok": True})
        mock_mysql.return_value.get_cluster_node_count = MagicMock(return_value=2)
        mock_mysql.return_value.get_primary_label = MagicMock(return_value="mysql-k8s-0")
        mock_mysql.return_value.set_dynamic_variable.side_effect = MySQLSetVariableError

        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()


if __name__ == "__main__":
    unittest.main()
