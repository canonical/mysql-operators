# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, patch

from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import DB_RELATION_NAME

APP_NAME = "mysql-k8s"

SAMPLE_CLUSTER_STATUS = {
    "defaultReplicaSet": {
        "topology": {
            "mysql-k8s/0": {
                "address": "2.2.2.2:3306",
                "mode": "R/W",
                "status": "ONLINE",
            },
            "mysql-k8s/1": {
                "address": "2.2.2.1:3306",
                "mode": "R/O",
                "status": "gone_away",
            },
            "mysql-k8s/2": {
                "address": "2.2.2.3:3306",
                "mode": "R/O",
                "status": "ONLINE",
            },
        }
    }
}


class TestDatabase(unittest.TestCase):
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
            "mysql-k8s",
            {"cluster-name": "test_cluster", "cluster-set-domain-name": "test_cluster_set"},
        )
        self.database_relation_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(self.database_relation_id, "app/0")
        self.charm = self.harness.charm

    def tearDown(self) -> None:
        self.patcher.stop()

    @patch("charm.MySQLOperatorCharm._on_mysql_pebble_ready")
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="mysql-k8s.somedomain")
    @patch("mysql_k8s_helpers.MySQL.cluster_metadata_exists", return_value=True)
    @patch("charmlibs.rollingops._peer._backend._PeerRollingOpsBackend._process_locks")
    @patch("k8s_helpers.KubernetesHelpers.wait_service_ready")
    @patch("mysql_k8s_helpers.MySQL.update_endpoints")
    @patch("k8s_helpers.KubernetesHelpers.create_endpoint_services")
    @patch("mysql_k8s_helpers.MySQL.get_mysql_version", return_value="8.4.0")
    @patch("mysql_k8s_helpers.MySQL.create_database")
    @patch("mysql_k8s_helpers.MySQL.create_scoped_user")
    @patch(
        "relations.mysql_provider.generate_random_password", return_value="super_secure_password"
    )
    @patch("relations.mysql_provider.get_k8s_fqdn")
    def test_database_requested(
        self,
        mock_get_k8s_fqdn,
        _generate_random_password,
        _create_scoped_user,
        _create_database,
        _get_mysql_version,
        _create_endpoint_services,
        _update_endpoints,
        _wait_service_ready,
        _,
        _cluster_metadata_exists,
        _get_unit_address,
        _on_mysql_pebble_ready,
    ):
        mock_get_k8s_fqdn.side_effect = ["mysql-k8s-primary", "mysql-k8s-replicas"]

        # run start-up events to enable usage of the helper class
        self.harness.set_leader(True)
        self.harness.container_pebble_ready("mysql")
        self.charm.on.config_changed.emit()

        # confirm that the relation databag is empty
        database_relation_databag = self.harness.get_relation_data(
            self.database_relation_id, self.harness.charm.app
        )
        database_relation = self.charm.model.get_relation(DB_RELATION_NAME)
        app_unit = next(iter(database_relation.units))

        self.assertEqual(database_relation_databag, {})
        self.assertEqual(database_relation.data.get(app_unit), {})
        self.assertEqual(database_relation.data.get(self.charm.unit), {})

        # update the app leader unit data to trigger database_requested event
        self.harness.update_relation_data(
            self.database_relation_id, "app", {"database": "test_db"}
        )

        username = (
            f"relation-{self.database_relation_id}_{self.harness.model.uuid.replace('-', '')}"
        )[:26]
        self.assertEqual(
            database_relation_databag,
            {
                "data": '{"database": "test_db"}',
                "password": "super_secure_password",
                "username": username,
                "endpoints": "mysql-k8s-primary.:3306",
                "version": "8.4.0",
                "read-only-endpoints": "mysql-k8s-replicas.:3306",
                "database": "test_db",
            },
        )

        _generate_random_password.assert_called_once()
        _create_database.assert_called_once()
        _create_scoped_user.assert_called_once()
        _get_mysql_version.assert_called_once()
        # pods are labeled and the primary service awaited here
        _update_endpoints.assert_called_once()
        _wait_service_ready.assert_called_once()
        self.assertEqual(mock_get_k8s_fqdn.call_count, 2)

    def _set_up_healthy_cluster(self, mock_mysql):
        """Mock a healthy cluster for update-status tests."""
        # the update-status handler is wrapped in a rolling-ops manager
        self.harness.add_relation("rolling-ops", "rolling-ops")
        self.harness.set_can_connect("mysql", True)
        self.harness.set_leader(True)
        self.charm._mysql = mock_mysql
        self.charm.replication_offer = MagicMock(idle=True)
        self.charm.replication_consumer = MagicMock(idle=True)
        mock_mysql.is_mysqld_running.return_value = True
        mock_mysql.get_member_state.return_value = "ONLINE"
        mock_mysql.get_member_role.return_value = "PRIMARY"
        mock_mysql.is_cluster_replica.return_value = False

    @patch("charm.MySQLOperatorCharm._handle_potential_cluster_crash_scenario", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql")
    def test_update_status_blocked_on_incomplete_database_relation_setup(
        self, mock_mysql, _handle_potential_cluster_crash_scenario
    ):
        """update-status reports blocked while a database relation setup is incomplete.

        Regression test for https://github.com/canonical/mysql-operators/issues/327:
        when the database-relation-changed hook fails after the password is written
        to the provider databag (e.g. a transient DNS failure, or CREATE USER error
        1396 on hook retry), the relation data is never published. Subsequent
        update-status hooks must detect this situation and keep the unit blocked
        instead of overriding the status with an active one.
        """
        self._set_up_healthy_cluster(mock_mysql)

        # state left behind by the failed relation hook: the password is in the
        # provider databag, but endpoints/credentials were never published
        self.harness.update_relation_data(
            self.database_relation_id, APP_NAME, {"password": "super_secure_password"}
        )

        self.harness.charm.on.update_status.emit()

        self.assertEqual(self.charm.unit.status, BlockedStatus("Failed to create scoped user"))

    @patch("charm.MySQLOperatorCharm._handle_potential_cluster_crash_scenario", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql")
    def test_update_status_not_blocked_when_database_relation_setup_complete(
        self, mock_mysql, _handle_potential_cluster_crash_scenario
    ):
        """update-status only reports blocked while the relation setup is incomplete."""
        self._set_up_healthy_cluster(mock_mysql)

        # the relation hook completed: credentials and endpoints are published
        self.harness.update_relation_data(
            self.database_relation_id,
            APP_NAME,
            {"password": "super_secure_password", "endpoints": "mysql-k8s-primary.:3306"},
        )

        self.harness.charm.on.update_status.emit()

        self.assertEqual(self.charm.unit.status, ActiveStatus("Primary"))

    @patch("charm.MySQLOperatorCharm._handle_potential_cluster_crash_scenario", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql")
    def test_direct_update_status_call_blocked_on_incomplete_setup(
        self, mock_mysql, _handle_potential_cluster_crash_scenario
    ):
        """Direct _on_update_status calls keep the unit blocked on incomplete setup.

        The self-healing observer calls charm._on_update_status() directly every
        120 seconds without emitting an update_status event, so the provider's
        update-status handler never runs on that path. The charm's handler must
        not override the blocked status for the incomplete relation setup.

        See https://github.com/canonical/mysql-operators/issues/327
        """
        self._set_up_healthy_cluster(mock_mysql)

        # state left behind by the failed relation hook: the password is in the
        # provider databag, but endpoints/credentials were never published
        self.harness.update_relation_data(
            self.database_relation_id, APP_NAME, {"password": "super_secure_password"}
        )

        # replicate the self-healing observer's direct calls
        self.charm._on_update_status(None)
        self.charm.update_endpoints()

        self.assertEqual(self.charm.unit.status, BlockedStatus("Failed to create scoped user"))
