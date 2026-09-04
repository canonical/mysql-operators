# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from charms.mysql.v0.mysql import MySQLTLSSetupError
from mysql_shell.models import InstanceState
from ops.model import BlockedStatus, SecretNotFoundError
from ops.pebble import ConnectionError as PebbleConnectionError
from ops.testing import Harness

from charm import MySQLOperatorCharm

APP_NAME = "mysql-k8s"


class TestTLS(unittest.TestCase):
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
            APP_NAME,
            {"cluster-name": "test_cluster", "cluster-set-domain-name": "test_cluster_set"},
        )
        self.charm = self.harness.charm
        self.tls = self.charm.tls

    def tearDown(self):
        self.patcher.stop()

    # ------------------------------------------------------------------
    # _get_common_name
    # ------------------------------------------------------------------

    def test_get_common_name_short_endpoints(self):
        """_get_common_name returns unit_endpoints when short enough."""
        result = self.tls._get_common_name()
        self.assertEqual(result, self.tls.unit_endpoints)

    def test_get_common_name_long_endpoints(self):
        """_get_common_name returns wildcard when unit_endpoints too long."""
        self.tls.unit_endpoints = "x" * 65
        result = self.tls._get_common_name()
        self.assertEqual(result, f"*.{APP_NAME}-endpoints")

    # ------------------------------------------------------------------
    # _get_client_addresses / _get_peer_addresses
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="10.0.0.1.")
    def test_get_client_addresses(self, _get_addr):
        """_get_client_addresses returns the unit address."""
        result = self.tls._get_client_addresses()
        self.assertIn("10.0.0.1.", result)

    @patch("charm.MySQLOperatorCharm.get_unit_address", return_value="10.0.0.2.")
    def test_get_peer_addresses(self, _get_addr):
        """_get_peer_addresses returns addresses from all peer-related relations."""
        result = self.tls._get_peer_addresses()
        # get_unit_address is called for each relation name (consumer, offer, peer)
        self.assertTrue(len(result) >= 1)

    # ------------------------------------------------------------------
    # _get_client_tls_files / _get_peer_tls_files
    # ------------------------------------------------------------------

    def test_get_client_tls_files_no_certs(self):
        """_get_client_tls_files returns None when no certificates assigned."""
        with patch.object(self.tls.client_certificate, "get_assigned_certificates") as mock_get:
            mock_get.return_value = ([], None)
            key, ca, cert = self.tls._get_client_tls_files()
        self.assertIsNone(key)
        self.assertIsNone(ca)
        self.assertIsNone(cert)

    def test_get_client_tls_files_with_certs(self):
        """_get_client_tls_files returns key, ca, and cert when assigned."""
        mock_cert = MagicMock()
        mock_cert.certificate = "cert-content"
        mock_cert.ca = "ca-content"
        mock_key = MagicMock()
        mock_key.__str__ = MagicMock(return_value="key-content")
        with patch.object(self.tls.client_certificate, "get_assigned_certificates") as mock_get:
            mock_get.return_value = ([mock_cert], mock_key)
            key, ca, cert = self.tls._get_client_tls_files()
        self.assertEqual(key, "key-content")
        self.assertEqual(ca, "ca-content")
        self.assertEqual(cert, "cert-content")

    def test_get_peer_tls_files_no_certs(self):
        """_get_peer_tls_files returns None when no certificates assigned."""
        with patch.object(self.tls.peer_certificate, "get_assigned_certificates") as mock_get:
            mock_get.return_value = ([], None)
            key, ca, cert = self.tls._get_peer_tls_files()
        self.assertIsNone(key)
        self.assertIsNone(ca)
        self.assertIsNone(cert)

    # ------------------------------------------------------------------
    # _parse_private_key
    # ------------------------------------------------------------------

    def test_parse_private_key_none(self):
        """_parse_private_key returns None when secret_id is None."""
        self.assertIsNone(self.tls._parse_private_key(None))

    def test_parse_private_key_secret_not_found(self):
        """_parse_private_key returns None when secret not found."""
        with patch.object(self.charm.model, "get_secret", side_effect=SecretNotFoundError):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_no_key_field(self):
        """_parse_private_key returns None when secret has no private-key field."""
        mock_secret = MagicMock()
        mock_secret.get_content.return_value = {}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_not_base64(self):
        """_parse_private_key returns None when key is not base64-encoded (PEM header present)."""
        mock_secret = MagicMock()
        mock_secret.get_content.return_value = {"private-key": "-----BEGIN PRIVATE KEY-----"}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_invalid_base64(self):
        """_parse_private_key returns None on invalid base64."""
        mock_secret = MagicMock()
        mock_secret.get_content.return_value = {"private-key": "!@#$invalid"}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    # ------------------------------------------------------------------
    # _on_client_certificate_available
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_client_cert_available_defers_when_not_online(self, mock_mysql):
        """_on_client_certificate_available defers when unit not online."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.RECOVERING
        event = MagicMock()
        self.tls._on_client_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_client_cert_available_push_error_defers(self, mock_mysql):
        """_on_client_certificate_available defers when pushing files fails."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        event = MagicMock()
        with patch.object(
            self.tls, "_push_tls_files_to_workload", side_effect=PebbleConnectionError
        ):
            self.tls._on_client_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_client_cert_available_tls_setup_error(self, mock_mysql):
        """_on_client_certificate_available sets Blocked when TLS setup fails."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        mock_mysql.return_value.setup_client_tls.side_effect = MySQLTLSSetupError
        event = MagicMock()
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_client_certificate_available(event)
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_client_cert_available_success(self, mock_mysql):
        """_on_client_certificate_available sets up client TLS on success."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        event = MagicMock()
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_client_certificate_available(event)
        mock_mysql.return_value.setup_client_tls.assert_called_once()
        mock_mysql.return_value.kill_client_sessions.assert_called_once()

    # ------------------------------------------------------------------
    # _on_peer_certificate_available
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_cert_available_defers_when_not_online(self, mock_mysql):
        """_on_peer_certificate_available defers when unit not online."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.RECOVERING
        event = MagicMock()
        self.tls._on_peer_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_cert_available_push_error_defers(self, mock_mysql):
        """_on_peer_certificate_available defers when pushing files fails."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        event = MagicMock()
        with patch.object(
            self.tls, "_push_tls_files_to_workload", side_effect=PebbleConnectionError
        ):
            self.tls._on_peer_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_cert_available_tls_setup_error(self, mock_mysql):
        """_on_peer_certificate_available sets Blocked when group TLS setup fails."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        mock_mysql.return_value.setup_group_tls.side_effect = MySQLTLSSetupError
        event = MagicMock()
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_peer_certificate_available(event)
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_cert_available_success(self, mock_mysql):
        """_on_peer_certificate_available sets up group TLS on success."""
        mock_mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        self.charm.rolling_ops = MagicMock()
        event = MagicMock()
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_peer_certificate_available(event)
        mock_mysql.return_value.setup_group_tls.assert_called_once()
        self.charm.rolling_ops.request_async_lock.assert_called_once_with(
            callback_id="replication"
        )

    # ------------------------------------------------------------------
    # _on_client_relation_broken
    # ------------------------------------------------------------------

    def test_client_relation_broken_removing_unit(self):
        """_on_client_relation_broken skips when unit is being removed."""
        self.charm.unit_peer_data["unit-status"] = "removing"
        self.tls._on_client_relation_broken(MagicMock())
        # Should not set MaintenanceStatus

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_client_relation_broken_tls_error(self, mock_mysql):
        """_on_client_relation_broken sets Blocked when disabling TLS fails."""
        mock_mysql.return_value.setup_client_tls.side_effect = MySQLTLSSetupError
        self.tls._on_client_relation_broken(MagicMock())
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_client_relation_broken_success(self, mock_mysql):
        """_on_client_relation_broken disables TLS and clears key on leader."""
        self.harness.set_leader()
        self.charm.app_peer_data["client-private-key"] = "old-key"
        self.tls._on_client_relation_broken(MagicMock())
        mock_mysql.return_value.setup_client_tls.assert_called_once()
        mock_mysql.return_value.kill_client_sessions.assert_called_once()
        self.assertNotIn("client-private-key", self.charm.app_peer_data)

    # ------------------------------------------------------------------
    # _on_peer_relation_broken
    # ------------------------------------------------------------------

    def test_peer_relation_broken_removing_unit(self):
        """_on_peer_relation_broken skips when unit is being removed."""
        self.charm.unit_peer_data["unit-status"] = "removing"
        self.tls._on_peer_relation_broken(MagicMock())

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_relation_broken_tls_error(self, mock_mysql):
        """_on_peer_relation_broken sets Blocked when disabling group TLS fails."""
        mock_mysql.return_value.setup_group_tls.side_effect = MySQLTLSSetupError
        self.tls._on_peer_relation_broken(MagicMock())
        self.assertTrue(isinstance(self.charm.unit.status, BlockedStatus))

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_peer_relation_broken_success(self, mock_mysql):
        """_on_peer_relation_broken disables group TLS and clears key on leader."""
        self.harness.set_leader()
        self.charm.rolling_ops = MagicMock()
        self.charm.app_peer_data["peer-private-key"] = "old-key"
        self.tls._on_peer_relation_broken(MagicMock())
        mock_mysql.return_value.setup_group_tls.assert_called_once()
        self.assertNotIn("peer-private-key", self.charm.app_peer_data)

    # ------------------------------------------------------------------
    # _push_tls_files_to_workload
    # ------------------------------------------------------------------

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_push_tls_files_writes_all_files(self, mock_mysql):
        """_push_tls_files_to_workload writes client and peer files when present."""
        mock_cert = MagicMock()
        mock_cert.certificate = "cert"
        mock_cert.ca = "ca"
        mock_key = MagicMock()
        mock_key.__str__ = MagicMock(return_value="key")
        with (
            patch.object(
                self.tls.client_certificate,
                "get_assigned_certificates",
                return_value=([mock_cert], mock_key),
            ),
            patch.object(
                self.tls.peer_certificate,
                "get_assigned_certificates",
                return_value=([mock_cert], mock_key),
            ),
        ):
            self.tls._push_tls_files_to_workload()
        # 6 write calls (client key/ca/cert + peer key/ca/cert)
        self.assertEqual(mock_mysql.return_value.write_content_to_file.call_count, 6)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_push_tls_files_skips_none(self, mock_mysql):
        """_push_tls_files_to_workload writes nothing when no certs."""
        with (
            patch.object(
                self.tls.client_certificate, "get_assigned_certificates", return_value=([], None)
            ),
            patch.object(
                self.tls.peer_certificate, "get_assigned_certificates", return_value=([], None)
            ),
        ):
            self.tls._push_tls_files_to_workload()
        mock_mysql.return_value.write_content_to_file.assert_not_called()
