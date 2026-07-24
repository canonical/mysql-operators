# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, patch

from ops.model import ActiveStatus, MaintenanceStatus
from ops.testing import Harness

from charm import MySQLOperatorCharm
from services.managers.self_healing_manager import check_pid


class TestIPAddressManager(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.manager = self.charm.hostname_manager

    @patch("services.managers.ip_address_manager.subprocess.Popen")
    def test_start_manager_skips_when_not_active(self, mock_popen):
        """start_manager does nothing when unit is not ActiveStatus."""
        self.charm.unit.status = MaintenanceStatus("busy")
        self.harness.add_relation("database-peers", "mysql")
        self.manager.start_manager()
        mock_popen.assert_not_called()

    @patch("services.managers.ip_address_manager.subprocess.Popen")
    def test_start_manager_skips_when_no_peers(self, mock_popen):
        """start_manager does nothing when peers is None."""
        self.charm.unit.status = ActiveStatus()
        self.manager.start_manager()
        mock_popen.assert_not_called()

    @patch("services.managers.ip_address_manager.os.kill")
    @patch("services.managers.ip_address_manager.subprocess.Popen")
    def test_start_manager_skips_when_pid_running(self, mock_popen, mock_kill):
        """start_manager does nothing when manager process already running."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit.status = ActiveStatus()
        self.charm.unit_peer_data["ip-address-manager-pid"] = "1234"
        # os.kill(pid, 0) succeeds -> process running
        mock_kill.return_value = None
        self.manager.start_manager()
        mock_popen.assert_not_called()

    @patch("services.managers.ip_address_manager.subprocess.Popen")
    def test_start_manager_restarts_when_pid_stale(self, mock_popen):
        """start_manager restarts when stored pid no longer alive."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit.status = ActiveStatus()
        self.charm.unit_peer_data["ip-address-manager-pid"] = "1234"

        mock_process = Mock()
        mock_process.pid = 5678
        mock_popen.return_value = mock_process

        with (
            patch("services.managers.ip_address_manager.os.kill", side_effect=OSError),
            patch("builtins.open"),
        ):
            self.manager.start_manager()

        mock_popen.assert_called_once()
        self.assertEqual(self.charm.unit_peer_data["ip-address-manager-pid"], "5678")

    @patch("services.managers.ip_address_manager.os.environ", {"PATH": "/usr/bin"})
    @patch("builtins.open")
    @patch("services.managers.ip_address_manager.subprocess.Popen")
    def test_start_manager_starts_process(self, mock_popen, mock_open):
        """start_manager spawns process and stores pid when starting fresh."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit.status = ActiveStatus()

        mock_process = Mock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process

        self.manager.start_manager()

        mock_popen.assert_called_once()
        self.assertEqual(self.charm.unit_peer_data["ip-address-manager-pid"], "9999")

    @patch("services.managers.ip_address_manager.subprocess.Popen")
    def test_start_manager_removes_juju_context_id(self, mock_popen):
        """start_manager strips JUJU_CONTEXT_ID from the spawned process env."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit.status = ActiveStatus()
        mock_popen.return_value = Mock(pid=1)

        with (
            patch("builtins.open"),
            patch.dict(
                "services.managers.ip_address_manager.os.environ",
                {"JUJU_CONTEXT_ID": "ctx-1", "PATH": "/usr/bin"},
            ),
        ):
            self.manager.start_manager()

        _, kwargs = mock_popen.call_args
        assert "JUJU_CONTEXT_ID" not in kwargs["env"]

    def test_stop_manager_skips_when_no_peers(self):
        """stop_manager does nothing when peers is None."""
        self.manager.stop_manager()
        # no exception raised

    def test_stop_manager_skips_when_no_pid(self):
        """stop_manager does nothing when no pid stored."""
        self.harness.add_relation("database-peers", "mysql")
        self.manager.stop_manager()

    @patch("services.managers.ip_address_manager.os.kill")
    def test_stop_manager_kills_and_removes_pid(self, mock_kill):
        """stop_manager sends SIGTERM and removes the pid from peer data."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit_peer_data["ip-address-manager-pid"] = "4321"
        self.manager.stop_manager()
        mock_kill.assert_called_once_with(4321, 15)
        self.assertNotIn("ip-address-manager-pid", self.charm.unit_peer_data)

    @patch("services.managers.ip_address_manager.os.kill", side_effect=OSError)
    def test_stop_manager_handles_oserror(self, mock_kill):
        """stop_manager swallows OSError when killing a dead process."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit_peer_data["ip-address-manager-pid"] = "4321"
        self.manager.stop_manager()
        mock_kill.assert_called_once_with(4321, 15)


class TestSelfHealingManager(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.manager = self.charm.self_healing_manager

    @patch("services.managers.self_healing_manager.subprocess.Popen")
    def test_start_manager_skips_when_no_peers(self, mock_popen):
        """start_manager does nothing when peers is None."""
        with patch.object(self.charm, "unit_initialized", return_value=True):
            self.manager.start_manager()
        mock_popen.assert_not_called()

    @patch("services.managers.self_healing_manager.subprocess.Popen")
    def test_start_manager_skips_when_not_initialized(self, mock_popen):
        """start_manager does nothing when unit not initialized."""
        self.harness.add_relation("database-peers", "mysql")
        with patch.object(self.charm, "unit_initialized", return_value=False):
            self.manager.start_manager()
        mock_popen.assert_not_called()

    @patch("services.managers.self_healing_manager.subprocess.Popen")
    def test_start_manager_skips_when_pid_running(self, mock_popen):
        """start_manager does nothing when manager process already running."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit_peer_data["self-heal-manager-pid"] = "1234"
        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("services.managers.self_healing_manager.check_pid", return_value=True),
        ):
            self.manager.start_manager()
        mock_popen.assert_not_called()

    @patch("services.managers.self_healing_manager.subprocess.Popen")
    def test_start_manager_starts_process(self, mock_popen):
        """start_manager spawns process and stores pid when starting fresh."""
        self.harness.add_relation("database-peers", "mysql")
        mock_process = Mock()
        mock_process.pid = 7777
        mock_popen.return_value = mock_process

        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("services.managers.self_healing_manager.check_pid", return_value=False),
            patch("builtins.open"),
            patch.dict(
                "services.managers.self_healing_manager.os.environ",
                {"PATH": "/usr/bin"},
            ),
        ):
            self.manager.start_manager()

        mock_popen.assert_called_once()
        self.assertEqual(self.charm.unit_peer_data["self-heal-manager-pid"], "7777")

    @patch("services.managers.self_healing_manager.subprocess.Popen")
    def test_start_manager_removes_juju_context_id(self, mock_popen):
        """start_manager strips JUJU_CONTEXT_ID from the spawned process env."""
        self.harness.add_relation("database-peers", "mysql")
        mock_popen.return_value = Mock(pid=1)

        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("services.managers.self_healing_manager.check_pid", return_value=False),
            patch("builtins.open"),
            patch.dict(
                "services.managers.self_healing_manager.os.environ",
                {"JUJU_CONTEXT_ID": "ctx-1", "PATH": "/usr/bin"},
            ),
        ):
            self.manager.start_manager()

        _, kwargs = mock_popen.call_args
        assert "JUJU_CONTEXT_ID" not in kwargs["env"]

    def test_stop_manager_skips_when_no_peers(self):
        """stop_manager does nothing when peers is None."""
        self.manager.stop_manager()

    def test_stop_manager_skips_when_no_pid(self):
        """stop_manager does nothing when no pid stored."""
        self.harness.add_relation("database-peers", "mysql")
        self.manager.stop_manager()

    @patch("services.managers.self_healing_manager.os.kill")
    def test_stop_manager_kills_and_removes_pid(self, mock_kill):
        """stop_manager sends SIGTERM and removes the pid from peer data."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit_peer_data["self-heal-manager-pid"] = "4321"
        self.manager.stop_manager()
        mock_kill.assert_called_once_with(4321, 15)
        self.assertNotIn("self-heal-manager-pid", self.charm.unit_peer_data)

    @patch("services.managers.self_healing_manager.os.kill", side_effect=OSError)
    def test_stop_manager_handles_oserror(self, mock_kill):
        """stop_manager swallows OSError when killing a dead process."""
        self.harness.add_relation("database-peers", "mysql")
        self.charm.unit_peer_data["self-heal-manager-pid"] = "4321"
        self.manager.stop_manager()
        mock_kill.assert_called_once_with(4321, 15)


class TestCheckPid(unittest.TestCase):
    @patch("services.managers.self_healing_manager.os.kill")
    def test_check_pid_alive(self, mock_kill):
        """check_pid returns True when process exists."""
        mock_kill.return_value = None
        self.assertTrue(check_pid(1234))
        mock_kill.assert_called_once_with(1234, 0)

    @patch("services.managers.self_healing_manager.os.kill", side_effect=OSError)
    def test_check_pid_dead(self, mock_kill):
        """check_pid returns False when process does not exist."""
        self.assertFalse(check_pid(1234))


if __name__ == "__main__":
    unittest.main()
