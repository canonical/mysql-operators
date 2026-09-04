# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, PropertyMock, patch

import charm_refresh
from charms.mysql.v0.mysql import (
    MySQLRescanClusterError,
    MySQLSetClusterPrimaryError,
    MySQLSetVariableError,
)
from ops import MaintenanceStatus
from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import PEER
from refresh import MachinesMySQLRefresh


class TestRefreshCompatibility(unittest.TestCase):
    """Tests for the MachinesMySQLRefresh.is_compatible classmethod."""

    def test_compatible(self):
        """Compatible when charm versions compatible and workload major.minor match."""
        old_cv = charm_refresh.CharmVersion("16/1.19.0")
        new_cv = charm_refresh.CharmVersion("16/1.20.0")
        self.assertTrue(
            MachinesMySQLRefresh.is_compatible(
                old_charm_version=old_cv,
                new_charm_version=new_cv,
                old_workload_version="8.4",
                new_workload_version="8.4",
            )
        )

    def test_incompatible_workload_version(self):
        """Incompatible when workload major.minor differ."""
        old_cv = charm_refresh.CharmVersion("16/1.19.0")
        new_cv = charm_refresh.CharmVersion("16/1.20.0")
        self.assertFalse(
            MachinesMySQLRefresh.is_compatible(
                old_charm_version=old_cv,
                new_charm_version=new_cv,
                old_workload_version="8.4",
                new_workload_version="8.0",
            )
        )

    def test_incompatible_charm_version(self):
        """Incompatible when charm versions incompatible (different track)."""
        old_cv = charm_refresh.CharmVersion("16/1.19.0")
        new_cv = charm_refresh.CharmVersion("17/1.19.0")
        self.assertFalse(
            MachinesMySQLRefresh.is_compatible(
                old_charm_version=old_cv,
                new_charm_version=new_cv,
                old_workload_version="8.4",
                new_workload_version="8.4",
            )
        )


class TestMachinesMySQLRefresh(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.peer_relation_id = self.harness.add_relation(PEER, "mysql")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/1")
        # Patch _RefreshVersions (reads refresh_versions.toml at construction)
        patcher = patch("charm_refresh._main._RefreshVersions")
        self._mock_versions = patcher.start()
        self.addCleanup(patcher.stop)
        self._mock_versions.return_value.workload = "8.4"
        # Build a refresh object using the real charm
        self.refresh = MachinesMySQLRefresh(
            workload_name="MySQL",
            charm_name="mysql",
            _charm=self.charm,
        )

    def test_run_pre_refresh_checks_after_1_unit_refreshed(self):
        """The post-1-unit pre-refresh check is a no-op."""
        # should not raise
        MachinesMySQLRefresh.run_pre_refresh_checks_after_1_unit_refreshed()

    def test_highest_ordinal(self):
        """highest_ordinal returns planned_units - 1."""
        with patch.object(self.charm.app, "planned_units", return_value=3):
            self.assertEqual(self.refresh.highest_ordinal, 2)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_before_any_units_success(self, _mysql):
        """Successful pre-refresh checks rescan, verify online and set primary."""
        mysql = _mysql.return_value
        mysql.get_cluster_status.return_value = {"ok": True}
        mysql.get_cluster_node_count.return_value = 2
        mysql.get_primary_label.return_value = self.charm.unit_label
        with patch.object(self.charm.app, "planned_units", return_value=2):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

        mysql.rescan_cluster.assert_called_once()
        mysql.get_cluster_status.assert_called_once_with(extended=True)
        mysql.get_cluster_node_count.assert_called_once()
        mysql.set_dynamic_variable.assert_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_rescan_error(self, _mysql):
        """PrecheckFailed raised when rescan_cluster fails."""
        _mysql.return_value.rescan_cluster.side_effect = MySQLRescanClusterError
        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_no_status(self, _mysql):
        """PrecheckFailed raised when cluster status cannot be retrieved."""
        _mysql.return_value.get_cluster_status.return_value = None
        with self.assertRaises(charm_refresh.PrecheckFailed):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_not_all_online(self, _mysql):
        """PrecheckFailed raised when not all units are online."""
        mysql = _mysql.return_value
        mysql.get_cluster_status.return_value = {"ok": True}
        mysql.get_cluster_node_count.return_value = 1
        with (
            patch.object(self.charm.app, "planned_units", return_value=2),
            self.assertRaises(charm_refresh.PrecheckFailed),
        ):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_set_primary_error(self, _mysql):
        """PrecheckFailed raised when setting the primary fails."""
        mysql = _mysql.return_value
        mysql.get_cluster_status.return_value = {"ok": True}
        mysql.get_cluster_node_count.return_value = 2
        mysql.get_primary_label.return_value = "other-unit"
        mysql.set_cluster_primary.side_effect = MySQLSetClusterPrimaryError
        with (
            patch.object(self.charm.app, "planned_units", return_value=2),
            self.assertRaises(charm_refresh.PrecheckFailed),
        ):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_pre_refresh_checks_set_variable_error(self, _mysql):
        """PrecheckFailed raised when setting slow shutdown fails."""
        mysql = _mysql.return_value
        mysql.get_cluster_status.return_value = {"ok": True}
        mysql.get_cluster_node_count.return_value = 2
        mysql.get_primary_label.return_value = self.charm.unit_label
        mysql.set_dynamic_variable.side_effect = MySQLSetVariableError
        with (
            patch.object(self.charm.app, "planned_units", return_value=2),
            self.assertRaises(charm_refresh.PrecheckFailed),
        ):
            self.refresh.run_pre_refresh_checks_before_any_units_refreshed()

    def test_refresh_snap(self):
        """refresh_snap sets maintenance status and installs dependencies."""
        with (
            patch.object(
                self.charm,
                "install_and_configure_mysql_dependencies",
                create=True,
            ) as _install_deps,
            patch.object(self.charm, "set_unit_status") as _set_status,
        ):
            self.refresh.refresh_snap(
                snap_name="charmed-mysql",
                snap_revision="42",
                refresh=Mock(),
            )
        _install_deps.assert_called_once_with(revision="42")
        _set_status.assert_called_once()
        self.assertIsInstance(_set_status.call_args.args[0], MaintenanceStatus)
