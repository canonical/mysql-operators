# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import Mock, PropertyMock, patch

from charmlibs.rollingops import OperationResult
from charms.grafana_agent.v0.cos_agent import ProtocolNotFoundError
from charms.mysql.v0.async_replication import RELATION_CONSUMER, RELATION_OFFER
from charms.mysql.v0.mysql import (
    InstanceState,
    MySQLAddInstanceToClusterError,
    MySQLConfigureInstanceError,
    MySQLConfigureMySQLUsersError,
    MySQLCreateClusterError,
    MySQLGetClusterPrimaryAddressError,
    MySQLInitializeJujuOperationsTableError,
    MySQLLockAcquisitionError,
    MySQLRebootFromCompleteOutageError,
    MySQLRejoinInstanceToClusterError,
)
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.testing import Harness
from tenacity import Retrying, stop_after_attempt

from charm import MySQLOperatorCharm, StorageUnavailableError
from constants import (
    DB_RELATION_NAME,
    PEER,
)
from mysql_vm_helpers import (
    MySQLCreateCustomMySQLDConfigError,
    MySQLSetOperatorUserAndStartMySQLDError,
    SnapServiceOperationError,
)


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.peer_relation_id = self.harness.add_relation("database-peers", "database-peers")
        self.rolling_relation_id = self.harness.add_relation("rolling-ops", "rolling-ops")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/1")

    @patch("socket.getfqdn", return_value="test-hostname")
    @patch("socket.gethostbyname", return_value="")
    @patch("subprocess.run")
    @patch("mysql_vm_helpers.is_volume_mounted", return_value=True)
    @patch("mysql_vm_helpers.MySQL.install_and_configure_mysql_dependencies")
    def test_on_install(self, _install_and_configure_mysql_dependencies, ___, __, _, _____):
        self.charm.on.install.emit()
        _install_and_configure_mysql_dependencies.assert_called_once()

        self.assertTrue(isinstance(self.harness.model.unit.status, WaitingStatus))

    @patch("charm.Retrying", return_value=Retrying(stop=stop_after_attempt(1)))
    @patch("subprocess.run")
    @patch("mysql_vm_helpers.is_volume_mounted", return_value=True)
    @patch(
        "mysql_vm_helpers.MySQL.install_and_configure_mysql_dependencies", side_effect=Exception()
    )
    def test_on_install_exception(
        self,
        _install_and_configure_mysql_dependencies,
        _is_volume_mounted,
        _check_call,
        _retrying,
    ):
        self.charm.on.install.emit()

        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

    def test_on_leader_elected_sets_mysql_passwords_secret(self):
        # ensure that the peer relation databag is empty
        peer_relation_databag = self.harness.get_relation_data(
            self.peer_relation_id, self.harness.charm.app
        )
        self.assertEqual(peer_relation_databag, {})

        # trigger the leader_elected event
        self.harness.set_leader(True)

        expected_peer_relation_databag_keys = [
            "operator-password",
            "replication-password",
            "monitoring-password",
            "backups-password",
        ]

        for key in expected_peer_relation_databag_keys:
            self.assertTrue(self.harness.charm.get_secret("app", key).isalnum())

    def test_on_leader_elected_sets_config_cluster_name_in_peer_databag(self):
        # ensure that the peer relation databag is empty
        peer_relation_databag = self.harness.get_relation_data(
            self.peer_relation_id, self.harness.charm.app
        )
        self.assertEqual(peer_relation_databag, {})

        # trigger the leader_elected and config_changed events
        self.harness.update_config({"cluster-name": "test-cluster"})
        self.harness.set_leader(True)

        # ensure that the peer relation has 'cluster_name' set to the config value
        peer_relation_databag = self.harness.get_relation_data(
            self.peer_relation_id, self.harness.charm.app
        )

        self.assertEqual(peer_relation_databag["cluster-name"], "test-cluster")

    def test_on_config_changed_sets_random_cluster_name_in_peer_databag(self):
        # ensure that the peer relation databag is empty
        peer_relation_databag = self.harness.get_relation_data(
            self.peer_relation_id, self.harness.charm.app
        )
        self.assertEqual(peer_relation_databag, {})

        # trigger the leader_elected and config_changed events
        self.harness.set_leader(True)
        self.charm.on.config_changed.emit()

        # ensure that the peer relation has a randomly generated 'cluster_name'
        peer_relation_databag = self.harness.get_relation_data(
            self.peer_relation_id, self.harness.charm.app
        )

        self.assertIsNotNone(peer_relation_databag["cluster-name"])

    @patch("charm.MySQLOperatorCharm._can_start", return_value=True)
    @patch("charm.MySQLOperatorCharm.workload_initialise")
    def test_on_start(
        self,
        _workload_initialise,
        _can_start,
    ):
        # execute on_leader_elected and config_changed to populate the peer databag
        self.harness.set_leader(True)
        self.charm.on.config_changed.emit()

        self.charm.on.start.emit()
        _workload_initialise.assert_called_once()
        _can_start.assert_called_once()

        self.assertTrue(isinstance(self.harness.model.unit.status, MaintenanceStatus))

    @patch("charm.LogRotationSetup.setup")
    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_workload_initialise_connects_exporter_when_data_dir_initialised(
        self,
        _mysql,
        _unit_initialized,
        _log_rotation_setup,
    ):
        mysql = _mysql.return_value
        mysql.is_data_dir_initialised.return_value = True

        self.charm.workload_initialise()

        mysql.start_mysqld.assert_called_once()
        mysql.connect_mysql_exporter.assert_called_once()
        mysql.initialise_mysqld.assert_not_called()

    @patch("services.observers.IPAddressObserver.update_etc_hosts", return_value=True)
    @patch("charm.instance_hostname", return_value="test-hostname")
    @patch("charm.LogRotationSetup.setup")
    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_workload_initialise_connects_exporter_when_bootstrapping(
        self,
        _mysql,
        _unit_initialized,
        _log_rotation_setup,
        _instance_hostname,
        _update_etc_hosts,
    ):
        mysql = _mysql.return_value
        mysql.is_data_dir_initialised.return_value = False
        mysql.get_pid_of_port_3306.side_effect = [1111, 2222]

        self.charm.workload_initialise()

        mysql.initialise_mysqld.assert_called_once()
        mysql.set_operator_user_and_start_mysqld.assert_called_once()
        mysql.connect_mysql_exporter.assert_called_once()

    @patch("charm.MySQLOperatorCharm._can_start", return_value=True)
    @patch("charm.MySQLOperatorCharm.create_cluster")
    @patch("charm.MySQLOperatorCharm.workload_initialise")
    def test_on_start_exceptions(
        self,
        _workload_initialise,
        _create_cluster,
        _can_start,
    ):
        # execute on_leader_elected and config_changed to populate the peer databag
        self.harness.set_leader(True)
        self.charm.on.config_changed.emit()

        # test an exception while configuring mysql users
        _workload_initialise.side_effect = MySQLConfigureMySQLUsersError

        self.charm.on.start.emit()
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

        _workload_initialise.reset_mock()

        # test an exception while configuring the instance
        _workload_initialise.side_effect = MySQLConfigureInstanceError

        self.charm.on.start.emit()
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

        _workload_initialise.reset_mock()

        # test an exception initializing the mysql.juju_units_operations table
        _create_cluster.side_effect = MySQLInitializeJujuOperationsTableError

        self.charm.on.start.emit()
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

        _create_cluster.reset_mock()

        # test an exception with creating a cluster
        _create_cluster.side_effect = MySQLCreateClusterError

        self.charm.on.start.emit()
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

        # test an exception with set the operator user and starting mysqld
        _create_cluster.side_effect = MySQLSetOperatorUserAndStartMySQLDError

        self.charm.on.start.emit()
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

        # test an exception creating a custom mysqld config
        _workload_initialise.side_effect = MySQLCreateCustomMySQLDConfigError

        self.charm.on.start.emit()
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

    @patch("mysql_vm_helpers.MySQL.is_cluster_in_no_quorum", return_value=False)
    @patch(
        "charm.MySQLOperatorCharm.cluster_initialized",
        new_callable=PropertyMock(return_value=True),
    )
    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charms.mysql.v0.mysql.MySQLCharmBase.build_unit_workload_status")
    @patch("mysql_vm_helpers.MySQL.get_member_state")
    @patch("mysql_vm_helpers.MySQL.get_member_role")
    @patch("mysql_vm_helpers.MySQL.get_cluster_status")
    @patch("charm.is_volume_mounted", return_value=True)
    @patch("mysql_vm_helpers.MySQL.reboot_from_complete_outage")
    @patch("charm.snap_service_operation")
    @patch("python_hosts.Hosts.write")
    @patch("mysql_vm_helpers.MySQL.wait_until_mysql_connection")
    @patch("services.observers.IPAddressObserver.update_etc_hosts", return_value=True)
    def test_on_update(
        self,
        _,
        __,
        ___,
        _snap_service_operation,
        _reboot_from_complete_outage,
        _is_volume_mounted,
        _get_cluster_status,
        _get_member_role,
        _get_member_state,
        _build_unit_workload_status,
        _unit_initialized,
        _cluster_initialized,
        _is_cluster_no_quorum,
    ):
        self.harness.update_relation_data(
            self.peer_relation_id,
            self.charm.app.name,
            {
                "cluster-name": "test-cluster",
                "cluster-set-domain-name": "test-domain",
            },
        )
        self.harness.remove_relation_unit(self.peer_relation_id, "mysql/1")
        self.harness.set_leader()
        self.charm.on.config_changed.emit()
        self.harness.update_relation_data(
            self.peer_relation_id,
            self.charm.unit.name,
            {
                "member-role": "primary",
                "member-state": "online",
            },
        )
        _get_member_role.return_value = "PRIMARY"
        _get_member_state.return_value = "ONLINE"
        _build_unit_workload_status.return_value = ActiveStatus()

        self.charm.on.update_status.emit()
        _get_member_role.assert_called_once()
        _get_member_state.assert_called_once()
        _reboot_from_complete_outage.assert_not_called()
        _snap_service_operation.assert_not_called()
        _is_volume_mounted.assert_called_once()
        _get_cluster_status.assert_called_once()

        self.assertTrue(isinstance(self.harness.model.unit.status, ActiveStatus))

        # test instance state = offline
        _get_member_role.reset_mock()
        _get_member_state.reset_mock()
        _build_unit_workload_status.reset_mock()
        _get_cluster_status.reset_mock()

        _get_member_role.return_value = "PRIMARY"
        _get_member_state.return_value = "OFFLINE"
        _build_unit_workload_status.return_value = MaintenanceStatus()
        self.harness.update_relation_data(
            self.peer_relation_id,
            self.charm.unit.name,
            {
                "member-state": "offline",
            },
        )

        self.charm.on.update_status.emit()
        _get_member_role.assert_called_once()
        _get_member_state.assert_called_once()
        _reboot_from_complete_outage.assert_called_once()
        _snap_service_operation.assert_called()
        _get_cluster_status.assert_not_called()

        self.assertTrue(isinstance(self.harness.model.unit.status, MaintenanceStatus))
        # test instance state = unreachable
        _get_member_role.reset_mock()
        _get_member_state.reset_mock()
        _build_unit_workload_status.reset_mock()
        _get_cluster_status.reset_mock()
        _snap_service_operation.reset_mock()

        _reboot_from_complete_outage.reset_mock()
        _snap_service_operation.return_value = False
        _get_member_role.return_value = "PRIMARY"
        _get_member_state.return_value = "UNREACHABLE"
        _build_unit_workload_status.return_value = BlockedStatus()

        self.charm.on.update_status.emit()
        _get_member_role.assert_called_once()
        _get_member_state.assert_called_once()
        _reboot_from_complete_outage.assert_not_called()
        _snap_service_operation.assert_called_once()
        _get_cluster_status.assert_not_called()

        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))


