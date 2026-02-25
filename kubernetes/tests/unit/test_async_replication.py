# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import PropertyMock, patch

from charms.mysql.v0.async_replication import RELATION_CONSUMER, RELATION_OFFER
from ops.testing import Harness

from charm import MySQLOperatorCharm


@patch("charms.rolling_ops.v0.rollingops.RollingOpsManager._on_process_locks")
class TestAsyncReplicationRaceCondition(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peers_relation_id = self.harness.add_relation("database-peers", "mysql-k8s")
        self.charm = self.harness.charm

    @patch("ops.framework.EventBase.defer")
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=False),
    )
    def test_offer_created_defers_when_cluster_not_initialized(self, _is_peer_data_set, _defer, _):
        """Test that _on_offer_created defers when peer data is not set."""
        self.harness.set_leader(True)

        # Add the relation - this triggers _on_offer_created
        _ = self.harness.add_relation(RELATION_OFFER, "db2")

        # Assert that the event was deferred
        _defer.assert_called_once()

    @patch("ops.framework.EventBase.defer")
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=False),
    )
    def test_consumer_created_defers_when_cluster_not_initialized(
        self, _is_peer_data_set, _defer, _
    ):
        """Test that _on_consumer_relation_created defers when peer data is not set."""
        self.harness.set_leader(True)

        # Add the relation - this triggers _on_consumer_relation_created
        _ = self.harness.add_relation(RELATION_CONSUMER, "db2")

        # Assert that the event was deferred
        _defer.assert_called_once()
