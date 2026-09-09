# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

import tenacity
from parameterized import parameterized

from utils import (
    _password_meets_rules,
    any_memory_to_bytes,
    generate_pebble_layer_env,
    generate_random_password,
    get_k8s_fqdn,
    split_mem,
)


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

    @patch.dict(
        os.environ,
        {
            "JUJU_CHARM_HTTP_PROXY": "http://squid.internal:3128",
            "JUJU_CHARM_HTTPS_PROXY": "http://squid.internal:3128",
            "JUJU_CHARM_NO_PROXY": "10.0.0.0/8,localhost,127.0.0.1,.internal",
        },
    )
    def test_generate_pebble_layer_env_no_proxy_is_sorted(self):
        """NO_PROXY entries are emitted in a stable, sorted order."""
        environment = generate_pebble_layer_env()

        self.assertEqual(
            environment["NO_PROXY"],
            ".internal,.svc.cluster.local,10.0.0.0/8,127.0.0.1,localhost",
        )
        self.assertEqual(environment["HTTP_PROXY"], "http://squid.internal:3128")
        self.assertEqual(environment["HTTPS_PROXY"], "http://squid.internal:3128")

    @patch.dict(
        os.environ,
        {
            "JUJU_CHARM_HTTP_PROXY": "http://squid.internal:3128",
            "JUJU_CHARM_HTTPS_PROXY": "",
            "JUJU_CHARM_NO_PROXY": "",
        },
    )
    def test_generate_pebble_layer_env_no_proxy_drops_empty_entries(self):
        """An empty JUJU_CHARM_NO_PROXY must not produce an empty NO_PROXY entry."""
        self.assertEqual(generate_pebble_layer_env()["NO_PROXY"], ".svc.cluster.local")

    def test_generate_pebble_layer_env_stable_across_hash_seeds(self):
        """The env must be identical across processes.

        The mysqld pebble layer embeds this environment, so any variation
        between hook invocations makes `_reconcile_pebble_layer` see a changed
        layer and restart mysqld. Python randomizes PYTHONHASHSEED per process,
        which is why this has to be checked out-of-process.
        """
        child_env = os.environ | {
            "JUJU_CHARM_HTTP_PROXY": "http://squid.internal:3128",
            "JUJU_CHARM_HTTPS_PROXY": "http://squid.internal:3128",
            "JUJU_CHARM_NO_PROXY": "10.0.0.0/8,localhost,127.0.0.1,.internal",
            "PYTHONPATH": os.pathsep.join(sys.path),
        }
        child_env.pop("PYTHONHASHSEED", None)

        results = {
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from utils import generate_pebble_layer_env;"
                    "print(generate_pebble_layer_env()['NO_PROXY'])",
                ],
                env=child_env,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
            for _ in range(10)
        }

        self.assertEqual(len(results), 1, f"NO_PROXY is not deterministic: {results}")

    @patch("utils.socket.getaddrinfo")
    def test_get_k8s_fqdn_local_unit(self, mock_getaddrinfo):
        """Test get_k8s_fqdn when name refers to the local unit."""
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
            get_k8s_fqdn("mysql-2.mysql-endpoints", "mysql-2"),
            "mysql-2.mysql-endpoints.default.svc.cluster.local.",
        )
        mock_getaddrinfo.assert_called_once_with(
            "mysql-2",
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )

    @patch("utils.socket.getaddrinfo")
    def test_get_k8s_fqdn_other_unit(self, mock_getaddrinfo):
        """Test get_k8s_fqdn when name refers to a different unit."""
        mock_getaddrinfo.return_value = [
            (
                None,
                None,
                None,
                "mysql-2.mysql-endpoints.default.svc.cluster.local",
                None,
            ),
        ]

        self.assertEqual(
            get_k8s_fqdn("mysql-1.mysql-endpoints", "mysql-2"),
            "mysql-1.mysql-endpoints.default.svc.cluster.local.",
        )
        mock_getaddrinfo.assert_called_once_with(
            "mysql-2",
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )

    @patch("utils.socket.getaddrinfo", side_effect=socket.gaierror)
    def test_get_k8s_fqdn_resolution_error(self, mock_getaddrinfo):
        get_k8s_fqdn.retry.retry = tenacity.retry_if_not_result(
            lambda x: True
        )  # Disable retry for testing
        with self.assertRaisesRegex(RuntimeError, "Failed to resolve canonical _name='mysql-2'"):
            get_k8s_fqdn("mysql-2.mysql-endpoints", "mysql-2")

        mock_getaddrinfo.assert_called_with(
            "mysql-2",
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
            RuntimeError, "Could not determine canonical for name='mysql-2.mysql-endpoints'"
        ):
            get_k8s_fqdn("mysql-2.mysql-endpoints", "mysql-2")

        mock_getaddrinfo.assert_called_with(
            "mysql-2.mysql-endpoints",
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )
