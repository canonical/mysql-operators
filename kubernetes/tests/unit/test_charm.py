# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import PropertyMock, patch

import pytest
from ops.model import ActiveStatus, WaitingStatus
from ops.testing import Harness
from tenacity import wait_none

from charm import MySQLOperatorCharm
from constants import (
    BACKUPS_PASSWORD_KEY,
    DEFAULT_PASSWORD_LENGTH,
    MONITORING_PASSWORD_KEY,
    MYSQL_DATA_DIR,
    MYSQL_LOGS_DIR,
    MYSQLD_LOCATION,
    OPERATOR_PASSWORD_KEY,
    REPLICATION_PASSWORD_KEY,
)
from mysql_k8s_helpers import MySQL, MySQLInitialiseMySQLDError

APP_NAME = "mysql-k8s"
REQUIRED_PASSWORD_KEYS = [
    MONITORING_PASSWORD_KEY,
    REPLICATION_PASSWORD_KEY,
    OPERATOR_PASSWORD_KEY,
    BACKUPS_PASSWORD_KEY,
]


class TestCharm(unittest.TestCase):
    def setUp(self) -> None:
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
        self.charm = self.harness.charm
        self.maxDiff = None

    @pytest.fixture
    def use_caplog(self, caplog):
        self._caplog = caplog

    def layer_dict(self, with_mysqld_exporter: bool = False):
        mysqld_cmd = [
            MYSQLD_LOCATION,
            "--basedir=/usr",
            f"--datadir={MYSQL_DATA_DIR}",
            "--plugin-dir=/usr/lib/mysql/plugin",
            f"--log-error={MYSQL_LOGS_DIR}/error.log",
            f"--pid-file={self.charm.unit_label}.pid",
        ]
        return {
            "summary": "mysqld services layer",
            "description": "pebble config layer for mysqld safe and exporter",
            "services": {
                "mysqld": {
                    "override": "replace",
                    "summary": "mysql daemon",
                    "command": " ".join(mysqld_cmd),
                    "startup": "enabled",
                    "user": "mysql",
                    "group": "mysql",
                    "kill-delay": "24h",
                    "environment": {"MYSQLD_PARENT_PID": 1},
                    "requires": ["mysql"],
                    "after": ["mysql"],
                },
                "mysql": {
                    "override": "replace",
                    "summary": "tail log",
                    "command": f"tail -F {MYSQL_LOGS_DIR}/error.log",
                    "startup": "enabled",
                },
                "mysqld_exporter": {
                    "override": "replace",
                    "summary": "mysqld exporter",
                    "command": "/start-mysqld-exporter.sh",
                    "startup": "enabled" if with_mysqld_exporter else "disabled",
                    "user": "mysql",
                    "group": "mysql",
                    "environment": {
                        "EXPORTER_USER": "charmed-stats",
                        "EXPORTER_PASS": self.charm.get_secret("app", "monitoring-password"),
                    },
                },
                "mysql-pitr-helper-collector": {
                    "command": "/start-mysql-pitr-helper-collector.sh",
                    "group": "mysql",
                    "override": "replace",
                    "startup": "disabled",
                    "summary": "mysql-pitr-helper binlogs collector",
                    "user": "mysql",
                },
            },
        }

    def tearDown(self) -> None:
        self.patcher.stop()

    def test_mysqld_layer(self):
        # Test layer property
        # Comparing output dicts
        self.assertEqual(self.charm._pebble_layer.to_dict(), self.layer_dict())

    @pytest.mark.usefixtures("with_juju_secrets")
    def test_on_leader_elected_secrets(self):
        # Test leader election setting of secret data
        self.harness.set_leader()

        # > 3.1.7 changed way last revision secret is accessed (peek)
        secret_data = self.harness.model.get_secret(
            label="database-peers.mysql-k8s.app"
        ).peek_content()

        # Test passwords in content and length
        for password in REQUIRED_PASSWORD_KEYS:
            self.assertTrue(
                secret_data[password].isalnum()
                and len(secret_data[password]) == DEFAULT_PASSWORD_LENGTH
            )

    @patch("mysql_k8s_helpers.MySQL.drop_root_user")
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="mysql-k8s.somedomain")
    @patch("mysql_k8s_helpers.MySQL.install_components")
    @patch("mysql_k8s_helpers.MySQL.cluster_metadata_exists", return_value=False)
    @patch("mysql_k8s_helpers.MySQL.rescan_cluster")
    @patch("charms.mysql.v0.mysql.MySQLCharmBase.build_unit_workload_status")
    @patch("mysql_k8s_helpers.MySQL.write_content_to_file")
    @patch("mysql_k8s_helpers.MySQL.is_data_dir_initialised", return_value=False)
    @patch("mysql_k8s_helpers.MySQL.create_cluster_set")
    @patch("mysql_k8s_helpers.MySQL.initialize_juju_units_operations_table")
    @patch("mysql_k8s_helpers.MySQL.get_mysql_version", return_value="8.4.0")
    @patch("mysql_k8s_helpers.MySQL.wait_until_mysql_connection")
    @patch("mysql_k8s_helpers.MySQL.configure_mysql_router_roles")
    @patch("mysql_k8s_helpers.MySQL.configure_mysql_system_roles")
    @patch("mysql_k8s_helpers.MySQL.configure_mysql_system_users")
    @patch("mysql_k8s_helpers.MySQL.configure_instance")
    @patch("mysql_k8s_helpers.MySQL.create_cluster")
    @patch("mysql_k8s_helpers.MySQL.initialise_mysqld")
    @patch("mysql_k8s_helpers.MySQL.is_instance_in_cluster")
    @patch("mysql_k8s_helpers.MySQL.get_member_state", return_value="ONLINE")
    @patch("mysql_k8s_helpers.MySQL.get_member_role", return_value="PRIMARY")
    @patch(
        "mysql_k8s_helpers.MySQL.get_innodb_buffer_pool_parameters",
        return_value=(123456, None, None),
    )
    @patch("mysql_k8s_helpers.MySQL.get_max_connections", return_value=120)
    @patch("mysql_k8s_helpers.MySQL.setup_logrotate_config")
    @patch("mysql_k8s_helpers.MySQL.set_operator_user_and_start_mysqld")
    def test_mysql_pebble_ready(
        self,
        _,
        __,
        _get_max_connections,
        _get_innodb_buffer_pool_parameters,
        _get_member_role,
        _get_member_state,
        _is_instance_in_cluster,
        _initialise_mysqld,
        _create_cluster,
        _configure_instance,
        _configure_mysql_router_roles,
        _configure_mysql_system_roles,
        _configure_mysql_system_users,
        _wait_until_mysql_connection,
        _get_mysql_version,
        _initialize_juju_units_operations_table,
        _create_cluster_set,
        _is_data_dir_initialised,
        _write_content_to_file,
        _build_unit_workload_status,
        _rescan_cluster,
        _cluster_metadata_exists,
        _install_components,
        _get_unit_address,
        _drop_root_user,
    ):
        _build_unit_workload_status.return_value = ActiveStatus()

        # Check if initial plan is empty
        self.harness.set_can_connect("mysql", True)
        initial_plan = self.harness.get_container_pebble_plan("mysql")
        self.assertEqual(initial_plan.to_yaml(), "{}\n")

        # Trigger pebble ready before leader election
        self.harness.container_pebble_ready("mysql")
        self.assertTrue(isinstance(self.charm.unit.status, WaitingStatus))

        self.harness.set_leader()
        # Trigger pebble ready after leader election
        self.harness.container_pebble_ready("mysql")
        self.assertTrue(isinstance(self.charm.unit.status, ActiveStatus))

        # After configuration run, plan should be populated
        plan = self.harness.get_container_pebble_plan("mysql")
        self.assertEqual(
            plan.to_dict()["services"],  # pyright: ignore[reportTypedDictNotRequiredAccess]
            self.layer_dict()["services"],
        )

        _is_data_dir_initialised.return_value = True
        self.harness.add_relation("metrics-endpoint", "test-cos-app")
        plan = self.harness.get_container_pebble_plan("mysql")
        self.assertEqual(
            plan.to_dict()["services"],  # pyright: ignore[reportTypedDictNotRequiredAccess]
            self.layer_dict(with_mysqld_exporter=True)["services"],
        )

    @patch("charm.MySQLOperatorCharm.unit_initialized")
    @patch("charm.MySQLOperatorCharm.cluster_initialized", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.join_unit_to_cluster")
    @patch("charm.MySQLOperatorCharm._configure_instance")
    @patch("charm.MySQLOperatorCharm._write_mysqld_configuration")
    @patch("charm.MySQLOperatorCharm._mysql")
    def test_pebble_ready_set_data(
        self,
        mock_mysql,
        mock_write_conf,
        mock_conf,
        mock_join,
        _cluster_initialized,
        _unit_initialized,
    ):
        mock_mysql.is_data_dir_initialised.return_value = False
        mock_mysql.get_member_role.return_value = "PRIMARY"
        mock_mysql.get_member_state.return_value = "ONLINE"
        self.harness.set_can_connect("mysql", True)
        self.harness.set_leader()

        mock_mysql.cluster_metadata_exists.return_value = False
        _cluster_initialized.return_value = False
        _unit_initialized.return_value = False

        # test on leader
        self.harness.set_leader(is_leader=True)
        self.harness.container_pebble_ready("mysql")
        self.assertEqual(self.charm.unit_peer_data["member-state"], "ONLINE")
        self.assertEqual(self.charm.unit_peer_data["member-role"], "PRIMARY")

        _cluster_initialized.return_value = True

        # test on non leader
        self.harness.set_leader(is_leader=False)
        self.harness.container_pebble_ready("mysql")
        self.assertEqual(self.charm.unit_peer_data["member-role"], "SECONDARY")
        self.assertEqual(self.charm.unit_peer_data["member-state"], "waiting")

    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="mysql-k8s.somedomain")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_mysql_pebble_ready_non_leader(self, _mysql_mock, mock_get_unit_address):
        # Test pebble ready when not leader
        # Expect unit to be in waiting status
        self.harness.update_relation_data(
            self.peer_relation_id, f"{APP_NAME}/1", {"configured": "True"}
        )
        _mysql_mock.get_mysql_version.return_value = "8.4.0"
        self.charm._mysql = _mysql_mock
        self.harness.container_pebble_ready("mysql")
        self.assertTrue(isinstance(self.charm.unit.status, WaitingStatus))

    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="mysql-k8s.somedomain")
    @patch("charm.MySQLOperatorCharm._mysql")
    def test_mysql_pebble_ready_exception(self, _mysql_mock, mock_get_unit_address):
        # Test exception raised in bootstrapping
        self.harness.set_leader()
        self.charm._mysql = _mysql_mock
        _mysql_mock.render_mysqld_configuration.return_value = ("content", {"config": "data"})
        _mysql_mock.get_innodb_buffer_pool_parameters.return_value = (123456, None, None)
        _mysql_mock.initialise_mysqld.side_effect = MySQLInitialiseMySQLDError
        # Trigger pebble ready after leader election
        self.harness.container_pebble_ready("mysql")

        self.assertFalse(isinstance(self.charm.unit.status, ActiveStatus))

    def test_on_config_changed(self):
        self.harness.update_relation_data(
            self.peer_relation_id,
            "mysql-k8s",
            {"cluster-name": "", "cluster-set-domain-name": "test_cluster_set"},
        )
        # Test config changed set of cluster name
        self.assertEqual(self.charm.peers.data[self.charm.app].get("cluster-name"), None)
        self.harness.set_leader()
        self.charm.on.config_changed.emit()
        # Cluster name is `cluster-<hash>`
        self.assertNotEqual(
            self.charm.peers.data[self.charm.app]["cluster-name"], "not_valid_cluster_name"
        )

    @patch(
        "charm.get_k8s_fqdn",
        return_value="mysql-k8s-0.mysql-k8s-endpoints.default.svc.cluster.local",
    )
    def test_get_unit_address(self, mock_get_k8s_fqdn):
        self.assertEqual(
            self.charm.get_unit_address(self.charm.unit),
            "mysql-k8s-0.mysql-k8s-endpoints.default.svc.cluster.local.",
        )
        mock_get_k8s_fqdn.assert_called_once_with("mysql-k8s-0.mysql-k8s-endpoints")

    @patch(
        "charm.get_k8s_fqdn",
        side_effect=[
            RuntimeError("Failed to resolve canonical name for mysql-k8s-0.mysql-k8s-endpoints"),
            "mysql-k8s-0.mysql-k8s-endpoints.default.svc.cluster.local",
        ],
    )
    def test_get_unit_address_retries_on_dns_not_propagated(self, mock_get_k8s_fqdn):
        """When DNS resolution fails transiently, get_unit_address must retry.

        Regression test for https://github.com/canonical/mysql-operators/issues/350.
        """
        # Use wait_none to reduce waiting between retries to zero for the sake of this test
        self.assertEqual(
            self.charm.get_unit_address.retry_with(wait=wait_none())(self.charm, self.charm.unit),
            "mysql-k8s-0.mysql-k8s-endpoints.default.svc.cluster.local.",
        )
        self.assertEqual(mock_get_k8s_fqdn.call_count, 2)

    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="mysql-k8s.somedomain")
    @patch("mysql_k8s_helpers.MySQL.is_data_dir_initialised", return_value=False)
    def test_mysql_property(self, _, mock_get_unit_address):
        # Test mysql property instance of mysql_k8s_helpers.MySQL
        # set leader and populate peer relation data
        self.harness.set_leader()
        self.harness.update_relation_data(
            self.peer_relation_id,
            f"{APP_NAME}/1",
            {
                "cluster-name": "cluster-1",
                "root-password": "root-password",
                "server-config-password": "server-config-password",
                "cluster-admin-password": "cluster-admin-password",
            },
        )

        mysql = self.charm._mysql
        self.assertTrue(isinstance(mysql, MySQL))

    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="mysql-k8s.somedomain")
    @patch("charm.MySQLOperatorCharm.unit_initialized", return_value=True)
    @patch("mysql_k8s_helpers.MySQL.is_cluster_replica", return_value=False)
    @patch("mysql_k8s_helpers.MySQL.remove_instance")
    @patch("mysql_k8s_helpers.MySQL.get_primary_label")
    @patch("mysql_k8s_helpers.MySQL.is_instance_in_cluster", return_value=True)
    def test_storage_detaching(
        self,
        mock_is_instance_in_cluster,
        mock_get_primary_label,
        mock_remove_instance,
        mock_is_cluster_replica,
        mock_unit_initialized,
        mock_get_unit_address,
    ):
        self.harness.update_relation_data(
            self.peer_relation_id,
            self.charm.app.name,
            {"cluster-name": "cluster-1", "cluster-set-domain-name": "cluster-1"},
        )
        mock_get_primary_label.return_value = self.charm.unit_label

        self.charm._on_storage_detaching(None)
        mock_remove_instance.assert_called_once_with(self.charm.unit_label, from_instance=None)

        self.assertEqual(
            self.harness.get_relation_data(self.peer_relation_id, self.charm.unit.name)[
                "unit-status"
            ],
            "removing",
        )
