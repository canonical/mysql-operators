# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import socket
import unittest
from unittest.mock import patch

from parameterized import parameterized

from utils import _password_meets_rules, any_memory_to_bytes, generate_random_password, get_k8s_fqdn, split_mem


class TestUtils(unittest.TestCase):
    def test_generate_random_password(self):
        password = generate_random_password(16)
        self.assertEqual(len(password), 16)
        self.assertTrue(password.isalnum())
        self.assertTrue(_password_meets_rules(password))

    @parameterized.expand([
        ("valid", "Abc123", True),
        ("no_uppercase", "abc123", False),
        ("no_lowercase", "ABC123", False),
        ("no_digit", "AbcDef", False),
    ])
    def test_password_meets_rules(self, name, password, expected):
        self.assertEqual(_password_meets_rules(password), expected)

    def test_split_mem(self):
        self.assertEqual(split_mem("1Gi"), ("1", "Gi"))
        self.assertEqual(split_mem("1G"), ("1", "G"))
        self.assertEqual(split_mem("1"), (None, "No unit found"))

    def test_any_memory_to_bytes(self):
        self.assertEqual(any_memory_to_bytes("1Gi"), 1073741824)
        self.assertEqual(any_memory_to_bytes("1G"), 10**9)
        self.assertEqual(any_memory_to_bytes("1024"), 1024)

    @patch("utils.socket.getaddrinfo")
    def test_get_k8s_fqdn(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (
                None,
                None,
                None,
                "",
                None,
            ),
            (
                None,
                None,
                None,
                "mysql-2.mysql-endpoints.default.svc.cluster.local.",
                None,
            ),
        ]

        self.assertEqual(
            get_k8s_fqdn("mysql-2.mysql-endpoints"),
            "mysql-2.mysql-endpoints.default.svc.cluster.local.",
        )
        mock_getaddrinfo.assert_called_once_with(
            "mysql-2.mysql-endpoints",
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )

    @patch("utils.socket.getaddrinfo", side_effect=socket.gaierror)
    def test_get_k8s_fqdn_resolution_error(self, mock_getaddrinfo):
        with self.assertRaisesRegex(
            RuntimeError, "Failed to resolve canonical name for mysql-2.mysql-endpoints"
        ):
            get_k8s_fqdn("mysql-2.mysql-endpoints")

        mock_getaddrinfo.assert_called_once_with(
            "mysql-2.mysql-endpoints",
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )

    @patch("utils.socket.getaddrinfo")
    def test_get_k8s_fqdn_without_canonical_name(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (
                None,
                None,
                None,
                "",
                None,
            ),
            (
                None,
                None,
                None,
                "",
                None,
            ),
        ]

        with self.assertRaisesRegex(
            RuntimeError, "Could not determine canonical name for mysql-2.mysql-endpoints"
        ):
            get_k8s_fqdn("mysql-2.mysql-endpoints")

        mock_getaddrinfo.assert_called_once_with(
            "mysql-2.mysql-endpoints",
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )
