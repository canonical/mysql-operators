# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import COS_AGENT_RELATION_NAME, PEER


class TestLogRotationSetup(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peer_relation_id = self.harness.add_relation(PEER, "mysql")
        self.harness.update_relation_data(
            self.peer_relation_id,
            "mysql",
            {"cluster-name": "test_cluster", "cluster-set-domain-name": "test_cluster_set"},
        )
        self.charm = self.harness.charm

    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock,
        return_value=True,
    )
    def test_cos_relation_created(self, mock_is_peer_data_set, mock_setup):
        self.harness.add_relation(COS_AGENT_RELATION_NAME, "opentelemetry-collector")
        mock_setup.assert_called_once_with(3, self.charm.text_logs, False)
        mock_is_peer_data_set.assert_called_once()

    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock,
        return_value=True,
    )
    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    def test_log_syncing(self, mock_setup, mock_is_peer_data_set):
        self.harness.update_config({"logs-retention-period": "auto"})
        self.harness.add_relation(COS_AGENT_RELATION_NAME, "opentelemetry-collector")
        event = MagicMock()
        mock_setup.assert_called_once()
        mock_setup.reset_mock()
        self.charm.log_rotation_setup._update_logs_rotation(event)
        self.assertEqual(self.harness.charm.unit_peer_data["logs_synced"], "true")
        mock_setup.assert_called_once()

    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    def test_cos_relation_broken(self, mock_setup):
        self.harness.update_config({"logs-retention-period": "auto"})
        event = MagicMock()
        self.charm.log_rotation_setup._cos_relation_broken(event)
        self.assertNotIn("logs_synced", self.harness.charm.unit_peer_data)
        mock_setup.assert_called_once()

    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock,
        return_value=True,
    )
    def test_setup_with_numeric_retention(self, mock_is_peer_data_set, mock_setup):
        """setup() uses the numeric retention period when not `auto`."""
        self.harness.update_config({"logs-retention-period": "7"})
        self.charm.log_rotation_setup.setup()
        mock_setup.assert_called_once()
        # retention_period=7, text_logs, compress=True (no cos relation)
        args = mock_setup.call_args.args
        self.assertEqual(args[0], 7)

    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock,
        return_value=True,
    )
    def test_setup_auto_with_logs_syncing(self, mock_is_peer_data_set, mock_setup):
        """setup() uses retention 1 when auto and logs are syncing."""
        self.harness.update_config({"logs-retention-period": "auto"})
        self.charm.unit_peer_data["logs_synced"] = "true"
        self.charm.log_rotation_setup.setup()
        mock_setup.assert_called_once()
        args = mock_setup.call_args.args
        self.assertEqual(args[0], 1)

    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    def test_update_logs_rotation_already_syncing(self, mock_setup):
        """_update_logs_rotation is a no-op when logs already syncing."""
        self.harness.add_relation(COS_AGENT_RELATION_NAME, "opentelemetry-collector")
        self.charm.unit_peer_data["logs_synced"] = "true"
        event = MagicMock()
        self.charm.log_rotation_setup._update_logs_rotation(event)
        mock_setup.assert_not_called()

    @patch("mysql_vm_helpers.MySQL.setup_logrotate_and_cron")
    def test_update_logs_rotation_no_cos_relation(self, mock_setup):
        """_update_logs_rotation is a no-op when no COS relation."""
        event = MagicMock()
        self.charm.log_rotation_setup._update_logs_rotation(event)
        mock_setup.assert_not_called()

    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock,
        return_value=False,
    )
    def test_cos_relation_created_defers_when_peer_data_not_set(self, mock_is_peer_data_set):
        """_cos_relation_created defers when peer data is not set."""
        event = MagicMock()
        self.charm.log_rotation_setup._cos_relation_created(event)
        event.defer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
