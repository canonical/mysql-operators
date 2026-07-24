# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import unittest
from unittest.mock import PropertyMock, patch

from ops.testing import Harness

from charm import MySQLOperatorCharm
from constants import HOSTNAME_DETAILS, PEER
from mysql_vm_helpers import MySQLFlushHostCacheError

APP_NAME = "mysql"


class TestHostnameResolution(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(MySQLOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm
        self.hostname_observer = self.charm.hostname_observer

    def test_get_host_details(self):
        """Test get_peer_host_details method."""
        host_entries = self.hostname_observer._get_host_details()

        # before relation
        self.assertEqual(host_entries, [])

        # Add relation
        peer_relation_id = self.harness.add_relation(PEER, APP_NAME)

        host_entries = self.hostname_observer._get_host_details()
        self.assertEqual(host_entries, [])

        # Add unit
        self.harness.add_relation_unit(peer_relation_id, f"{APP_NAME}/0")
        self.harness.update_relation_data(
            peer_relation_id,
            f"{APP_NAME}/0",
            {
                HOSTNAME_DETAILS: json.dumps({
                    "address": "1.1.1.1",
                    "names": ["name1", "name2", "name3"],
                })
            },
        )

        host_entries = self.hostname_observer._get_host_details()
        self.assertEqual(len(host_entries), 1)
        self.assertEqual(host_entries[0].address, "1.1.1.1")

    @patch("socket.gethostname", return_value="mysql-0")
    def test_update_host_details_in_databag(self, _gethostname_mock):
        """Test update_host_details_in_databag method."""
        # Add relation
        self.harness.add_relation(PEER, APP_NAME)
        self.assertEqual(self.charm.unit_peer_data.get(HOSTNAME_DETAILS), None)
        self.hostname_observer._update_host_details_in_databag(None)
        _gethostname_mock.assert_called()

        self.assertTrue("mysql-0" in self.charm.unit_peer_data[HOSTNAME_DETAILS])

    @patch("socket.getfqdn", return_value="fqdn")
    @patch("socket.gethostname", return_value="mysql-0")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    def test_on_ip_address_change(self, _mysql, _gethostname_mock, _getfqdn_mock):
        """Test _on_ip_address_change updates databag and restarts mysqld."""
        self.harness.add_relation(PEER, APP_NAME)
        self.hostname_observer._on_ip_address_change(None)
        _mysql.return_value.restart_mysqld.assert_called_once()
        self.assertIn(HOSTNAME_DETAILS, self.charm.unit_peer_data)

    def test_get_host_details_old_format(self):
        """Test _get_host_details migrates the old format (ip/hostname/fqdn)."""
        peer_relation_id = self.harness.add_relation(PEER, APP_NAME)
        self.harness.add_relation_unit(peer_relation_id, f"{APP_NAME}/0")
        self.harness.update_relation_data(
            peer_relation_id,
            f"{APP_NAME}/0",
            {HOSTNAME_DETAILS: json.dumps({"ip": "1.2.3.4", "hostname": "h", "fqdn": "f"})},
        )
        host_entries = self.hostname_observer._get_host_details()
        self.assertEqual(len(host_entries), 1)
        self.assertEqual(host_entries[0].address, "1.2.3.4")
        self.assertEqual(host_entries[0].names, ["h", "f"])

    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=False),
    )
    def test_update_etc_hosts_peer_data_not_set(self, _):
        """update_etc_hosts returns False when peer data is not set."""
        self.assertFalse(self.hostname_observer.update_etc_hosts(None))

    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=True),
    )
    def test_update_etc_hosts_no_host_entries(self, _):
        """update_etc_hosts returns False when there are no host entries."""
        self.harness.add_relation(PEER, APP_NAME)
        self.assertFalse(self.hostname_observer.update_etc_hosts(None))

    @patch("python_hosts.Hosts.write")
    @patch("python_hosts.Hosts.exists", return_value=False)
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=True),
    )
    def test_update_etc_hosts_no_loopback(self, _is_peer_data_set, _mysql, _exists, _write):
        """update_etc_hosts writes hosts and flushes cache when no loopback."""
        peer_relation_id = self.harness.add_relation(PEER, APP_NAME)
        self.harness.add_relation_unit(peer_relation_id, f"{APP_NAME}/0")
        self.harness.update_relation_data(
            peer_relation_id,
            f"{APP_NAME}/0",
            {HOSTNAME_DETAILS: json.dumps({"address": "1.1.1.1", "names": ["n"]})},
        )
        result = self.hostname_observer.update_etc_hosts(None)
        self.assertFalse(result)
        _write.assert_called_once()
        _mysql.return_value.flush_host_cache.assert_called_once()

    @patch("python_hosts.Hosts.write")
    @patch("python_hosts.Hosts.remove_all_matching")
    @patch("python_hosts.Hosts.exists", return_value=True)
    @patch("socket.getfqdn", return_value="fqdn")
    @patch("charm.MySQLOperatorCharm._mysql", new_callable=PropertyMock)
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=True),
    )
    def test_update_etc_hosts_loopback_exists(
        self,
        _is_peer_data_set,
        _mysql,
        _getfqdn,
        _exists,
        _remove,
        _write,
    ):
        """update_etc_hosts removes MAAS loopback entry and returns True."""
        peer_relation_id = self.harness.add_relation(PEER, APP_NAME)
        self.harness.add_relation_unit(peer_relation_id, f"{APP_NAME}/0")
        self.harness.update_relation_data(
            peer_relation_id,
            f"{APP_NAME}/0",
            {HOSTNAME_DETAILS: json.dumps({"address": "1.1.1.1", "names": ["n"]})},
        )
        result = self.hostname_observer.update_etc_hosts(None)
        self.assertTrue(result)
        # MAAS entry removed by address
        _remove.assert_any_call(address="127.0.1.1")
        _write.assert_called_once()

    @patch("python_hosts.Hosts.write")
    @patch("python_hosts.Hosts.exists", return_value=False)
    @patch(
        "charm.MySQLOperatorCharm._mysql",
        new_callable=PropertyMock,
    )
    @patch(
        "charm.MySQLOperatorCharm._is_peer_data_set",
        new_callable=PropertyMock(return_value=True),
    )
    def test_update_etc_hosts_flush_cache_error(self, _is_peer_data_set, _mysql, _exists, _write):
        """update_etc_hosts swallows MySQLFlushHostCacheError."""
        _mysql.return_value.flush_host_cache.side_effect = MySQLFlushHostCacheError
        peer_relation_id = self.harness.add_relation(PEER, APP_NAME)
        self.harness.add_relation_unit(peer_relation_id, f"{APP_NAME}/0")
        self.harness.update_relation_data(
            peer_relation_id,
            f"{APP_NAME}/0",
            {HOSTNAME_DETAILS: json.dumps({"address": "1.1.1.1", "names": ["n"]})},
        )
        # should not raise
        result = self.hostname_observer.update_etc_hosts(None)
        self.assertFalse(result)
