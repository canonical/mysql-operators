# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from ops.model import BlockedStatus
from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import CONTAINER_NAME, DB_RELATION_NAME

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
        self.rolling_relation_id = self.harness.add_relation("rolling-ops", "rolling-ops")
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def test_get_username(self):
        """_get_username builds a unique username from relation id and model uuid."""
        username = self.charm.database_relation._get_username(self.database_relation_id)
        expected = (
            f"relation-{self.database_relation_id}_{self.harness.model.uuid.replace('-', '')}"[:26]
        )
        self.assertEqual(username, expected)

    # ------------------------------------------------------------------
    # _on_database_requested - early returns
    # ------------------------------------------------------------------

    def test_database_requested_non_leader(self):
        """_on_database_requested is a no-op for non-leader."""
        event = MagicMock()
        self.charm.database_relation._on_database_requested(event)
        # Should return early; no exception raised

    @patch(
        "charm.MySQLOperatorCharm.cluster_initialized",
        new_callable=PropertyMock,
        return_value=False,
    )
    @patch("ops.model.Unit.is_leader", return_value=True)
    def test_database_requested_defers_when_cluster_not_ready(self, _is_leader, _cluster_init):
        """_on_database_requested defers when cluster not initialized."""
        self.harness.set_can_connect(CONTAINER_NAME, True)
        event = MagicMock()
        self.charm.database_relation._on_database_requested(event)
        event.defer.assert_called_once()

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
    @patch("relations.mysql_provider.generate_random_password", return_value="pass")
    @patch("relations.mysql_provider.get_k8s_fqdn")
    def test_database_requested_create_user_error(
        self,
        mock_get_k8s_fqdn,
        _gen,
        mock_scoped,
        _create_db,
        _get_mysql_version,
        _create_endpoint_services,
        _update_endpoints,
        _wait_service_ready,
        _,
        _cluster_metadata_exists,
        _get_unit_address,
        _on_mysql_pebble_ready,
    ):
        """_on_database_requested sets Blocked when create_scoped_user fails."""
        from charms.mysql.v0.mysql import MySQLCreateApplicationScopedUserError

        mock_get_k8s_fqdn.side_effect = ["primary", "replicas"]
        mock_scoped.side_effect = MySQLCreateApplicationScopedUserError

        self.harness.set_can_connect(CONTAINER_NAME, True)
        self.harness.set_leader(True)
        self.harness.container_pebble_ready("mysql")
        self.charm.on.config_changed.emit()

        self.harness.update_relation_data(
            self.database_relation_id, "app", {"database": "test_db"}
        )
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

    # ------------------------------------------------------------------
    # _on_database_broken
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_database_broken_non_leader(self, _mysql):
        """_on_database_broken is a no-op for non-leader."""
        event = MagicMock()
        self.charm.database_relation._on_database_broken(event)
        _mysql.return_value.delete_users_for_relation.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_database_broken_removing_unit(self, _mysql):
        """_on_database_broken is a no-op when unit is being removed."""
        self.harness.set_leader()
        self.charm.unit_peer_data["unit-status"] = "removing"
        event = MagicMock()
        self.charm.database_relation._on_database_broken(event)
        _mysql.return_value.delete_users_for_relation.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_database_broken_deletes_users(self, _mysql):
        """_on_database_broken deletes users when they exist."""
        self.harness.set_leader()
        _mysql.return_value.does_mysql_user_exist.return_value = True
        event = MagicMock()
        event.relation.id = self.database_relation_id
        self.charm.database_relation._on_database_broken(event)
        _mysql.return_value.delete_users_for_relation.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_database_broken_no_users(self, _mysql):
        """_on_database_broken is a no-op when users don't exist."""
        self.harness.set_leader()
        _mysql.return_value.does_mysql_user_exist.return_value = False
        event = MagicMock()
        event.relation.id = self.database_relation_id
        self.charm.database_relation._on_database_broken(event)
        _mysql.return_value.delete_users_for_relation.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_database_broken_delete_error(self, _mysql):
        """_on_database_broken swallows MySQLDeleteUsersForRelationError."""
        from charms.mysql.v0.mysql import MySQLDeleteUsersForRelationError

        self.harness.set_leader()
        _mysql.return_value.does_mysql_user_exist.return_value = True
        _mysql.return_value.delete_users_for_relation.side_effect = (
            MySQLDeleteUsersForRelationError
        )
        event = MagicMock()
        event.relation.id = self.database_relation_id
        # Should not raise
        self.charm.database_relation._on_database_broken(event)

    # ------------------------------------------------------------------
    # _on_database_provides_relation_departed
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_relation_departed_non_leader(self, _mysql):
        """_on_database_provides_relation_departed is a no-op for non-leader."""
        event = MagicMock()
        self.charm.database_relation._on_database_provides_relation_departed(event)
        _mysql.return_value.get_mysql_router_users_for_unit.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_relation_departed_same_app(self, _mysql):
        """_on_database_provides_relation_departed is a no-op for same-app departures."""
        self.harness.set_leader()
        event = MagicMock()
        event.departing_unit.app.name = self.charm.app.name
        self.charm.database_relation._on_database_provides_relation_departed(event)
        _mysql.return_value.get_mysql_router_users_for_unit.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_relation_departed_no_users(self, _mysql):
        """_on_database_provides_relation_departed is a no-op when no router users."""
        self.harness.set_leader()
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = []
        event = MagicMock()
        event.departing_unit.app.name = "other-app"
        self.charm.database_relation._on_database_provides_relation_departed(event)
        _mysql.return_value.delete_user.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_relation_departed_multiple_users(self, _mysql):
        """_on_database_provides_relation_departed logs error for multiple router users."""
        self.harness.set_leader()
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [
            MagicMock(username="u1"),
            MagicMock(username="u2"),
        ]
        event = MagicMock()
        event.departing_unit.app.name = "other-app"
        self.charm.database_relation._on_database_provides_relation_departed(event)
        _mysql.return_value.delete_user.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_relation_departed_removes_router(self, _mysql):
        """_on_database_provides_relation_departed deletes router user and metadata."""
        user = MagicMock()
        user.username = "router-user"
        user.attributes = {"router_id": "router-123"}
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [user]
        self.harness.set_leader()
        event = MagicMock()
        event.relation.id = self.database_relation_id
        event.departing_unit.name = "router/0"
        event.departing_unit.app.name = "other-app"

        self.charm.database_relation._on_database_provides_relation_departed(event)

        _mysql.return_value.delete_user.assert_called_once_with("router-user")
        _mysql.return_value.remove_router_from_cluster_metadata.assert_called_once_with(
            "router-123"
        )

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_relation_departed_swallows_errors(self, _mysql):
        """_on_database_provides_relation_departed swallows delete/metadata errors."""
        from charms.mysql.v0.mysql import MySQLDeleteUserError, MySQLRemoveRouterFromMetadataError

        user = MagicMock()
        user.username = "router-user"
        user.attributes = {"router_id": "router-123"}
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [user]
        _mysql.return_value.delete_user.side_effect = MySQLDeleteUserError
        _mysql.return_value.remove_router_from_cluster_metadata.side_effect = (
            MySQLRemoveRouterFromMetadataError
        )
        self.harness.set_leader()
        event = MagicMock()
        event.relation.id = self.database_relation_id
        event.departing_unit.name = "router/0"
        event.departing_unit.app.name = "other-app"

        # Should not raise
        self.charm.database_relation._on_database_provides_relation_departed(event)

    # ------------------------------------------------------------------
    # _configure_endpoints
    # ------------------------------------------------------------------

    def test_configure_endpoints_cannot_connect(self):
        """_configure_endpoints is a no-op when container not accessible."""
        self.harness.set_can_connect(CONTAINER_NAME, False)
        self.charm.database_relation._configure_endpoints(None)
        # No exception; no endpoint update

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_configure_endpoints_not_initialized(self, _mysql):
        """_configure_endpoints is a no-op when unit not initialized."""
        self.harness.set_can_connect(CONTAINER_NAME, True)
        with patch.object(self.charm, "unit_initialized", return_value=False):
            self.charm.database_relation._configure_endpoints(None)
        _mysql.return_value.update_endpoints.assert_not_called()

    # ------------------------------------------------------------------
    # _on_update_status
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._is_cluster_blocked", return_value=True)
    def test_update_status_cluster_blocked(self, _blocked):
        """_on_update_status is a no-op when cluster is blocked."""
        self.charm.database_relation._on_update_status(None)

    @patch("charm.MySQLOperatorCharm._is_cluster_blocked", return_value=False)
    def test_update_status_refresh_none(self, _blocked):
        """_on_update_status is a no-op when refresh is None."""
        self.charm._refresh = None
        self.charm.database_relation._on_update_status(None)

    @patch("charm.MySQLOperatorCharm._is_cluster_blocked", return_value=False)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_update_status_cannot_connect(self, _mysql, _blocked):
        """_on_update_status is a no-op when container not accessible."""
        self.harness.set_can_connect(CONTAINER_NAME, False)
        self.charm.database_relation._on_update_status(None)
        _mysql.return_value.update_endpoints.assert_not_called()
