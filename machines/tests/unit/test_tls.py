# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import unittest
from unittest.mock import Mock, PropertyMock, patch

from charms.mysql.v0.mysql import MySQLTLSSetupError
from mysql_shell.models import InstanceState
from ops.model import ActiveStatus, BlockedStatus
from ops.pebble import ConnectionError as PebbleConnectionError
from ops.pebble import PathError
from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import PEER


def _generate_valid_key_b64() -> str:
    """Generate a valid base64-encoded RSA private key for testing."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return base64.b64encode(pem.encode()).decode()


class TestTLS(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.peer_relation_id = self.harness.add_relation(PEER, "mysql")
        self.harness.add_relation_unit(self.peer_relation_id, "mysql/1")
        self.harness.add_relation("rolling-ops", "rolling-ops")
        self.tls = self.charm.tls

    # ---- _get_client/peer_common_name ----

    def test_get_client_common_name_with_address(self):
        """Returns unit address when available."""
        with patch.object(self.charm, "get_unit_address", return_value="1.2.3.4"):
            self.assertEqual(self.tls._get_client_common_name(), "1.2.3.4")

    def test_get_client_common_name_fallback(self):
        """Returns unit_name when address is empty."""
        with patch.object(self.charm, "get_unit_address", return_value=""):
            self.assertEqual(self.tls._get_client_common_name(), self.tls.unit_name)

    def test_get_peer_common_name_with_address(self):
        """Returns unit address when available."""
        with patch.object(self.charm, "get_unit_address", return_value="1.2.3.4"):
            self.assertEqual(self.tls._get_peer_common_name(), "1.2.3.4")

    def test_get_peer_common_name_fallback(self):
        """Returns unit_name when address is empty."""
        with patch.object(self.charm, "get_unit_address", return_value=""):
            self.assertEqual(self.tls._get_peer_common_name(), self.tls.unit_name)

    # ---- _get_client/peer_addresses ----

    def test_get_client_addresses(self):
        """Returns set with client address."""
        with patch.object(self.charm, "get_unit_address", return_value="1.2.3.4"):
            self.assertEqual(self.tls._get_client_addresses(), {"1.2.3.4"})

    def test_get_client_addresses_empty(self):
        """Returns empty set when no address."""
        with patch.object(self.charm, "get_unit_address", return_value=""):
            self.assertEqual(self.tls._get_client_addresses(), set())

    def test_get_peer_addresses(self):
        """Returns set with peer addresses."""
        with patch.object(self.charm, "get_unit_address", return_value="1.2.3.4"):
            self.assertEqual(self.tls._get_peer_addresses(), {"1.2.3.4"})

    def test_get_peer_addresses_empty(self):
        """Returns empty set when no addresses."""
        with patch.object(self.charm, "get_unit_address", return_value=""):
            self.assertEqual(self.tls._get_peer_addresses(), set())

    # ---- _get_client/peer_tls_files ----

    def test_get_client_tls_files_with_certs(self):
        """Returns key, ca, cert when certs available."""
        mock_cert = Mock()
        mock_cert.certificate = "cert"
        mock_cert.ca = "ca"
        mock_key = Mock()
        mock_key.__str__ = Mock(return_value="key")
        with patch.object(
            self.tls.client_certificate,
            "get_assigned_certificates",
            return_value=([mock_cert], mock_key),
        ):
            key, ca, cert = self.tls._get_client_tls_files()
        self.assertEqual(key, "key")
        self.assertEqual(ca, "ca")
        self.assertEqual(cert, "cert")

    def test_get_client_tls_files_empty(self):
        """Returns None tuple when no certs."""
        with patch.object(
            self.tls.client_certificate, "get_assigned_certificates", return_value=(None, None)
        ):
            key, ca, cert = self.tls._get_client_tls_files()
        self.assertIsNone(key)
        self.assertIsNone(ca)
        self.assertIsNone(cert)

    def test_get_peer_tls_files_with_certs(self):
        """Returns key, ca, cert when certs available."""
        mock_cert = Mock()
        mock_cert.certificate = "cert"
        mock_cert.ca = "ca"
        mock_key = Mock()
        mock_key.__str__ = Mock(return_value="key")
        with patch.object(
            self.tls.peer_certificate,
            "get_assigned_certificates",
            return_value=([mock_cert], mock_key),
        ):
            key, ca, cert = self.tls._get_peer_tls_files()
        self.assertEqual(key, "key")
        self.assertEqual(ca, "ca")
        self.assertEqual(cert, "cert")

    def test_get_peer_tls_files_empty(self):
        """Returns None tuple when no certs."""
        with patch.object(
            self.tls.peer_certificate, "get_assigned_certificates", return_value=(None, None)
        ):
            key, ca, cert = self.tls._get_peer_tls_files()
        self.assertIsNone(key)
        self.assertIsNone(ca)
        self.assertIsNone(cert)

    # ---- _parse_private_key ----

    def test_parse_private_key_none(self):
        """Returns None when secret_id is None."""
        self.assertIsNone(self.tls._parse_private_key(None))

    def test_parse_private_key_secret_not_found(self):
        """Returns None when secret not found."""
        from ops.model import SecretNotFoundError

        with patch.object(self.charm.model, "get_secret", side_effect=SecretNotFoundError):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_no_private_key_field(self):
        """Returns None when secret doesn't contain private-key."""
        mock_secret = Mock()
        mock_secret.get_content.return_value = {"other": "value"}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_not_base64(self):
        """Returns None when private key is not base64 encoded (contains PEM headers)."""
        mock_secret = Mock()
        mock_secret.get_content.return_value = {"private-key": "-----BEGIN RSA PRIVATE KEY-----"}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_invalid_base64(self):
        """Returns None when base64 decoding fails (invalid padding)."""
        mock_secret = Mock()
        mock_secret.get_content.return_value = {"private-key": "abc"}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_invalid_format(self):
        """Returns None when private key is valid PEM but too small (< 2048 bits)."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        small_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        small_pem = small_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        small_b64 = base64.b64encode(small_pem.encode()).decode()
        mock_secret = Mock()
        mock_secret.get_content.return_value = {"private-key": small_b64}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            self.assertIsNone(self.tls._parse_private_key("secret-id"))

    def test_parse_private_key_valid(self):
        """Returns PrivateKey when valid."""
        valid_key_b64 = _generate_valid_key_b64()
        mock_secret = Mock()
        mock_secret.get_content.return_value = {"private-key": valid_key_b64}
        with patch.object(self.charm.model, "get_secret", return_value=mock_secret):
            result = self.tls._parse_private_key("secret-id")
        self.assertIsNotNone(result)
        self.assertTrue(result.is_valid())

    # ---- _push_tls_files_to_workload ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_push_tls_files_all_present(self, _mysql):
        """Pushes all 6 files when both client and peer certs available."""
        mock_cert = Mock()
        mock_cert.certificate = "cert"
        mock_cert.ca = "ca"
        mock_key = Mock()
        mock_key.__str__ = Mock(return_value="key")
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
        self.assertEqual(_mysql.return_value.write_content_to_file.call_count, 6)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_push_tls_files_empty(self, _mysql):
        """Writes nothing when no certs available."""
        with (
            patch.object(
                self.tls.client_certificate, "get_assigned_certificates", return_value=(None, None)
            ),
            patch.object(
                self.tls.peer_certificate, "get_assigned_certificates", return_value=(None, None)
            ),
        ):
            self.tls._push_tls_files_to_workload()
        _mysql.return_value.write_content_to_file.assert_not_called()

    # ---- _on_client_certificate_available ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_client_certificate_available_not_online(self, _mysql):
        """Defers when unit is not online."""
        _mysql.return_value.get_member_state.return_value = InstanceState.OFFLINE
        event = Mock()
        self.tls._on_client_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_client_certificate_available_push_error(self, _mysql):
        """Defers when pushing TLS files fails."""
        _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        event = Mock()
        with patch.object(
            self.tls, "_push_tls_files_to_workload", side_effect=PebbleConnectionError
        ):
            self.tls._on_client_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_client_certificate_available_tls_error(self, _mysql):
        """Sets blocked status when setup_client_tls fails."""
        _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        _mysql.return_value.setup_client_tls.side_effect = MySQLTLSSetupError
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_client_certificate_available(Mock())
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    @patch("charm.MySQLOperatorCharm.build_unit_workload_status", return_value=ActiveStatus())
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_client_certificate_available_success(self, _mysql, _build_status):
        """Sets active status on success."""
        _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_client_certificate_available(Mock())
        _mysql.return_value.setup_client_tls.assert_called_once()
        _mysql.return_value.kill_client_sessions.assert_called_once()

    # ---- _on_peer_certificate_available ----

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_peer_certificate_available_not_online(self, _mysql):
        """Defers when unit is not online."""
        _mysql.return_value.get_member_state.return_value = InstanceState.OFFLINE
        event = Mock()
        self.tls._on_peer_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_peer_certificate_available_push_error(self, _mysql):
        """Defers when pushing TLS files fails."""
        _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        event = Mock()
        with patch.object(
            self.tls, "_push_tls_files_to_workload", side_effect=PathError("not-found", "test")
        ):
            self.tls._on_peer_certificate_available(event)
        event.defer.assert_called_once()

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_peer_certificate_available_tls_error(self, _mysql):
        """Sets blocked status when setup_group_tls fails."""
        _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        _mysql.return_value.setup_group_tls.side_effect = MySQLTLSSetupError
        with patch.object(self.tls, "_push_tls_files_to_workload"):
            self.tls._on_peer_certificate_available(Mock())
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_peer_certificate_available_success(self, _mysql):
        """Requests async lock on success."""
        _mysql.return_value.get_member_state.return_value = InstanceState.ONLINE
        with (
            patch.object(self.tls, "_push_tls_files_to_workload"),
            patch.object(self.charm.rolling_ops, "request_async_lock") as mock_request,
        ):
            self.tls._on_peer_certificate_available(Mock())
        _mysql.return_value.setup_group_tls.assert_called_once()
        mock_request.assert_called_with(callback_id="replication")

    # ---- _on_client_relation_broken ----

    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_client_relation_broken_removing_unit(self, _removing):
        """No-op when unit is being removed."""
        _removing.return_value = True
        self.tls._on_client_relation_broken(Mock())

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_client_relation_broken_tls_error(self, _removing, _mysql):
        """Sets blocked status when disabling client TLS fails."""
        _removing.return_value = False
        _mysql.return_value.setup_client_tls.side_effect = MySQLTLSSetupError
        self.tls._on_client_relation_broken(Mock())
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    @patch("charm.MySQLOperatorCharm.build_unit_workload_status", return_value=ActiveStatus())
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_client_relation_broken_success_non_leader(self, _removing, _mysql, _build_status):
        """Does not delete app peer data when not leader."""
        _removing.return_value = False
        self.tls._on_client_relation_broken(Mock())
        _mysql.return_value.setup_client_tls.assert_called_once()
        _mysql.return_value.kill_client_sessions.assert_called_once()

    @patch("charm.MySQLOperatorCharm.build_unit_workload_status", return_value=ActiveStatus())
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_client_relation_broken_success_leader(self, _removing, _mysql, _build_status):
        """Deletes client-private-key from app peer data when leader."""
        _removing.return_value = False
        self.harness.set_leader()
        self.charm.app_peer_data["client-private-key"] = "old-key"
        self.tls._on_client_relation_broken(Mock())
        self.assertNotIn("client-private-key", self.charm.app_peer_data)

    # ---- _on_peer_relation_broken ----

    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_peer_relation_broken_removing_unit(self, _removing):
        """No-op when unit is being removed."""
        _removing.return_value = True
        self.tls._on_peer_relation_broken(Mock())

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_peer_relation_broken_tls_error(self, _removing, _mysql):
        """Sets blocked status when disabling peer TLS fails."""
        _removing.return_value = False
        _mysql.return_value.setup_group_tls.side_effect = MySQLTLSSetupError
        self.tls._on_peer_relation_broken(Mock())
        self.assertIsInstance(self.charm.unit.status, BlockedStatus)

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_peer_relation_broken_success_non_leader(self, _removing, _mysql):
        """Requests async lock on success when not leader."""
        _removing.return_value = False
        with patch.object(self.charm.rolling_ops, "request_async_lock") as mock_request:
            self.tls._on_peer_relation_broken(Mock())
        _mysql.return_value.setup_group_tls.assert_called_once()
        mock_request.assert_called_with(callback_id="replication")

    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch("charm.MySQLOperatorCharm.removing_unit", new_callable=PropertyMock)
    def test_on_peer_relation_broken_success_leader(self, _removing, _mysql):
        """Deletes peer-private-key from app peer data when leader."""
        _removing.return_value = False
        self.harness.set_leader()
        self.charm.app_peer_data["peer-private-key"] = "old-key"
        with patch.object(self.charm.rolling_ops, "request_async_lock"):
            self.tls._on_peer_relation_broken(Mock())
        self.assertNotIn("peer-private-key", self.charm.app_peer_data)
