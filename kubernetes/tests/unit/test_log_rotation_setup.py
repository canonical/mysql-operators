# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import CONTAINER_NAME, COS_LOGGING_RELATION_NAME

APP_NAME = "mysql-k8s"


class TestLogRotationSetup(unittest.TestCase):
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
        self.log_rotate_setup = self.charm.log_rotate_setup

    def tearDown(self):
        self.patcher.stop()

    # ------------------------------------------------------------------
    # setup()
    # ------------------------------------------------------------------

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=False
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_setup_auto_not_syncing(self, mock_setup, _has_cos):
        """setup() uses retention=3 when auto and logs not syncing."""
        self.harness.update_config({"logs-retention-period": "auto"})
        self.log_rotate_setup.setup()

        mock_setup.assert_called_once_with(3, self.charm.text_logs, True)

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=False
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_setup_auto_syncing(self, mock_setup, _has_cos):
        """setup() uses retention=1 when auto and logs syncing."""
        self.harness.update_config({"logs-retention-period": "auto"})
        self.charm.unit_peer_data["logs_synced"] = "true"
        self.log_rotate_setup.setup()

        mock_setup.assert_called_once_with(1, self.charm.text_logs, True)

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=True
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_setup_auto_with_cos_no_sync(self, mock_setup, _has_cos):
        """setup() disables compression when COS relation present and not syncing."""
        self.harness.update_config({"logs-retention-period": "auto"})
        self.log_rotate_setup.setup()

        mock_setup.assert_called_once_with(3, self.charm.text_logs, False)

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=False
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_setup_numeric_retention(self, mock_setup, _has_cos):
        """setup() uses the numeric retention period when not auto."""
        self.harness.update_config({"logs-retention-period": "7"})
        self.log_rotate_setup.setup()

        mock_setup.assert_called_once_with(7, self.charm.text_logs, True)

    # ------------------------------------------------------------------
    # _update_logs_rotation()
    # ------------------------------------------------------------------

    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_update_logs_rotation_no_cos_relation(self, mock_setup):
        """_update_logs_rotation is a no-op when no COS relation."""
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.log_rotate_setup._update_logs_rotation(MagicMock())

        mock_setup.assert_not_called()

    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_update_logs_rotation_cannot_connect(self, mock_setup):
        """_update_logs_rotation is a no-op when container not accessible."""
        self.harness.add_relation(COS_LOGGING_RELATION_NAME, "loki")
        self.harness.set_can_connect(CONTAINER_NAME, False)
        self.log_rotate_setup._update_logs_rotation(MagicMock())

        mock_setup.assert_not_called()

    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_update_logs_rotation_already_syncing(self, mock_setup):
        """_update_logs_rotation is a no-op when logs already syncing."""
        self.harness.add_relation(COS_LOGGING_RELATION_NAME, "loki")
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.charm.unit_peer_data["logs_synced"] = "true"
        self.log_rotate_setup._update_logs_rotation(MagicMock())

        mock_setup.assert_not_called()

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=True
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_update_logs_rotation_triggers_setup(self, mock_setup, _has_cos):
        """_update_logs_rotation sets logs_synced and reconfigures when logs start syncing."""
        self.harness.add_relation(COS_LOGGING_RELATION_NAME, "loki")
        self.harness.set_can_connect(CONTAINER_NAME, True)

        self.log_rotate_setup._update_logs_rotation(MagicMock())

        self.assertEqual(self.charm.unit_peer_data["logs_synced"], "true")
        mock_setup.assert_called_once()

    # ------------------------------------------------------------------
    # _cos_relation_created()
    # ------------------------------------------------------------------

    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_cos_relation_created_cannot_connect(self, mock_setup):
        """_cos_relation_created is a no-op when container not accessible."""
        self.harness.set_can_connect(CONTAINER_NAME, False)
        event = MagicMock()
        self.log_rotate_setup._cos_relation_created(event)

        mock_setup.assert_not_called()
        event.defer.assert_not_called()

    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_cos_relation_created_defers_without_cluster_name(self, mock_setup):
        """_cos_relation_created defers when cluster name not set."""
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.harness.update_relation_data(self.peer_relation_id, APP_NAME, {"cluster-name": ""})

        event = MagicMock()
        self.log_rotate_setup._cos_relation_created(event)

        mock_setup.assert_not_called()
        event.defer.assert_called_once()

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=True
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_cos_relation_created_triggers_setup(self, mock_setup, _has_cos):
        """_cos_relation_created calls setup when cluster name is set."""
        self.harness.set_can_connect(CONTAINER_NAME, True)

        self.log_rotate_setup._cos_relation_created(MagicMock())

        mock_setup.assert_called_once()

    # ------------------------------------------------------------------
    # _cos_relation_broken()
    # ------------------------------------------------------------------

    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_cos_relation_broken_cannot_connect(self, mock_setup):
        """_cos_relation_broken is a no-op when container not accessible."""
        self.harness.set_can_connect(CONTAINER_NAME, False)
        self.log_rotate_setup._cos_relation_broken(MagicMock())

        mock_setup.assert_not_called()

    @patch(
        "charm.MySQLOperatorCharm.has_cos_relation", new_callable=PropertyMock, return_value=False
    )
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    def test_cos_relation_broken_clears_sync_and_setup(self, mock_setup, _has_cos):
        """_cos_relation_broken removes logs_synced and reconfigures."""
        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.charm.unit_peer_data["logs_synced"] = "true"

        self.log_rotate_setup._cos_relation_broken(MagicMock())

        self.assertNotIn("logs_synced", self.charm.unit_peer_data)
        mock_setup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
