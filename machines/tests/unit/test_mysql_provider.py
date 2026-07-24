# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, PropertyMock, patch

from charms.mysql.v0.mysql import (
    MySQLCreateApplicationDatabaseError,
    MySQLDeleteUserError,
    MySQLDeleteUsersForRelationError,
    MySQLGetClusterEndpointsError,
    MySQLRemoveRouterFromMetadataError,
)
from ops.model import BlockedStatus
from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import DB_RELATION_NAME, PEER


class TestMySQLProvider(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.peer_relation_id = self.harness.add_relation(PEER, "mysql")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/1")
        self.rolling_relation_id = self.harness.add_relation("rolling-ops", "rolling-ops")
        self.provider = self.charm.database_relation

    # ---- _get_username ----

    def test_get_username(self):
        """Username is derived from relation id and model uuid."""
        username = self.provider._get_username(42)
        self.assertTrue(username.startswith("relation-42_"))
        self.assertLessEqual(len(username), 26)

    # ---- _get_or_set_password ----

    def test_get_or_set_password_existing(self):
        """Returns existing password when already cached."""
        relation = Mock(id=5)
        with patch.object(self.provider.database, "fetch_my_relation_field", return_value="pw"):
            result = self.provider._get_or_set_password(relation)
        self.assertEqual(result, "pw")

    def test_get_or_set_password_new(self):
        """Generates and stores a new password when not cached."""
        relation = Mock(id=5)
        with (
            patch.object(self.provider.database, "fetch_my_relation_field", return_value=None),
            patch.object(self.provider.database, "update_relation_data") as mock_update,
        ):
            result = self.provider._get_or_set_password(relation)
        self.assertEqual(len(result), 24)
        mock_update.assert_called_once()

    # ---- _update_endpoints_all_relations ----

    def test_update_endpoints_all_relations_not_leader(self):
        """No-op when not leader."""
        self.provider._update_endpoints_all_relations(None)

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_update_endpoints_all_relations_no_relations(self, _cluster, _unit):
        """No-op when there are no database relations."""
        self.harness.set_leader()
        _cluster.return_value = True
        self.provider._update_endpoints_all_relations(None)

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_update_endpoints_all_relations_cluster_not_initialized(self, _cluster, _unit):
        """No-op when cluster not initialized."""
        self.harness.set_leader()
        _cluster.return_value = False
        self.harness.add_relation(DB_RELATION_NAME, "app")
        self.provider._update_endpoints_all_relations(None)

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_update_endpoints_all_relations_not_in_relation_data(self, _mysql, _cluster, _unit):
        """Skips relation when on_database_requested hasn't happened yet."""
        self.harness.set_leader()
        _cluster.return_value = True
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        with (
            patch.object(self.provider.database, "fetch_relation_data", return_value={}),
            patch.object(self.provider, "_update_endpoints") as mock_update,
        ):
            self.provider._update_endpoints_all_relations(None)
            mock_update.assert_not_called()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_update_endpoints_all_relations_success(self, _mysql, _cluster, _unit):
        """Updates endpoints for all relations that have been requested."""
        self.harness.set_leader()
        _cluster.return_value = True
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        with (
            patch.object(self.provider.database, "fetch_relation_data", return_value={rel_id: {}}),
            patch.object(self.provider, "_update_endpoints") as mock_update,
        ):
            self.provider._update_endpoints_all_relations(None)
        mock_update.assert_called_once()

    # ---- _update_endpoints ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_update_endpoints_unchanged(self, _mysql):
        """Skips update when endpoints haven't changed."""
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        self.harness.update_relation_data(
            rel_id, "mysql", {"endpoints": "rw", "read-only-endpoints": "ro"}
        )
        with (
            patch.object(self.charm, "get_cluster_endpoints", return_value=("rw", "ro", "")),
            patch.object(self.provider.database, "set_endpoints") as mock_set,
        ):
            self.provider._update_endpoints(rel_id, "app")
        mock_set.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_update_endpoints_changed(self, _mysql):
        """Updates endpoints when they have changed."""
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        with (
            patch.object(
                self.charm, "get_cluster_endpoints", return_value=("new_rw", "new_ro", "")
            ),
            patch.object(self.provider.database, "set_endpoints") as mock_set_rw,
            patch.object(self.provider.database, "set_read_only_endpoints") as mock_set_ro,
        ):
            self.provider._update_endpoints(rel_id, "app")
        mock_set_rw.assert_called_once_with(rel_id, "new_rw")
        mock_set_ro.assert_called_once_with(rel_id, "new_ro")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_update_endpoints_error(self, _mysql):
        """Handles MySQLGetClusterEndpointsError gracefully."""
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        with (
            patch.object(
                self.charm, "get_cluster_endpoints", side_effect=MySQLGetClusterEndpointsError
            ),
            patch.object(self.provider.database, "set_endpoints") as mock_set,
        ):
            self.provider._update_endpoints(rel_id, "app")
        mock_set.assert_not_called()

    # ---- _on_database_requested ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_database_requested_not_leader(self, _mysql):
        """No-op when not leader."""
        event = Mock()
        self.provider._on_database_requested(event)
        _mysql.return_value.create_database.assert_not_called()

    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_database_requested_cluster_not_initialized(self, _cluster):
        """Defers when cluster is not initialized."""
        self.harness.set_leader()
        _cluster.return_value = False
        event = Mock()
        self.provider._on_database_requested(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    @patch("relations.mysql_provider.generate_random_password", return_value="pass")
    @patch("charm.MySQLOperatorCharm.get_cluster_endpoints")
    def test_on_database_requested_router_role(self, _get_endpoints, _gen_pw, _cluster, _mysql):
        """Skips database creation when ROLE_ROUTER in extra_user_roles."""
        self.harness.set_leader()
        _cluster.return_value = True
        _get_endpoints.return_value = ("rw", "ro", "")
        _mysql.return_value.get_mysql_version.return_value = "8.4"

        with self.harness.hooks_disabled():
            rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
            self.harness.add_relation_unit(rel_id, "app/0")

        event = Mock()
        event.relation.id = rel_id
        event.app.name = "app"
        event.database = "test_db"
        event.extra_user_roles = "charmed_router"

        with (
            patch.object(self.provider.database, "fetch_my_relation_field", return_value=None),
            patch.object(self.provider.database, "update_relation_data"),
            patch.object(self.provider.database, "set_database"),
            patch.object(self.provider.database, "set_credentials"),
            patch.object(self.provider.database, "set_endpoints"),
            patch.object(self.provider.database, "set_version"),
            patch.object(self.provider.database, "set_read_only_endpoints"),
        ):
            self.provider._on_database_requested(event)
        _mysql.return_value.create_database.assert_not_called()
        _mysql.return_value.create_scoped_user.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    @patch("relations.mysql_provider.generate_random_password", return_value="pass")
    def test_on_database_requested_create_error(self, _gen_pw, _cluster, _mysql):
        """Sets blocked status when create_database fails."""
        self.harness.set_leader()
        _cluster.return_value = True
        _mysql.return_value.create_database.side_effect = MySQLCreateApplicationDatabaseError

        with self.harness.hooks_disabled():
            rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
            self.harness.add_relation_unit(rel_id, "app/0")

        event = Mock()
        event.relation.id = rel_id
        event.app.name = "app"
        event.database = "test_db"
        event.extra_user_roles = ""

        with (
            patch.object(self.provider.database, "fetch_my_relation_field", return_value=None),
            patch.object(self.provider.database, "update_relation_data"),
        ):
            self.provider._on_database_requested(event)
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    # ---- _on_database_broken ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_database_broken_not_leader(self, _mysql):
        """No-op when not leader."""
        event = Mock()
        self.provider._on_database_broken(event)
        _mysql.return_value.does_mysql_user_exist.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_database_broken_removing_unit(self, _removing, _mysql):
        """No-op when unit is being removed."""
        self.harness.set_leader()
        _removing.return_value = True
        event = Mock()
        self.provider._on_database_broken(event)
        _mysql.return_value.does_mysql_user_exist.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_database_broken_user_not_found(self, _removing, _mysql):
        """Logs warning when user does not exist."""
        self.harness.set_leader()
        _removing.return_value = False
        _mysql.return_value.does_mysql_user_exist.return_value = False
        event = Mock()
        event.relation.id = 1
        self.provider._on_database_broken(event)
        _mysql.return_value.delete_users_for_relation.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_database_broken_user_deleted(self, _removing, _mysql):
        """Deletes user when it exists."""
        self.harness.set_leader()
        _removing.return_value = False
        _mysql.return_value.does_mysql_user_exist.return_value = True
        event = Mock()
        event.relation.id = 1
        self.provider._on_database_broken(event)
        _mysql.return_value.delete_users_for_relation.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_database_broken_delete_error(self, _removing, _mysql):
        """Handles MySQLDeleteUsersForRelationError gracefully."""
        self.harness.set_leader()
        _removing.return_value = False
        _mysql.return_value.does_mysql_user_exist.return_value = True
        _mysql.return_value.delete_users_for_relation.side_effect = (
            MySQLDeleteUsersForRelationError
        )
        event = Mock()
        event.relation.id = 1
        # should not raise
        self.provider._on_database_broken(event)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_database_broken_key_error(self, _removing, _mysql):
        """Handles KeyError gracefully."""
        self.harness.set_leader()
        _removing.return_value = False
        _mysql.return_value.does_mysql_user_exist.return_value = True
        _mysql.return_value.delete_users_for_relation.side_effect = KeyError
        event = Mock()
        event.relation.id = 1
        self.provider._on_database_broken(event)

    # ---- _on_database_provides_relation_departed ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_not_leader(self, _mysql):
        """No-op when not leader."""
        event = Mock()
        self.provider._on_database_provides_relation_departed(event)
        _mysql.return_value.get_mysql_router_users_for_unit.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_same_app(self, _mysql):
        """No-op when departing unit belongs to same app."""
        self.harness.set_leader()
        event = Mock()
        event.departing_unit.app.name = self.charm.app.name
        self.provider._on_database_provides_relation_departed(event)
        _mysql.return_value.get_mysql_router_users_for_unit.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_no_users(self, _mysql):
        """No-op when no router users found."""
        self.harness.set_leader()
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = []
        event = Mock()
        event.departing_unit.app.name = "other-app"
        event.departing_unit.name = "other-app/0"
        event.relation.id = 1
        self.provider._on_database_provides_relation_departed(event)
        _mysql.return_value.delete_user.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_multiple_users(self, _mysql):
        """No-op when more than one router user found."""
        self.harness.set_leader()
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [
            Mock(username="u1", attributes={}),
            Mock(username="u2", attributes={}),
        ]
        event = Mock()
        event.departing_unit.app.name = "other-app"
        event.departing_unit.name = "other-app/0"
        event.relation.id = 1
        self.provider._on_database_provides_relation_departed(event)
        _mysql.return_value.delete_user.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_success(self, _mysql):
        """Deletes user and removes router from metadata."""
        self.harness.set_leader()
        user = Mock(username="router_user", attributes={"router_id": "rid-123"})
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [user]
        event = Mock()
        event.departing_unit.app.name = "other-app"
        event.departing_unit.name = "other-app/0"
        event.relation.id = 1
        self.provider._on_database_provides_relation_departed(event)
        _mysql.return_value.delete_user.assert_called_once_with("router_user")
        _mysql.return_value.remove_router_from_cluster_metadata.assert_called_once_with("rid-123")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_delete_error(self, _mysql):
        """Handles MySQLDeleteUserError gracefully."""
        self.harness.set_leader()
        user = Mock(username="router_user", attributes={"router_id": "rid-123"})
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [user]
        _mysql.return_value.delete_user.side_effect = MySQLDeleteUserError
        event = Mock()
        event.departing_unit.app.name = "other-app"
        event.departing_unit.name = "other-app/0"
        event.relation.id = 1
        # should not raise
        self.provider._on_database_provides_relation_departed(event)
        _mysql.return_value.remove_router_from_cluster_metadata.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_db_provides_relation_departed_remove_metadata_error(self, _mysql):
        """Handles MySQLRemoveRouterFromMetadataError gracefully."""
        self.harness.set_leader()
        user = Mock(username="router_user", attributes={"router_id": "rid-123"})
        _mysql.return_value.get_mysql_router_users_for_unit.return_value = [user]
        _mysql.return_value.remove_router_from_cluster_metadata.side_effect = (
            MySQLRemoveRouterFromMetadataError
        )
        event = Mock()
        event.departing_unit.app.name = "other-app"
        event.departing_unit.name = "other-app/0"
        event.relation.id = 1
        # should not raise
        self.provider._on_database_provides_relation_departed(event)

    # ---- _on_relation_departed ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_relation_departed_not_leader(self, _mysql):
        """No-op when not leader."""
        event = Mock()
        self.provider._on_relation_departed(event)
        _mysql.return_value.is_instance_in_cluster.assert_not_called()

    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_departed_no_relations(self, _cluster):
        """No-op when there are no database relations."""
        self.harness.set_leader()
        _cluster.return_value = True
        event = Mock()
        self.provider._on_relation_departed(event)

    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_departed_cluster_not_initialized(self, _cluster):
        """No-op when cluster not initialized."""
        self.harness.set_leader()
        _cluster.return_value = False
        self.harness.add_relation(DB_RELATION_NAME, "app")
        event = Mock()
        self.provider._on_relation_departed(event)

    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_departed_leader_departing(self, _cluster):
        """No-op when the leader unit is departing."""
        self.harness.set_leader()
        _cluster.return_value = True
        self.harness.add_relation(DB_RELATION_NAME, "app")
        event = Mock()
        event.departing_unit.name = self.charm.unit.name
        self.provider._on_relation_departed(event)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_departed_unit_still_in_cluster(self, _cluster, _mysql):
        """Defers when departing unit is still in the cluster."""
        self.harness.set_leader()
        _cluster.return_value = True
        self.harness.add_relation(DB_RELATION_NAME, "app")
        _mysql.return_value.is_instance_in_cluster.return_value = True
        event = Mock()
        event.departing_unit.name = "mysql/1"
        event.departing_unit.app.name = "mysql"
        event.app.name = "mysql"
        self.provider._on_relation_departed(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_departed_success(self, _cluster, _mysql):
        """Updates endpoints when departing unit is no longer in cluster."""
        self.harness.set_leader()
        _cluster.return_value = True
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        _mysql.return_value.is_instance_in_cluster.return_value = False
        with (
            patch.object(self.provider.database, "fetch_relation_data", return_value={rel_id: {}}),
            patch.object(self.provider, "_update_endpoints") as mock_update,
        ):
            event = Mock()
            event.departing_unit.name = "mysql/1"
            event.departing_unit.app.name = "mysql"
            event.app.name = "mysql"
            self.provider._on_relation_departed(event)
        mock_update.assert_called_once()

    # ---- _on_relation_joined ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_relation_joined_not_leader(self, _mysql):
        """No-op when not leader."""
        event = Mock()
        self.provider._on_relation_joined(event)
        _mysql.return_value.is_instance_in_cluster.assert_not_called()

    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_joined_no_relations(self, _cluster):
        """No-op when there are no database relations."""
        self.harness.set_leader()
        _cluster.return_value = True
        event = Mock()
        self.provider._on_relation_joined(event)

    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_joined_cluster_not_initialized(self, _cluster):
        """No-op when cluster not initialized."""
        self.harness.set_leader()
        _cluster.return_value = False
        self.harness.add_relation(DB_RELATION_NAME, "app")
        event = Mock()
        self.provider._on_relation_joined(event)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_joined_refresh_none(self, _cluster, _mysql):
        """Continues (doesn't defer) when refresh is None but unit not in cluster."""
        self.harness.set_leader()
        _cluster.return_value = True
        self.harness.add_relation(DB_RELATION_NAME, "app")
        _mysql.return_value.is_instance_in_cluster.return_value = False
        event = Mock()
        event.unit.name = "mysql/1"
        event.app.name = "mysql"
        with patch.object(self.charm, "_refresh", None):
            self.provider._on_relation_joined(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_joined_refresh_in_progress(self, _cluster, _mysql):
        """Defers when refresh is in progress."""
        self.harness.set_leader()
        _cluster.return_value = True
        self.harness.add_relation(DB_RELATION_NAME, "app")
        mock_refresh = Mock()
        mock_refresh.in_progress = True
        event = Mock()
        event.unit.name = "mysql/1"
        event.app.name = "mysql"
        with patch.object(self.charm, "_refresh", mock_refresh):
            self.provider._on_relation_joined(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_joined_unit_not_in_cluster(self, _cluster, _mysql):
        """Defers when joined unit is not yet in the cluster."""
        self.harness.set_leader()
        _cluster.return_value = True
        self.harness.add_relation(DB_RELATION_NAME, "app")
        _mysql.return_value.is_instance_in_cluster.return_value = False
        mock_refresh = Mock()
        mock_refresh.in_progress = False
        event = Mock()
        event.unit.name = "mysql/1"
        event.app.name = "mysql"
        with patch.object(self.charm, "_refresh", mock_refresh):
            self.provider._on_relation_joined(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    def test_on_relation_joined_success(self, _cluster, _mysql):
        """Updates endpoints when joined unit is in the cluster."""
        self.harness.set_leader()
        _cluster.return_value = True
        rel_id = self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation_unit(rel_id, "app/0")
        _mysql.return_value.is_instance_in_cluster.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = False
        with (
            patch.object(self.provider.database, "fetch_relation_data", return_value={rel_id: {}}),
            patch.object(self.provider, "_update_endpoints") as mock_update,
        ):
            event = Mock()
            event.unit.name = "mysql/1"
            event.app.name = "mysql"
            with patch.object(self.charm, "_refresh", mock_refresh):
                self.provider._on_relation_joined(event)
        mock_update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
