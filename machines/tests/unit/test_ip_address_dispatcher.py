# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import contextlib
from unittest.mock import MagicMock, patch

from scripts.ip_address_dispatcher import dispatch, main

JUJU_HOOK = "JUJU_DISPATCH_PATH=hooks/ip_address_change"


def test_dispatch_invokes_run_command_with_ip_address_change_event():
    with patch("subprocess.run") as _run:
        dispatch("/usr/bin/juju-run", "mysql/0", "/charm")

    _run.assert_called_once_with(
        ["/usr/bin/juju-run", "-u", "mysql/0", f"{JUJU_HOOK} /charm/dispatch"],
    )


def _fake_socket(ip_address):
    """Build a MagicMock that behaves like a socket returning `ip_address`."""
    mock_socket = MagicMock()
    mock_socket.getsockname.return_value = (ip_address, 0)
    return mock_socket


def test_main_sets_initial_ip_without_dispatching():
    argv = ["ip_address_dispatcher.py", "/usr/bin/juju-run", "mysql/0", "/charm"]

    mock_socket = _fake_socket("10.0.0.1")

    with (
        patch("sys.argv", argv),
        patch("scripts.ip_address_dispatcher.dispatch") as _dispatch,
        patch("scripts.ip_address_dispatcher.socket.socket", return_value=mock_socket),
        patch("time.sleep", side_effect=InterruptedError),
        patch("builtins.print") as _print,
        patch("sys.stdout.flush") as _flush,
        contextlib.suppress(InterruptedError),
    ):
        main()

    _dispatch.assert_not_called()
    _print.assert_any_call("Setting initial ip address to 10.0.0.1")
    _flush.assert_called_once_with()


def test_main_dispatches_when_ip_changes():
    argv = ["ip_address_dispatcher.py", "/usr/bin/juju-run", "mysql/0", "/charm"]

    # First call returns 10.0.0.1 (initial), second returns 10.0.0.2 (changed).
    first_socket = _fake_socket("10.0.0.1")
    second_socket = _fake_socket("10.0.0.2")
    with (
        patch("sys.argv", argv),
        patch("scripts.ip_address_dispatcher.dispatch") as _dispatch,
        patch(
            "scripts.ip_address_dispatcher.socket.socket",
            side_effect=[first_socket, second_socket],
        ),
        patch("time.sleep", side_effect=[None, InterruptedError]),
        patch("builtins.print"),
        patch("sys.stdout.flush"),
        contextlib.suppress(InterruptedError),
    ):
        main()

    # dispatch is called only on the second iteration when the IP changed.
    _dispatch.assert_called_once_with("/usr/bin/juju-run", "mysql/0", "/charm")


def test_main_does_not_dispatch_when_ip_unchanged():
    argv = ["ip_address_dispatcher.py", "/usr/bin/juju-run", "mysql/0", "/charm"]

    # Both iterations return the same IP.
    first_socket = _fake_socket("10.0.0.1")
    second_socket = _fake_socket("10.0.0.1")
    with (
        patch("sys.argv", argv),
        patch("scripts.ip_address_dispatcher.dispatch") as _dispatch,
        patch(
            "scripts.ip_address_dispatcher.socket.socket",
            side_effect=[first_socket, second_socket],
        ),
        patch("time.sleep", side_effect=[None, InterruptedError]),
        patch("builtins.print"),
        patch("sys.stdout.flush"),
        contextlib.suppress(InterruptedError),
    ):
        main()

    _dispatch.assert_not_called()


def test_socket_connect_fails():
    argv = ["ip_address_dispatcher.py", "/usr/bin/juju-run", "mysql/0", "/charm"]

    mock_socket = MagicMock()
    mock_socket.connect.side_effect = OSError("network unreachable")

    with (
        patch("sys.argv", argv),
        patch("scripts.ip_address_dispatcher.dispatch") as _dispatch,
        patch("scripts.ip_address_dispatcher.socket.socket", return_value=mock_socket),
        patch("time.sleep", side_effect=InterruptedError),
        patch("builtins.print") as _print,
        patch("sys.stdout.flush"),
        contextlib.suppress(InterruptedError),
    ):
        main()

    # The fallback IP 127.0.0.1 is used as the initial address, so no dispatch.
    _dispatch.assert_not_called()


def test_main_parses_run_command_unit_and_charm_directory_arguments():
    captured = {}

    def _fake_dispatch(run_command, unit, charm_directory):
        captured["run_command"] = run_command
        captured["unit"] = unit
        captured["charm_directory"] = charm_directory
        raise InterruptedError

    argv = ["ip_address_dispatcher.py", "/usr/bin/juju-run", "my-unit/1", "/some/charm/dir"]
    mock_socket = _fake_socket("10.0.0.1")

    with (
        patch("sys.argv", argv),
        # The first iteration sets the initial IP; force a change on the second
        # so dispatch is invoked and we can capture the parsed arguments.
        patch("scripts.ip_address_dispatcher.dispatch", side_effect=_fake_dispatch),
        patch("scripts.ip_address_dispatcher.socket.socket", return_value=mock_socket),
        patch("time.sleep"),
        patch("builtins.print"),
        patch("sys.stdout.flush"),
        contextlib.suppress(InterruptedError),
    ):
        # Simulate an IP change by making the second getsockname return a different IP.
        mock_socket.getsockname.side_effect = [("10.0.0.1", 0), ("10.0.0.2", 0)]
        main()

    assert captured == {
        "run_command": "/usr/bin/juju-run",
        "unit": "my-unit/1",
        "charm_directory": "/some/charm/dir",
    }
