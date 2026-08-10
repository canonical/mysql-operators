# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import PropertyMock, patch

from ops.model import ActiveStatus
from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import CONTAINER_NAME

APP_NAME = "mysql-k8s"


class TestLogRotateManager(unittest.TestCase):
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
        self.manager = self.charm.log_rotate_manager

    def tearDown(self):
        self.patcher.stop()

    # ------------------------------------------------------------------
    # start_log_rotate_manager
    # ------------------------------------------------------------------

    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_skips_when_not_active(self, _popen):
        """Start skips when unit is not ActiveStatus."""
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.manager.start_log_rotate_manager()
        _popen.assert_not_called()

    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_skips_when_no_peers(self, _popen):
        """Start skips when there is no peer relation."""
        self.charm.unit.status = ActiveStatus("ok")
        with (
            patch.object(type(self.charm), "peers", new=PropertyMock(return_value=None)),
            patch.object(self.charm, "unit_initialized", return_value=True),
        ):
            self.harness.set_can_connect(CONTAINER_NAME, True)
            self.manager.start_log_rotate_manager()
        _popen.assert_not_called()

    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_skips_when_cannot_connect(self, _popen):
        """Start skips when container not accessible."""
        self.charm.unit.status = ActiveStatus("ok")
        self.harness.set_can_connect(CONTAINER_NAME, False)
        self.manager.start_log_rotate_manager()
        _popen.assert_not_called()

    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_skips_when_not_initialized(self, _popen):
        """Start skips when unit not initialized."""
        self.charm.unit.status = ActiveStatus("ok")
        self.harness.set_can_connect(CONTAINER_NAME, True)
        with patch.object(self.charm, "unit_initialized", return_value=False):
            self.manager.start_log_rotate_manager()
        _popen.assert_not_called()

    @patch("services.managers.log_rotate_manager.os.kill")
    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_skips_when_process_running(self, _popen, _kill):
        """Start is a no-op when a manager process is already running."""
        self.charm.unit.status = ActiveStatus("ok")
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.charm.unit_peer_data["log-rotate-manager-pid"] = "12345"

        with patch.object(self.charm, "unit_initialized", return_value=True):
            self.manager.start_log_rotate_manager()

        _kill.assert_called_once_with(12345, 0)
        _popen.assert_not_called()

    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_restarts_when_process_dead(self, _popen):
        """Start launches a new process when the previous PID is dead."""
        self.charm.unit.status = ActiveStatus("ok")
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.charm.unit_peer_data["log-rotate-manager-pid"] = "999"
        _popen.return_value.pid = 4242

        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("services.managers.log_rotate_manager.os.kill", side_effect=OSError),
        ):
            self.manager.start_log_rotate_manager()

        _popen.assert_called_once()
        self.assertEqual(self.charm.unit_peer_data["log-rotate-manager-pid"], "4242")

    @patch("services.managers.log_rotate_manager.subprocess.Popen")
    def test_start_launches_new_process(self, _popen):
        """Start launches a new process when no PID stored."""
        self.charm.unit.status = ActiveStatus("ok")
        self.harness.set_can_connect(CONTAINER_NAME, True)
        _popen.return_value.pid = 99

        with patch.object(self.charm, "unit_initialized", return_value=True):
            self.manager.start_log_rotate_manager()

        _popen.assert_called_once()
        args, kwargs = _popen.call_args
        self.assertEqual(args[0][0], "/usr/bin/python3")
        self.assertEqual(args[0][1], "scripts/log_rotate_dispatcher.py")
        self.assertEqual(args[0][2], self.charm.unit.name)
        self.assertEqual(kwargs["env"].get("JUJU_CONTEXT_ID"), None)
        self.assertEqual(self.charm.unit_peer_data["log-rotate-manager-pid"], "99")

    # ------------------------------------------------------------------
    # stop_log_rotate_manager
    # ------------------------------------------------------------------

    @patch("services.managers.log_rotate_manager.os.kill")
    def test_stop_skips_when_no_peers(self, _kill):
        """Stop is a no-op when there is no peer relation."""
        with patch.object(type(self.charm), "peers", new=PropertyMock(return_value=None)):
            self.manager.stop_log_rotate_manager()
        _kill.assert_not_called()

    @patch("services.managers.log_rotate_manager.os.kill")
    def test_stop_skips_when_no_pid(self, _kill):
        """Stop is a no-op when no PID is stored."""
        self.manager.stop_log_rotate_manager()
        _kill.assert_not_called()

    @patch("services.managers.log_rotate_manager.os.kill")
    def test_stop_kills_and_clears_pid(self, _kill):
        """Stop sends SIGTERM and removes the PID from peer data."""
        self.charm.unit_peer_data["log-rotate-manager-pid"] = "555"
        self.manager.stop_log_rotate_manager()
        _kill.assert_called_once_with(555, 15)
        self.assertNotIn("log-rotate-manager-pid", self.charm.unit_peer_data)

    @patch("services.managers.log_rotate_manager.os.kill", side_effect=OSError)
    def test_stop_swallows_error_when_process_dead(self, _kill):
        """Stop silently ignores a dead process."""
        self.charm.unit_peer_data["log-rotate-manager-pid"] = "555"
        self.manager.stop_log_rotate_manager()
        _kill.assert_called_once_with(555, 15)


if __name__ == "__main__":
    unittest.main()
