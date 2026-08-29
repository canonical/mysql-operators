# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus
from ops.testing import Harness
from tenacity import wait_none

from charm import MySQLOperatorCharm
from constants import (
    BACKUPS_PASSWORD_KEY,
    CONTAINER_NAME,
    DEFAULT_PASSWORD_LENGTH,
    MONITORING_PASSWORD_KEY,
    MYSQL_DATA_DIR,
    MYSQL_LOGS_DIR,
    MYSQLD_LOCATION,
    OPERATOR_PASSWORD_KEY,
    REPLICATION_PASSWORD_KEY,
)
from k8s_helpers import KubernetesClientError
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

    def layer_dict(self):
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
                    "startup": "enabled",
                    "user": "mysql",
                    "group": "mysql",
                    "environment": {
                        "EXPORTER_USER": "charmed-stats",
                        "EXPORTER_PASS": self.charm.get_secret("app", "monitoring-password"),
                    },
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

    @patch("charm.MySQLOperatorCharm._mysql_pebble_ready_checks", return_value=False)
    @patch("charm.MySQLOperatorCharm.refresh", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm._write_mysqld_configuration")
    def test_mysql_pebble_ready_k8s_api_denied(
        self, _write_mysqld_configuration, _refresh, _checks
    ):
        """When k8s API access is denied (no trust), pebble-ready defers and blocks."""
        from ops.charm import PebbleReadyEvent

        _write_mysqld_configuration.side_effect = KubernetesClientError
        _refresh.return_value = None

        event = MagicMock(spec=PebbleReadyEvent)
        event.workload = self.harness.charm.unit.get_container("mysql")

        self.charm._on_mysql_pebble_ready(event)

        event.defer.assert_called_once()
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

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

    @patch("k8s_helpers.KubernetesHelpers.create_endpoint_services")
    def test_create_endpoint_services(self, _create_endpoint_services):
        """_create_endpoint_services creates the primary & replicas k8s services.

        Pod labeling (update_endpoints) and readiness wait live in the relation
        handler, not here — early creation only cares about surfacing k8s API errors.
        """
        result = self.charm._create_endpoint_services()

        self.assertTrue(result)
        _create_endpoint_services.assert_called_once_with(["primary", "replicas"])

    @patch(
        "k8s_helpers.KubernetesHelpers.create_endpoint_services",
        side_effect=KubernetesClientError,
    )
    def test_create_endpoint_services_permission_denied(self, _create_endpoint_services):
        """When k8s service creation is denied (juju trust), unit is Blocked and returns False."""
        result = self.charm._create_endpoint_services()

        self.assertFalse(result)
        _create_endpoint_services.assert_called_once_with(["primary", "replicas"])
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

    @patch("charm.MySQLOperatorCharm._create_endpoint_services")
    def test_on_start_creates_endpoint_services(self, _create_endpoint_services):
        """On start, the leader creates k8s endpoint services early in the lifecycle."""
        _create_endpoint_services.return_value = True
        self.harness.set_leader()
        self.charm.on.start.emit()

        _create_endpoint_services.assert_called_once()

    @patch("charm.MySQLOperatorCharm._create_endpoint_services")
    def test_on_start_non_leader_skips(self, _create_endpoint_services):
        """Non-leader units do not create endpoint services on start."""
        self.charm.on.start.emit()

        _create_endpoint_services.assert_not_called()

    @patch("ops.charm.StartEvent.defer")
    @patch("charm.MySQLOperatorCharm._create_endpoint_services")
    def test_on_start_defers_when_not_trusted(self, _create_endpoint_services, _defer):
        """When service creation fails (no trust), start event is deferred for auto-retry."""
        _create_endpoint_services.return_value = False
        self.harness.set_leader()

        self.charm.on.start.emit()
        _defer.assert_called_once()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def test_text_logs_includes_audit_when_enabled(self):
        """text_logs includes 'audit' when plugin-audit-enabled is True."""
        self.harness.update_config({"plugin-audit-enabled": True})
        self.assertEqual(self.charm.text_logs, ["error", "audit"])

    def test_text_logs_excludes_audit_when_disabled(self):
        """text_logs only includes 'error' when plugin-audit-enabled is False."""
        self.harness.update_config({"plugin-audit-enabled": False})
        self.assertEqual(self.charm.text_logs, ["error"])

    def test_get_unit_hostname(self):
        """get_unit_hostname translates unit name to k8s hostname."""
        self.assertEqual(
            self.charm.get_unit_hostname("mysql-k8s/0"),
            "mysql-k8s-0.mysql-k8s-endpoints",
        )

    def test_get_unit_hostname_defaults_to_self(self):
        """get_unit_hostname defaults to this unit when no argument."""
        self.assertEqual(
            self.charm.get_unit_hostname(),
            "mysql-k8s-0.mysql-k8s-endpoints",
        )

    def test_is_new_unit_true(self):
        """is_new_unit is True when only default keys present."""
        # Clear all keys and set only the default keys
        for key in list(self.charm.unit_peer_data.keys()):
            del self.charm.unit_peer_data[key]
        self.charm.unit_peer_data["egress-subnets"] = "10.0.0.0/24"
        self.charm.unit_peer_data["ingress-address"] = "10.0.0.1"
        self.charm.unit_peer_data["private-address"] = "10.0.0.1"
        self.assertTrue(self.charm.is_new_unit)

    def test_is_new_unit_false(self):
        """is_new_unit is False when extra keys are present."""
        self.charm.unit_peer_data["member-state"] = "online"
        self.assertFalse(self.charm.is_new_unit)

    def test_unit_initialized_cannot_connect(self):
        """unit_initialized returns False when container not accessible."""
        self.harness.set_can_connect(CONTAINER_NAME, False)
        self.assertFalse(self.charm.unit_initialized())

    # ------------------------------------------------------------------
    # _on_peer_relation_joined
    # ------------------------------------------------------------------

    def test_on_peer_relation_joined_sets_defaults(self):
        """_on_peer_relation_joined sets member-role and member-state defaults."""
        self.charm._on_peer_relation_joined(None)
        self.assertEqual(self.charm.unit_peer_data["member-role"], "UNKNOWN")
        self.assertEqual(self.charm.unit_peer_data["member-state"], "waiting")

    # ------------------------------------------------------------------
    # _rotate_private_keys
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm.config", new_callable=PropertyMock)
    def test_rotate_private_keys_emits_refresh_on_change(self, mock_config):
        """_rotate_private_keys emits refresh events when keys change."""
        mock_tls = MagicMock()
        mock_tls.client_certificates_refresh_event = MagicMock()
        mock_tls.peer_certificates_refresh_event = MagicMock()
        self.charm.tls = mock_tls
        self.harness.set_leader()

        mock_config.return_value.tls_client_private_key = "new-client-key"
        mock_config.return_value.tls_peer_private_key = "new-peer-key"
        self.charm._rotate_private_keys()

        mock_tls.client_certificates_refresh_event.emit.assert_called_once()
        mock_tls.peer_certificates_refresh_event.emit.assert_called_once()
        self.assertEqual(self.charm.app_peer_data["client-private-key"], "new-client-key")
        self.assertEqual(self.charm.app_peer_data["peer-private-key"], "new-peer-key")

    @patch("charm.MySQLOperatorCharm.config", new_callable=PropertyMock)
    def test_rotate_private_keys_no_change(self, mock_config):
        """_rotate_private_keys does not emit when keys unchanged."""
        mock_tls = MagicMock()
        mock_tls.client_certificates_refresh_event = MagicMock()
        mock_tls.peer_certificates_refresh_event = MagicMock()
        self.charm.tls = mock_tls
        self.charm.app_peer_data["client-private-key"] = "same-key"
        self.charm.app_peer_data["peer-private-key"] = "same-peer-key"

        mock_config.return_value.tls_client_private_key = "same-key"
        mock_config.return_value.tls_peer_private_key = "same-peer-key"
        self.charm._rotate_private_keys()

        mock_tls.client_certificates_refresh_event.emit.assert_not_called()
        mock_tls.peer_certificates_refresh_event.emit.assert_not_called()

    # ------------------------------------------------------------------
    # set_unit_status
    # ------------------------------------------------------------------

    def test_set_unit_status_no_refresh(self):
        """set_unit_status sets status directly when refresh is None."""
        self.charm._refresh = None
        self.charm.set_unit_status(MaintenanceStatus("test"))
        self.assertTrue(isinstance(self.charm.unit.status, MaintenanceStatus))

    def test_set_unit_status_refresh_higher_priority(self):
        """set_unit_status does not override higher priority refresh status."""
        self.charm._refresh.unit_status_higher_priority = True
        self.charm.unit.status = ActiveStatus("existing")
        self.charm.set_unit_status(MaintenanceStatus("test"))
        self.assertTrue(isinstance(self.charm.unit.status, ActiveStatus))

    def test_set_unit_status_refresh_lower_priority_overrides_active(self):
        """set_unit_status uses lower priority refresh status when current is Active."""
        refresh_status = MaintenanceStatus("refreshing")
        self.charm._refresh.unit_status_higher_priority = None
        self.charm._refresh.unit_status_lower_priority.return_value = refresh_status
        self.charm.set_unit_status(ActiveStatus("ok"))
        self.assertTrue(isinstance(self.charm.unit.status, MaintenanceStatus))

    # ------------------------------------------------------------------
    # _set_app_status
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm.build_app_workload_status")
    def test_set_app_status_leader_online(self, mock_build):
        """_set_app_status sets app status when leader and online."""
        from charms.mysql.v0.mysql import InstanceState

        mock_build.return_value = ActiveStatus("ok")
        self.harness.set_leader()
        self.charm._set_app_status(InstanceState.ONLINE)
        self.assertTrue(isinstance(self.charm.app.status, ActiveStatus))

    @patch("charm.MySQLOperatorCharm.build_app_workload_status")
    def test_set_app_status_non_leader(self, mock_build):
        """_set_app_status is a no-op when non-leader."""
        from charms.mysql.v0.mysql import InstanceState

        self.charm._set_app_status(InstanceState.ONLINE)
        mock_build.assert_not_called()

    @patch("charm.MySQLOperatorCharm.build_app_workload_status")
    def test_set_app_status_not_online(self, mock_build):
        """_set_app_status is a no-op when state is not online."""
        from charms.mysql.v0.mysql import InstanceState

        self.harness.set_leader()
        self.charm._set_app_status(InstanceState.OFFLINE)
        mock_build.assert_not_called()

    # ------------------------------------------------------------------
    # _all_peers_reachable
    # ------------------------------------------------------------------

    @patch("charm.socket.create_connection")
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="1.2.3.4")
    def test_all_peers_reachable_true(self, _get_addr, mock_socket):
        """_all_peers_reachable returns True when all peers respond."""
        mock_socket.return_value.__enter__ = MagicMock()
        self.assertTrue(self.charm._all_peers_reachable())

    @patch("charm.socket.create_connection", side_effect=OSError("unreachable"))
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="1.2.3.4")
    def test_all_peers_reachable_false(self, _get_addr, _mock_socket):
        """_all_peers_reachable returns False when a peer is unreachable."""
        self.assertFalse(self.charm._all_peers_reachable())

    # ------------------------------------------------------------------
    # _get_primary_from_online_peer
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="peer-address")
    def test_get_primary_from_online_peer_success(self, _get_addr, mock_mysql):
        """_get_primary_from_online_peer returns primary address from online peer."""
        from charms.mysql.v0.mysql import InstanceState

        online_unit = next(iter(self.charm.peers.units))
        self.charm.peers.data[online_unit]["member-state"] = InstanceState.ONLINE
        mock_mysql.return_value.get_cluster_primary_address.return_value = "primary:3306"

        result = self.charm._get_primary_from_online_peer()
        self.assertEqual(result, "primary:3306")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="peer-address")
    def test_get_primary_from_online_peer_no_online(self, _get_addr, mock_mysql):
        """_get_primary_from_online_peer returns None when no peer is online."""
        mock_mysql.return_value.get_cluster_primary_address.return_value = None
        result = self.charm._get_primary_from_online_peer()
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # update_endpoints
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._on_update_status")
    def test_update_endpoints(self, mock_update_status):
        """update_endpoints configures endpoints and triggers update status."""
        self.charm.database_relation = MagicMock()
        self.charm.update_endpoints()
        self.charm.database_relation._configure_endpoints.assert_called_once_with(None)
        mock_update_status.assert_called_once_with(None)
