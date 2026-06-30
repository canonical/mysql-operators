# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

from charms.mysql.v0.mysql import MySQLCharmBase, MySQLSecretError
from ops.model import RelationDataTypeError
from ops.testing import Harness
from parameterized import parameterized

SHORT_CLUSTER_TOPOLOGY = {
    "mysql-0": {
        "address": "mysql-0.mysql-endpoints:3306",
        "memberRole": "SECONDARY",
        "mode": "R/O",
        "status": "ONLINE",
    },
    "mysql-1": {
        "address": "mysql-1.mysql-endpoints:3306",
        "memberRole": "PRIMARY",
        "mode": "R/W",
        "status": "ONLINE",
    },
    "mysql-2": {
        "address": "mysql-2.mysql-endpoints:3306",
        "memberRole": "",
        "mode": "R/O",
        "status": "OFFLINE",
    },
}


class TestCharmBase(unittest.TestCase):
    @patch.multiple(MySQLCharmBase, __abstractmethods__=set())
    def setUp(self):
        self.harness = Harness(
            MySQLCharmBase,
            meta=Path("metadata.yaml").read_text(),
            actions=Path("actions.yaml").read_text(),
        )
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.peer_relation_id = self.harness.add_relation("database-peers", "mysql")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/1")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/2")

    @patch("charm.MySQLCharmBase.get_unit_address")
    @patch("charm.MySQLCharmBase._mysql")
    def test_get_cluster_endpoints(self, _mysql, _get_unit_address):
        """Test get_cluster_endpoints() method."""
        _mysql.is_cluster_replica.return_value = False
        _mysql.get_cluster_topology.return_value = SHORT_CLUSTER_TOPOLOGY

        _mocked_address = "mysql-N.mysql-endpoints"
        _get_unit_address.return_value = _mocked_address

        rw, ro, no = self.charm.get_cluster_endpoints("database-peers")

        self.assertEqual(rw, f"{_mocked_address}:3306")
        self.assertEqual(ro, f"{_mocked_address}:3306")
        self.assertEqual(no, f"{_mocked_address}:3306")

    @parameterized.expand([("app"), ("unit")])
    def test_set_secret(self, scope):
        self.harness.set_leader()

        self.charm.set_secret(scope, "password", "test-password")
        assert self.charm.get_secret(scope, "password") == "test-password"

        self.charm.set_secret(scope, "password", None)
        assert self.charm.get_secret(scope, "password") is None

        with self.assertRaises(MySQLSecretError):
            self.charm.set_secret("not-a-scope", "password", "test")  # type: ignore

    @parameterized.expand([("app", True), ("unit", True), ("unit", False)])
    def test_set_reset_new_secret(self, scope, is_leader):
        """NOTE: currently ops.testing seems to allow for non-leader to set secrets too!"""
        # App has to be leader, unit can be either
        self.harness.set_leader(is_leader)
        # Getting current password
        self.harness.charm.set_secret(scope, "new-secret", "bla")
        assert self.harness.charm.get_secret(scope, "new-secret") == "bla"

        # Reset new secret
        self.harness.charm.set_secret(scope, "new-secret", "blablabla")
        assert self.harness.charm.get_secret(scope, "new-secret") == "blablabla"

        # Set another new secret
        self.harness.charm.set_secret(scope, "new-secret2", "blablabla")
        assert self.harness.charm.get_secret(scope, "new-secret2") == "blablabla"

    @parameterized.expand([("app", True), ("unit", True), ("unit", False)])
    def test_invalid_secret(self, scope, is_leader):
        # App has to be leader, unit can be either
        self.harness.set_leader(is_leader)

        with self.assertRaises((TypeError, RelationDataTypeError)):
            self.harness.charm.set_secret(scope, "somekey", 1)  # type: ignore

        self.harness.charm.set_secret(scope, "somekey", "")
        assert self.harness.charm.get_secret(scope, "somekey") is None

    def test_delete_existing_password_secrets(self):
        """NOTE: currently ops.testing seems to allow for non-leader to remove secrets too!"""
        self.harness.set_leader()
        self.harness.charm.set_secret("app", "replication", "somepw")
        self.harness.charm.set_secret("app", "replication", "")
        assert self.harness.charm.get_secret("app", "replication") is None

        self.harness.charm.set_secret("unit", "somekey", "somesecret")
        self.harness.charm.set_secret("unit", "somekey", "")
        assert self.harness.charm.get_secret("unit", "somekey") is None

        # Ensure deleting non-existing secrets does not raise errors
        self.harness.charm.remove_secret("app", "root-password")
        self.harness.charm.remove_secret("unit", "root-password")
        self.harness.charm.remove_secret("app", "non-existing-secret")
        self.harness.charm.remove_secret("unit", "non-existing-secret")

    def test_abstract_methods(self):
        """Test abstract methods."""
        with self.assertRaises(NotImplementedError):
            self.harness.charm.get_unit_hostname()

        with self.assertRaises(NotImplementedError):
            _ = self.harness.charm._mysql

    @patch("charms.mysql.v0.mysql.MySQLCharmBase._mysql", new_callable=PropertyMock)
    def test_set_password_restarts_exporter_for_monitoring_user(self, _mysql):
        """Rotating the monitoring password always restarts the exporter."""
        self.charm.replication_offer = Mock(role=Mock(relation_side="replication-offer"))
        self.harness.set_leader()
        self.harness.update_relation_data(
            self.peer_relation_id,
            "mysql",
            {"cluster-name": "test-cluster", "cluster-set-domain-name": "test-set"},
        )

        self.harness.run_action(
            "set-password", {"username": "charmed-stats", "password": "newpass123"}
        )

        _mysql.return_value.update_user_password.assert_called_once_with(
            "charmed-stats", "newpass123"
        )
        _mysql.return_value.restart_mysql_exporter.assert_called_once()

    @patch("charms.mysql.v0.mysql.MySQLCharmBase._mysql", new_callable=PropertyMock)
    def test_set_password_does_not_restart_exporter_for_other_users(self, _mysql):
        """Rotating a non-monitoring password does not restart the exporter."""
        self.charm.replication_offer = Mock(role=Mock(relation_side="replication-offer"))
        self.harness.set_leader()
        self.harness.update_relation_data(
            self.peer_relation_id,
            "mysql",
            {"cluster-name": "test-cluster", "cluster-set-domain-name": "test-set"},
        )

        self.harness.run_action(
            "set-password", {"username": "charmed-operator", "password": "newpass123"}
        )

        _mysql.return_value.update_user_password.assert_called_once_with(
            "charmed-operator", "newpass123"
        )
        _mysql.return_value.restart_mysql_exporter.assert_not_called()