class TestCharmExtended(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.peer_relation_id = self.harness.add_relation(PEER, "mysql")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/1")
        self.rolling_relation_id = self.harness.add_relation("rolling-ops", "rolling-ops")

    def _set_peer_data(self):
        self.harness.update_relation_data(
            self.peer_relation_id,
            "mysql",
            {"cluster-name": "test-cluster", "cluster-set-domain-name": "test-set"},
        )

    # ---- Properties ----

    def test_has_blocked_status_true(self):
        self.charm.unit.status = BlockedStatus("blocked")
        self.assertTrue(self.charm._has_blocked_status)

    def test_has_blocked_status_false(self):
        self.charm.unit.status = ActiveStatus()
        self.assertFalse(self.charm._has_blocked_status)

    @patch("socket.getfqdn", return_value="fqdn")
    def test_unit_fqdn(self, _):
        self.assertEqual(self.charm.unit_fqdn, "fqdn")

    def test_unit_address(self):
        addr = str(self.harness.charm.model.get_binding(PEER).network.bind_address)
        self.assertTrue(addr)

    def test_database_address(self):
        self.harness.add_relation(DB_RELATION_NAME, "app")
        addr = str(self.harness.charm.model.get_binding(DB_RELATION_NAME).network.bind_address)
        self.assertTrue(addr)

    def test_text_logs_no_audit(self):
        self.harness.update_config({"plugin-audit-enabled": False})
        self.assertEqual(self.charm.text_logs, ["error"])

    def test_text_logs_with_audit(self):
        self.harness.update_config({"plugin-audit-enabled": True})
        self.assertEqual(self.charm.text_logs, ["error", "audit"])

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_is_unit_primary_true(self, _mysql):
        _mysql.return_value.get_primary_label.return_value = self.charm.unit_label
        self.assertTrue(self.charm.is_unit_primary())

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_is_unit_primary_false(self, _mysql):
        _mysql.return_value.get_primary_label.return_value = "other"
        self.assertFalse(self.charm.is_unit_primary())

    def test_is_unit_busy_true(self):
        self.charm.unit_peer_data["member-state"] = "waiting"
        self.assertTrue(self.charm.is_unit_busy())

    def test_is_unit_busy_false(self):
        self.charm.unit_peer_data["member-state"] = "online"
        self.assertFalse(self.charm.is_unit_busy())

    def test_refresh_property(self):
        self.assertIsNotNone(self.charm.refresh)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_get_unit_hostname_with_unit_name(self, _mysql):
        self.charm.unit_peer_data["instance-hostname"] = "1.2.3.4:3306"
        self.harness.update_relation_data(
            self.peer_relation_id, "mysql/1", {"instance-hostname": "5.6.7.8:3306"}
        )
        result = self.charm.get_unit_hostname("mysql/1")
        self.assertEqual(result, "5.6.7.8")

    def test_get_unit_hostname_without_unit_name(self):
        self.charm.unit_peer_data["instance-hostname"] = "1.2.3.4:3306"
        result = self.charm.get_unit_hostname()
        self.assertEqual(result, "1.2.3.4")

    # ---- get_unit_address ----

    @patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock, return_value=None)
    def test_get_unit_address_no_peers(self, _peers):
        self.assertEqual(self.charm.get_unit_address(self.charm.unit, PEER), "")

    def test_get_unit_address_with_data(self):
        self.harness.update_relation_data(
            self.peer_relation_id, self.charm.unit.name, {f"{PEER}-address": "1.2.3.4"}
        )
        self.assertEqual(self.charm.get_unit_address(self.charm.unit, PEER), "1.2.3.4")

    def test_get_unit_address_key_error(self):
        result = self.charm.get_unit_address(Mock(name="unknown"), PEER)
        self.assertEqual(result, "")

    # ---- set_unit_status ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_set_unit_status_refresh_none(self, _mysql):
        with patch.object(self.charm, "_refresh", None):
            self.charm.set_unit_status(MaintenanceStatus("test"))
        self.assertIsInstance(self.charm.unit.status, MaintenanceStatus)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_set_unit_status_higher_priority(self, _mysql):
        self.charm.unit.status = ActiveStatus()
        self.charm._refresh.unit_status_higher_priority = True
        self.charm.set_unit_status(MaintenanceStatus("test"))
        self.assertIsInstance(self.charm.unit.status, ActiveStatus)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_set_unit_status_lower_priority_active(self, _mysql):
        self.charm._refresh.unit_status_higher_priority = False
        self.charm._refresh.unit_status_lower_priority.return_value = MaintenanceStatus(
            "refreshing"
        )
        self.charm.set_unit_status(ActiveStatus())
        self.assertIsInstance(self.charm.unit.status, MaintenanceStatus)

    # ---- update_endpoint_addresses ----

    def test_update_endpoint_addresses(self):
        self.harness.add_relation(DB_RELATION_NAME, "app")
        self.harness.add_relation(RELATION_OFFER, "offer-app")
        self.harness.add_relation(RELATION_CONSUMER, "consumer-app")
        self.charm.update_endpoint_addresses()
        self.assertIn(f"{PEER}-address", self.charm.unit_peer_data)

    def test_update_endpoint_address_no_binding(self):
        with patch.object(self.charm.model, "get_binding", return_value=None):
            self.charm.update_endpoint_address("nonexistent")
            self.assertNotIn("nonexistent-address", self.charm.unit_peer_data)

    # ---- _on_leader_settings_changed ----

    def test_on_leader_settings_changed(self):
        self.charm._on_leader_settings_changed(None)
        self.assertEqual(self.charm.unit_peer_data.get("leader"), "false")

    # ---- _on_config_changed ----

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    def test_config_changed_not_initialized(self, mock_peer):
        mock_peer.return_value = False
        with patch.object(self.charm, "_rotate_private_keys") as mock_rotate:
            self.charm._on_config_changed(None)
            mock_rotate.assert_not_called()

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_config_changed_refresh_in_progress(self, _mysql, mock_peer):
        mock_peer.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = True
        with (
            patch.object(self.charm, "_refresh", mock_refresh),
            patch.object(self.charm, "_rotate_private_keys") as mock_rotate,
        ):
            self.charm._on_config_changed(None)
            mock_rotate.assert_not_called()

    @patch("charm.LogRotationSetup.setup")
    @patch("charm.MySQLOperatorCharm._rotate_private_keys")
    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_config_changed_no_config_content(self, _mysql, mock_peer, _rotate, _log):
        mock_peer.return_value = True
        _mysql.return_value.read_file_content.return_value = None
        self.charm._on_config_changed(None)
        _mysql.return_value.write_mysqld_config.assert_not_called()

    @patch("charm.LogRotationSetup.setup")
    @patch("charm.MySQLOperatorCharm._rotate_private_keys")
    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_config_changed_static_requires_restart(self, _mysql, mock_peer, _rotate, _log):
        mock_peer.return_value = True
        _mysql.return_value.read_file_content.return_value = "[mysqld]\ninnodb_buffer_pool_size=1G"
        _mysql.return_value.write_mysqld_config.return_value = {"innodb_buffer_pool_size": "2G"}
        _mysql.return_value.is_mysqld_running.return_value = True
        with patch.object(self.charm.rolling_ops, "request_async_lock") as mock_lock:
            self.charm._on_config_changed(None)
            mock_lock.assert_called_once_with(callback_id="restart")

    @patch("charm.LogRotationSetup.setup")
    @patch("charm.MySQLOperatorCharm._rotate_private_keys")
    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_config_changed_dynamic_only(self, _mysql, mock_peer, _rotate, _log):
        mock_peer.return_value = True
        _mysql.return_value.read_file_content.return_value = "[mysqld]\nmax_connections=100"
        _mysql.return_value.write_mysqld_config.return_value = {"max_connections": "200"}
        _mysql.return_value.is_mysqld_running.return_value = True
        self.charm._on_config_changed(None)
        _mysql.return_value.set_dynamic_variable.assert_called_once()

    # ---- _on_peer_relation_changed ----

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    def test_peer_relation_changed_not_set(self, mock_peer):
        mock_peer.return_value = False
        event = Mock()
        self.charm._on_peer_relation_changed(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._is_unit_waiting_to_join_cluster", return_value=False)
    def test_peer_relation_changed_no_join(self, _waiting, mock_peer):
        mock_peer.return_value = True
        with patch.object(self.charm, "update_endpoint_addresses") as mock_update:
            self.charm._on_peer_relation_changed(Mock())
            mock_update.assert_called_once()

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._is_unit_waiting_to_join_cluster", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_relation_changed_join(self, _mysql, _waiting, mock_peer):
        mock_peer.return_value = True
        with (
            patch.object(self.charm, "join_unit_to_cluster") as mock_join,
            patch.object(self.charm, "update_endpoint_addresses"),
        ):
            self.charm._on_peer_relation_changed(Mock())
            mock_join.assert_called_once()

    # ---- _on_storage_detaching ----

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=False)
    def test_storage_detaching_not_initialized(self, _):
        self.charm._on_storage_detaching(None)

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_storage_detaching_not_in_cluster(self, _mysql, _):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        self.charm._on_storage_detaching(None)

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_storage_detaching_is_primary_not_leader(self, _mysql, _):
        _mysql.return_value.is_instance_in_cluster.return_value = True
        _mysql.return_value.is_cluster_replica.return_value = False
        with (
            patch.object(self.charm, "is_unit_primary", return_value=True),
            patch.object(self.charm.unit, "is_leader", return_value=False),
        ):
            self.harness.update_relation_data(self.peer_relation_id, "mysql/1", {"leader": "true"})
            self.charm._on_storage_detaching(None)
            _mysql.return_value.set_cluster_primary.assert_called_once()

    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_storage_detaching_is_replica_cluster(self, _mysql, _):
        _mysql.return_value.is_instance_in_cluster.return_value = True
        _mysql.return_value.is_cluster_replica.return_value = True
        _mysql.return_value.get_cluster_global_primary_address.return_value = "10.0.0.1"
        with patch.object(self.charm, "is_unit_primary", return_value=False):
            self.charm._on_storage_detaching(None)
        _mysql.return_value.remove_instance.assert_called_once()

    # ---- _charm_tracing_config ----

    def test_charm_tracing_config_not_ready(self):
        with patch.object(self.charm._grafana_agent, "is_ready", return_value=False):
            self.charm._charm_tracing_config()

    @patch("charm.set_destination")
    def test_charm_tracing_config_success(self, _set_dest):
        with (
            patch.object(self.charm._grafana_agent, "is_ready", return_value=True),
            patch.object(
                self.charm._grafana_agent,
                "get_tracing_endpoint",
                return_value="http://localhost:4318",
            ),
        ):
            self.charm._charm_tracing_config()
            _set_dest.assert_called_once()

    @patch("charm.set_destination")
    def test_charm_tracing_config_no_endpoint(self, _set_dest):
        with (
            patch.object(self.charm._grafana_agent, "is_ready", return_value=True),
            patch.object(self.charm._grafana_agent, "get_tracing_endpoint", return_value=""),
        ):
            self.charm._charm_tracing_config()
            _set_dest.assert_not_called()

    @patch("charm.set_destination")
    def test_charm_tracing_config_protocol_error(self, _set_dest):
        with (
            patch.object(self.charm._grafana_agent, "is_ready", return_value=True),
            patch.object(
                self.charm._grafana_agent,
                "get_tracing_endpoint",
                side_effect=ProtocolNotFoundError("test"),
            ),
        ):
            self.charm._charm_tracing_config()
            _set_dest.assert_not_called()

    @patch("charm.set_destination")
    def test_charm_tracing_config_https(self, _set_dest):
        with (
            patch.object(self.charm._grafana_agent, "is_ready", return_value=True),
            patch.object(
                self.charm._grafana_agent,
                "get_tracing_endpoint",
                return_value="https://localhost:4318",
            ),
        ):
            self.charm._charm_tracing_config()
            _set_dest.assert_not_called()

    # ---- _handle_non_online_instance_status ----

    @patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_handle_online_no_quorum_leader(self, _mysql, mock_peers):
        _mysql.return_value.is_cluster_in_no_quorum.return_value = True
        _mysql.return_value.reboot_from_complete_outage.return_value = None
        mock_peers.return_value = Mock(units=set())
        with patch.object(self.charm.unit, "is_leader", return_value=True):
            self.charm._handle_non_online_instance_status(InstanceState.ONLINE)
        _mysql.return_value.stop_group_replication.assert_called_once()

    @patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_handle_online_no_quorum_reboot_error(self, _mysql, mock_peers):
        _mysql.return_value.is_cluster_in_no_quorum.return_value = True
        _mysql.return_value.reboot_from_complete_outage.side_effect = (
            MySQLRebootFromCompleteOutageError
        )
        mock_peers.return_value = Mock(units=set())
        with patch.object(self.charm.unit, "is_leader", return_value=True):
            result = self.charm._handle_non_online_instance_status(InstanceState.ONLINE)
        self.assertTrue(result)
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    def test_handle_recovering(self):
        result = self.charm._handle_non_online_instance_status(InstanceState.RECOVERING)
        self.assertTrue(result)

    @patch("charm.snap_service_operation", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_handle_unreachable_restart_success(self, _mysql, _snap):
        result = self.charm._handle_non_online_instance_status(InstanceState.UNREACHABLE)
        self.assertTrue(result)

    @patch("charm.snap_service_operation", return_value=False)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_handle_unreachable_restart_fail(self, _mysql, _snap):
        result = self.charm._handle_non_online_instance_status(InstanceState.UNREACHABLE)
        self.assertFalse(result)
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    @patch("charm.snap_service_operation", side_effect=SnapServiceOperationError("fail"))
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_handle_unreachable_snap_error(self, _mysql, _snap):
        result = self.charm._handle_non_online_instance_status(InstanceState.UNREACHABLE)
        self.assertFalse(result)
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    # ---- _execute_manual_rejoin ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_manual_rejoin_no_online_peer(self, _mysql):
        with patch.object(self.charm, "_get_primary_from_online_peer", return_value=None):
            self.charm._execute_manual_rejoin()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_manual_rejoin_not_in_cluster(self, _mysql):
        _mysql.return_value.instance_belongs_to_cluster.return_value = False
        with patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"):
            self.charm._execute_manual_rejoin()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_manual_rejoin_locks_acquired(self, _mysql):
        _mysql.return_value.instance_belongs_to_cluster.return_value = True
        _mysql.return_value.are_locks_acquired.return_value = True
        with patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"):
            self.charm._execute_manual_rejoin()
        _mysql.return_value.rejoin_instance_to_cluster.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_manual_rejoin_success(self, _mysql):
        _mysql.return_value.instance_belongs_to_cluster.return_value = True
        _mysql.return_value.are_locks_acquired.return_value = False
        with patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"):
            self.charm._execute_manual_rejoin()
        _mysql.return_value.rejoin_instance_to_cluster.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_manual_rejoin_rejoin_fails(self, _mysql):
        _mysql.return_value.instance_belongs_to_cluster.return_value = True
        _mysql.return_value.are_locks_acquired.return_value = False
        _mysql.return_value.rejoin_instance_to_cluster.side_effect = (
            MySQLRejoinInstanceToClusterError
        )
        with patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"):
            self.charm._execute_manual_rejoin()
        _mysql.return_value.remove_instance.assert_called_once()
        _mysql.return_value.add_instance_to_cluster.assert_called_once()

    # ---- _on_update_status ----

    def test_update_status_not_initialized(self):
        with (
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
        ):
            mock_ci.return_value = False
            self.charm._on_update_status(None)

    def test_update_status_volume_not_mounted(self):
        with (
            patch("charm.is_volume_mounted", return_value=False),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
        ):
            mock_ci.return_value = True
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm._on_update_status(None)

    def test_update_status_initialising(self):
        with (
            patch("charm.is_volume_mounted", return_value=True),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
            patch(
                "charm.MySQLOperatorCharm.unit_configured", new_callable=PropertyMock
            ) as mock_uc,
            patch.object(self.charm, "unit_initialized", return_value=False),
            patch.object(self.charm.unit, "is_leader", return_value=False),
        ):
            mock_ci.return_value = True
            mock_uc.return_value = False
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm.unit_peer_data["member-state"] = "waiting"
            self.charm._on_update_status(None)

    def test_update_status_refresh_none(self):
        with (
            patch("charm.is_volume_mounted", return_value=True),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
            patch.object(self.charm, "_refresh", None),
        ):
            mock_ci.return_value = True
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm._on_update_status(None)

    def test_update_status_refresh_in_progress(self):
        mock_refresh = Mock()
        mock_refresh.in_progress = True
        with (
            patch("charm.is_volume_mounted", return_value=True),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
            patch.object(self.charm, "_refresh", mock_refresh),
        ):
            mock_ci.return_value = True
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm._on_update_status(None)

    def test_update_status_waiting_to_join(self):
        with (
            patch("charm.is_volume_mounted", return_value=True),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
            patch.object(self.charm, "_is_unit_waiting_to_join_cluster", return_value=True),
            patch.object(self.charm, "join_unit_to_cluster") as mock_join,
        ):
            mock_ci.return_value = True
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm._on_update_status(None)
            mock_join.assert_called_once()

    def test_update_status_unable_to_get_state(self):
        from charms.mysql.v0.mysql import MySQLUnableToGetMemberStateError

        with (
            patch("charm.is_volume_mounted", return_value=True),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock) as _mysql,
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
            patch.object(self.charm, "_refresh", Mock(in_progress=False)),
        ):
            _mysql.return_value.get_member_state.side_effect = MySQLUnableToGetMemberStateError
            _mysql.return_value.get_member_role.side_effect = MySQLUnableToGetMemberStateError
            mock_ci.return_value = True
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm._on_update_status(None)

    def test_update_status_skip_async_replication(self):
        with (
            patch("charm.is_volume_mounted", return_value=True),
            patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock) as _mysql,
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
            patch.object(self.charm, "_refresh", Mock(in_progress=False)),
        ):
            _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
            _mysql.return_value.get_member_role.return_value = "PRIMARY"
            mock_ci.return_value = True
            self.charm.unit_peer_data["member-role"] = "primary"
            self.charm.replication_offer = Mock(idle=False)
            self.charm.replication_consumer = Mock(idle=True)
            self.charm._on_update_status(None)

    # ---- _all_peers_reachable ----

    def test_all_peers_reachable_empty_address(self):
        mock_unit = Mock()
        with (
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
            patch.object(self.charm, "get_unit_address", return_value=""),
        ):
            mock_peers.return_value = Mock(units={mock_unit})
            self.assertFalse(self.charm._all_peers_reachable())

    def test_all_peers_reachable_connection_fail(self):
        mock_unit = Mock()
        with (
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
            patch.object(self.charm, "get_unit_address", return_value="1.2.3.4"),
            patch("socket.create_connection", side_effect=OSError),
        ):
            mock_peers.return_value = Mock(units={mock_unit})
            self.assertFalse(self.charm._all_peers_reachable())

    def test_all_peers_reachable_success(self):
        mock_unit = Mock()
        with (
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
            patch.object(self.charm, "get_unit_address", return_value="1.2.3.4"),
            patch("socket.create_connection"),
        ):
            mock_peers.return_value = Mock(units={mock_unit})
            self.assertTrue(self.charm._all_peers_reachable())

    # ---- _can_start ----

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    def test_can_start_not_set(self, mock_peer):
        mock_peer.return_value = False
        event = Mock()
        self.assertFalse(self.charm._can_start(event))
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.is_volume_mounted", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_can_start_refresh_in_progress(self, _mysql, _vol, mock_peer):
        mock_peer.return_value = True
        mock_refresh = Mock()
        mock_refresh.in_progress = True
        with (
            patch.object(self.charm, "_refresh", mock_refresh),
            patch(
                "charm.MySQLOperatorCharm._has_blocked_status", new_callable=PropertyMock
            ) as mock_blocked,
        ):
            mock_blocked.return_value = False
            event = Mock()
            self.assertFalse(self.charm._can_start(event))
            event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.is_volume_mounted", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_can_start_blocked(self, _mysql, _vol, mock_peer):
        mock_peer.return_value = True
        with (
            patch.object(self.charm, "_refresh", Mock(in_progress=False)),
            patch(
                "charm.MySQLOperatorCharm._has_blocked_status", new_callable=PropertyMock
            ) as mock_blocked,
        ):
            mock_blocked.return_value = True
            self.assertFalse(self.charm._can_start(Mock()))

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.is_volume_mounted", return_value=False)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_can_start_volume_not_mounted(self, _mysql, _vol, mock_peer):
        mock_peer.return_value = True
        with (
            patch.object(self.charm, "_refresh", Mock(in_progress=False)),
            patch(
                "charm.MySQLOperatorCharm._has_blocked_status", new_callable=PropertyMock
            ) as mock_blocked,
        ):
            mock_blocked.return_value = False
            with self.assertRaises(StorageUnavailableError):
                self.charm._can_start(Mock())

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.is_volume_mounted", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_can_start_empty_config(self, _mysql, _vol, mock_peer):
        mock_peer.return_value = True
        _mysql.return_value.read_file_content.return_value = None
        with (
            patch.object(self.charm, "_refresh", Mock(in_progress=False)),
            patch(
                "charm.MySQLOperatorCharm._has_blocked_status", new_callable=PropertyMock
            ) as mock_blocked,
        ):
            mock_blocked.return_value = False
            self.assertTrue(self.charm._can_start(Mock()))

    @patch("charm.MySQLOperatorCharm._is_peer_data_set", new_callable=PropertyMock)
    @patch("charm.is_volume_mounted", return_value=True)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_can_start_already_initialized(self, _mysql, _vol, mock_peer):
        mock_peer.return_value = True
        _mysql.return_value.read_file_content.return_value = "config"
        self.charm._refresh.in_progress = False
        with (
            patch(
                "charm.MySQLOperatorCharm._has_blocked_status", new_callable=PropertyMock
            ) as mock_blocked,
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch("charm.Retrying", return_value=Retrying(stop=stop_after_attempt(1))),
            patch.object(self.charm, "_on_update_status"),
        ):
            mock_blocked.return_value = False
            self.assertFalse(self.charm._can_start(Mock()))

    # ---- _create_cluster ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_create_cluster_success(self, _mysql):
        self._set_peer_data()
        with (
            patch.object(self.charm, "create_cluster"),
            patch.object(self.charm, "build_unit_workload_status", return_value=ActiveStatus()),
        ):
            self.charm._create_cluster()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_create_cluster_error(self, _mysql):
        self._set_peer_data()
        with (
            patch.object(self.charm, "create_cluster", side_effect=MySQLCreateClusterError),
            self.assertRaises(MySQLCreateClusterError),
        ):
            self.charm._create_cluster()

    # ---- _is_unit_waiting_to_join_cluster ----

    def test_is_unit_waiting_to_join_true(self):
        self.charm.unit_peer_data["member-state"] = "waiting"
        with (
            patch(
                "charm.MySQLOperatorCharm.unit_configured", new_callable=PropertyMock
            ) as mock_uc,
            patch.object(self.charm, "unit_initialized", return_value=False),
            patch(
                "charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock
            ) as mock_ci,
        ):
            mock_uc.return_value = True
            mock_ci.return_value = True
            self.assertTrue(self.charm._is_unit_waiting_to_join_cluster())

    def test_is_unit_waiting_to_join_false(self):
        self.charm.unit_peer_data["member-state"] = "online"
        self.assertFalse(self.charm._is_unit_waiting_to_join_cluster())

    # ---- _get_primary_from_online_peer ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_get_primary_from_online_peer_success(self, _mysql):
        _mysql.return_value.get_cluster_primary_address.return_value = "1.2.3.4"
        mock_unit = Mock()
        mock_peer_data = Mock()
        mock_peer_data.get.return_value = InstanceState.ONLINE
        with (
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
            patch.object(self.charm, "get_unit_address", return_value="5.6.7.8"),
        ):
            mock_peers.return_value = Mock(units={mock_unit}, data={mock_unit: mock_peer_data})
            result = self.charm._get_primary_from_online_peer()
            self.assertEqual(result, "1.2.3.4")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_get_primary_from_online_peer_error(self, _mysql):
        _mysql.return_value.get_cluster_primary_address.side_effect = (
            MySQLGetClusterPrimaryAddressError
        )
        mock_unit = Mock()
        mock_peer_data = Mock()
        mock_peer_data.get.return_value = InstanceState.ONLINE
        with (
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
            patch.object(self.charm, "get_unit_address", return_value="5.6.7.8"),
        ):
            mock_peers.return_value = Mock(units={mock_unit}, data={mock_unit: mock_peer_data})
            result = self.charm._get_primary_from_online_peer()
            self.assertIsNone(result)

    # ---- join_unit_to_cluster ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_already_in_cluster(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = True
        with patch.object(self.charm, "build_unit_workload_status", return_value=ActiveStatus()):
            self.charm.join_unit_to_cluster()
        _mysql.return_value.add_instance_to_cluster.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_no_primary(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        with (
            patch.object(self.charm, "_get_primary_from_online_peer", return_value=None),
            patch.object(self.charm, "set_unit_status"),
        ):
            self.charm.join_unit_to_cluster()
        _mysql.return_value.add_instance_to_cluster.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_max_size(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        _mysql.return_value.get_cluster_node_count.return_value = 9
        with (
            patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"),
            patch.object(self.charm, "set_unit_status") as mock_status,
        ):
            self.charm.join_unit_to_cluster()
        self.assertTrue(
            any(isinstance(c.args[0], WaitingStatus) for c in mock_status.call_args_list)
        )

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_locks_acquired(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        _mysql.return_value.get_cluster_node_count.return_value = 1
        _mysql.return_value.is_cluster_replica.return_value = False
        _mysql.return_value.are_locks_acquired.return_value = True
        with (
            patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"),
            patch.object(self.charm, "set_unit_status"),
        ):
            self.charm.join_unit_to_cluster()
        _mysql.return_value.add_instance_to_cluster.assert_not_called()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_success(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        _mysql.return_value.get_cluster_node_count.return_value = 1
        _mysql.return_value.is_cluster_replica.return_value = False
        _mysql.return_value.are_locks_acquired.return_value = False
        with (
            patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"),
            patch.object(self.charm, "build_unit_workload_status", return_value=ActiveStatus()),
        ):
            self.charm.join_unit_to_cluster()
        _mysql.return_value.add_instance_to_cluster.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_add_error(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        _mysql.return_value.get_cluster_node_count.return_value = 1
        _mysql.return_value.is_cluster_replica.return_value = False
        _mysql.return_value.are_locks_acquired.return_value = False
        _mysql.return_value.add_instance_to_cluster.side_effect = MySQLAddInstanceToClusterError
        with patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"):
            self.charm.join_unit_to_cluster()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_join_unit_lock_error(self, _mysql):
        _mysql.return_value.is_instance_in_cluster.return_value = False
        _mysql.return_value.get_cluster_node_count.return_value = 1
        _mysql.return_value.is_cluster_replica.return_value = False
        _mysql.return_value.are_locks_acquired.return_value = False
        _mysql.return_value.add_instance_to_cluster.side_effect = MySQLLockAcquisitionError
        with (
            patch.object(self.charm, "_get_primary_from_online_peer", return_value="1.2.3.4"),
            patch.object(self.charm, "set_unit_status"),
        ):
            self.charm.join_unit_to_cluster()

    # ---- recover_unit_after_restart ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_recover_single_unit(self, _mysql):
        with patch.object(self.charm.app, "planned_units", return_value=1):
            self.charm.recover_unit_after_restart()
        _mysql.return_value.reboot_from_complete_outage.assert_called_once()

    @patch("charm.Retrying", return_value=Retrying(stop=stop_after_attempt(1)))
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_recover_multi_unit_success(self, _mysql, _retry):
        _mysql.return_value.is_instance_in_cluster.return_value = True
        with patch.object(self.charm.app, "planned_units", return_value=3):
            self.charm.recover_unit_after_restart()
        _mysql.return_value.hold_if_recovering.assert_called()

    @patch("charm.Retrying")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_recover_multi_unit_retry_error(self, _mysql, _retry):
        from tenacity import RetryError as TenacityRetryError

        _mysql.return_value.is_instance_in_cluster.return_value = False
        mock_attempt = Mock()
        mock_attempt.retry_state.attempt_number = 1
        _retry.return_value.__iter__ = Mock(side_effect=TenacityRetryError(Mock(attempt_number=1)))
        with (
            patch.object(self.charm.app, "planned_units", return_value=3),
            self.assertRaises(TenacityRetryError),
        ):
            self.charm.recover_unit_after_restart()

    # ---- _restart_group_replication ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_restart_group_replication_no_relation(self, _mysql):
        with patch.object(self.charm.model, "get_relation", return_value=None):
            result = self.charm._restart_group_replication()
        self.assertEqual(result, OperationResult.RETRY_RELEASE)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_restart_group_replication_primary_skip(self, _mysql):
        mock_relation = Mock()
        with (
            patch.object(self.charm.model, "get_relation", return_value=mock_relation),
            patch.object(self.charm, "is_unit_primary", return_value=True),
            patch.object(self.charm.rolling_ops, "is_waiting_callback", return_value=True),
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
        ):
            mock_peers.return_value = Mock(units={Mock()})
            result = self.charm._restart_group_replication()
        self.assertEqual(result, OperationResult.RETRY_RELEASE)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_restart_group_replication_no_primary(self, _mysql):
        _mysql.return_value.get_cluster_primary_address.return_value = None
        mock_relation = Mock()
        with (
            patch.object(self.charm.model, "get_relation", return_value=mock_relation),
            patch.object(self.charm, "is_unit_primary", return_value=False),
            patch.object(self.charm.rolling_ops, "is_waiting_callback", return_value=False),
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
        ):
            mock_peers.return_value = Mock(units=set())
            result = self.charm._restart_group_replication()
        self.assertEqual(result, OperationResult.RETRY_HOLD)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_restart_group_replication_success(self, _mysql):
        _mysql.return_value.get_cluster_primary_address.return_value = "1.2.3.4"
        mock_relation = Mock()
        with (
            patch.object(self.charm.model, "get_relation", return_value=mock_relation),
            patch.object(self.charm, "is_unit_primary", return_value=False),
            patch.object(self.charm.rolling_ops, "is_waiting_callback", return_value=False),
            patch("charm.MySQLOperatorCharm.peers", new_callable=PropertyMock) as mock_peers,
            patch.object(self.charm, "_on_update_status"),
        ):
            mock_peers.return_value = Mock(units=set())
            result = self.charm._restart_group_replication()
        self.assertEqual(result, OperationResult.RELEASE)

    # ---- _restart ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_restart_standalone(self, _mysql):
        with (
            patch.object(self.charm, "unit_initialized", return_value=False),
            patch.object(self.charm, "_on_update_status"),
        ):
            result = self.charm._restart()
        _mysql.return_value.restart_mysqld.assert_called_once()
        self.assertEqual(result, OperationResult.RELEASE)

    @patch("charm.sleep")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_restart_initialized(self, _mysql, _sleep):
        with (
            patch.object(self.charm, "unit_initialized", return_value=True),
            patch.object(self.charm.app, "planned_units", return_value=1),
            patch.object(self.charm, "is_unit_primary", return_value=False),
            patch.object(self.charm, "recover_unit_after_restart"),
            patch.object(self.charm, "_on_update_status"),
        ):
            result = self.charm._restart()
        _mysql.return_value.restart_mysqld.assert_called_once()
        self.assertEqual(result, OperationResult.RELEASE)

    # ---- _rotate_private_keys ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_private_keys_client_changed(self, _mysql):
        self.harness.set_leader()
        self.charm.app_peer_data["client-private-key"] = "old"
        with self.harness.hooks_disabled():
            self.harness.update_config({"tls-client-private-key": "new"})
        self.charm._rotate_private_keys()
        self.assertEqual(self.charm.app_peer_data["client-private-key"], "new")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_private_keys_peer_changed(self, _mysql):
        self.harness.set_leader()
        self.charm.app_peer_data["peer-private-key"] = "old"
        with self.harness.hooks_disabled():
            self.harness.update_config({"tls-peer-private-key": "new"})
        self.charm._rotate_private_keys()
        self.assertEqual(self.charm.app_peer_data["peer-private-key"], "new")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_rotate_private_keys_unchanged(self, _mysql):
        self.harness.set_leader()
        self.charm.app_peer_data["client-private-key"] = "same"
        self.charm.app_peer_data["peer-private-key"] = "same"
        with self.harness.hooks_disabled():
            self.harness.update_config({
                "tls-client-private-key": "same",
                "tls-peer-private-key": "same",
            })
        with (
            patch.object(self.charm.tls, "client_certificates_refresh_event") as mock_client,
            patch.object(self.charm.tls, "peer_certificates_refresh_event") as mock_peer,
        ):
            self.charm._rotate_private_keys()
            mock_client.emit.assert_not_called()
            mock_peer.emit.assert_not_called()

    # ---- install_workload ----

    @patch("charm.Retrying", return_value=Retrying(stop=stop_after_attempt(1)))
    @patch("mysql_vm_helpers.MySQL.install_and_configure_mysql_dependencies")
    def test_install_workload_success(self, _install, _retry):
        self.assertTrue(self.charm.install_workload())

    @patch("charm.Retrying", return_value=Retrying(stop=stop_after_attempt(1)))
    @patch(
        "mysql_vm_helpers.MySQL.install_and_configure_mysql_dependencies",
        side_effect=Exception(),
    )
    def test_install_workload_failure(self, _install, _retry):
        self.assertFalse(self.charm.install_workload())

    # ---- update_endpoints ----

    def test_update_endpoints(self):
        with patch.object(self.charm.database_relation, "_update_endpoints_all_relations") as mock:
            self.charm.update_endpoints()
            mock.assert_called_once()
