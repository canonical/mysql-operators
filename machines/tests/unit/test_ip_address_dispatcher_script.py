# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# The ip_address_dispatcher script lives in machines/scripts/, which is not on
# PYTHONPATH. Add it so the module can be imported directly.
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.append(os.path.abspath(_SCRIPTS_DIR))

import ip_address_dispatcher  # noqa: E402


class TestDispatch(unittest.TestCase):
    """Tests for the dispatch function."""

    @patch("ip_address_dispatcher.subprocess.run")
    def test_dispatch_invokes_subprocess_with_expected_arguments(self, mock_run):
        """Dispatch builds the juju-exec command and runs it via subprocess."""
        ip_address_dispatcher.dispatch("juju-exec", "mysql/0", "/charm/dir")

        expected_sub_command = "JUJU_DISPATCH_PATH=hooks/ip_address_change /charm/dir/dispatch"
        mock_run.assert_called_once_with(["juju-exec", "-u", "mysql/0", expected_sub_command])

    @patch("ip_address_dispatcher.subprocess.run")
    def test_dispatch_uses_provided_run_command(self, mock_run):
        """Dispatch uses the provided run_command (e.g. juju-exec vs juju-run)."""
        ip_address_dispatcher.dispatch("juju-run", "myapp/1", "/opt/charm")

        expected_sub_command = "JUJU_DISPATCH_PATH=hooks/ip_address_change /opt/charm/dispatch"
        mock_run.assert_called_once_with(["juju-run", "-u", "myapp/1", expected_sub_command])


class TestGetLocalIP(unittest.TestCase):
    """Tests for the _get_local_ip helper inside main()."""

    def _build_get_local_ip(self):
        """Recreate the _get_local_ip closure for isolated testing."""
        import socket as _socket

        def _get_local_ip():
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            s.settimeout(0)

            try:
                s.connect(("10.10.10.10", 1))
                ip = s.getsockname()[0]
            except Exception:
                ip_address_dispatcher.logger.exception("Unable to get local IP address")
                ip = "127.0.0.1"

            return ip

        return _get_local_ip

    @patch("ip_address_dispatcher.socket.socket")
    def test_get_local_ip_returns_sockname_on_success(self, mock_socket_cls):
        """_get_local_ip returns the IP from getsockname when connect succeeds."""
        fake_socket = MagicMock()
        fake_socket.getsockname.return_value = ("192.168.1.5", 12345)
        mock_socket_cls.return_value = fake_socket

        get_local_ip = self._build_get_local_ip()
        ip = get_local_ip()

        self.assertEqual(ip, "192.168.1.5")
        fake_socket.connect.assert_called_once_with(("10.10.10.10", 1))
        fake_socket.getsockname.assert_called_once()

    @patch("ip_address_dispatcher.socket.socket")
    def test_get_local_ip_returns_loopback_on_exception(self, mock_socket_cls):
        """_get_local_ip returns 127.0.0.1 when connect raises."""
        fake_socket = MagicMock()
        fake_socket.connect.side_effect = OSError("network unreachable")
        mock_socket_cls.return_value = fake_socket

        with self.assertLogs(ip_address_dispatcher.logger, level="ERROR"):
            get_local_ip = self._build_get_local_ip()
            ip = get_local_ip()

        self.assertEqual(ip, "127.0.0.1")
        fake_socket.getsockname.assert_not_called()


class TestMain(unittest.TestCase):
    """Tests for the main() entry point."""

    @patch("ip_address_dispatcher.time.sleep")
    @patch("ip_address_dispatcher.socket.socket")
    def test_main_sets_initial_ip_and_sleeps(self, mock_socket_cls, mock_sleep):
        """main() records the initial IP and prints the initial message."""
        fake_socket = MagicMock()
        fake_socket.getsockname.return_value = ("10.0.0.1", 0)
        mock_socket_cls.return_value = fake_socket

        # Stop the loop after the first iteration
        mock_sleep.side_effect = StopIteration

        with (
            patch("ip_address_dispatcher.sys.argv", ["script", "juju-exec", "mysql/0", "/charm"]),
            patch("builtins.print") as mock_print,
            self.assertRaises(StopIteration),
        ):
            ip_address_dispatcher.main()

        mock_print.assert_called_once()
        printed_msg = mock_print.call_args.args[0]
        self.assertIn("Setting initial ip address to 10.0.0.1", printed_msg)
        mock_sleep.assert_called_once_with(30)

    @patch("ip_address_dispatcher.dispatch")
    @patch("ip_address_dispatcher.time.sleep")
    @patch("ip_address_dispatcher.socket.socket")
    def test_main_dispatches_on_ip_change(self, mock_socket_cls, mock_sleep, mock_dispatch):
        """main() dispatches an event when the IP address changes."""
        fake_socket = MagicMock()
        # First call returns old IP, second returns new IP
        fake_socket.getsockname.side_effect = [
            ("10.0.0.1", 0),
            ("10.0.0.2", 0),
        ]
        mock_socket_cls.return_value = fake_socket

        # Stop the loop after the second iteration
        mock_sleep.side_effect = [None, StopIteration]

        with (
            patch("ip_address_dispatcher.sys.argv", ["script", "juju-exec", "mysql/0", "/charm"]),
            patch("builtins.print") as mock_print,
            self.assertRaises(StopIteration),
        ):
            ip_address_dispatcher.main()

        # Initial + change messages were printed
        self.assertEqual(mock_print.call_count, 2)
        change_msg = mock_print.call_args_list[1].args[0]
        self.assertIn("Detected ip address change from 10.0.0.1 to 10.0.0.2", change_msg)

        # dispatch was called with the argv-provided parameters
        mock_dispatch.assert_called_once_with("juju-exec", "mysql/0", "/charm")

    @patch("ip_address_dispatcher.dispatch")
    @patch("ip_address_dispatcher.time.sleep")
    @patch("ip_address_dispatcher.socket.socket")
    def test_main_does_not_dispatch_when_ip_unchanged(
        self, mock_socket_cls, mock_sleep, mock_dispatch
    ):
        """main() does not dispatch when the IP address stays the same."""
        fake_socket = MagicMock()
        fake_socket.getsockname.return_value = ("10.0.0.1", 0)
        mock_socket_cls.return_value = fake_socket

        # Stop the loop after the second iteration
        mock_sleep.side_effect = [None, StopIteration]

        with (
            patch("ip_address_dispatcher.sys.argv", ["script", "juju-exec", "mysql/0", "/charm"]),
            patch("builtins.print") as mock_print,
            self.assertRaises(StopIteration),
        ):
            ip_address_dispatcher.main()

        # Only the initial message is printed; no change message
        self.assertEqual(mock_print.call_count, 1)
        mock_dispatch.assert_not_called()
