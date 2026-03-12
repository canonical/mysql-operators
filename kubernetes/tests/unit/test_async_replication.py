# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import PropertyMock, patch

from ops.testing import Harness

from charm import MySQLOperatorCharm


class TestAsyncReplication(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = patch("lightkube.core.client.GenericSyncClient")
        self.patcher.start()
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peer_relation_id = self.harness.add_relation("database-peers", "database-peers")
        self.restart_relation_id = self.harness.add_relation("restart", "restart")
        self.harness.set_leader(True)

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock, return_value=False)
    @patch("ops.framework.EventBase.defer")
    def test_consumer_relation_created_deferred_when_peer_data_not_set(self, mock_defer, mock_peer_data):
        """Test that consumer relation created event is deferred when peer data is not set."""
        relation_id = self.harness.add_relation("replication", "remote")
        self.harness.add_relation_unit(relation_id, "remote/0")

        mock_defer.assert_called()

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock, return_value=False)
    @patch("ops.framework.EventBase.defer")
    def test_consumer_relation_changed_deferred_when_peer_data_not_set(self, mock_defer, mock_peer_data):
        """Test that consumer relation changed event is deferred when peer data is not set."""
        relation_id = self.harness.add_relation("replication", "remote")
        self.harness.add_relation_unit(relation_id, "remote/0")
        self.harness.update_relation_data(relation_id, "remote/0", {"key": "value"})

        mock_defer.assert_called()
