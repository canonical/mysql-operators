# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import contextlib
from unittest.mock import call, patch

from scripts.self_healing_dispatcher import dispatch, main

JUJU_HOOK = "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster"


def test_dispatch_invokes_run_command_with_heal_event():
    with patch("subprocess.run") as _run:
        dispatch("/usr/bin/juju-run", "mysql/0", "/charm")

    _run.assert_called_once_with(
        ["/usr/bin/juju-run", "-u", "mysql/0", f"{JUJU_HOOK} /charm/dispatch"],
    )


def test_main_loops_dispatching_every_120s_until_interrupted():
    argv = ["self_healing_dispatcher.py", "/usr/bin/juju-run", "mysql/0", "/charm"]

    with (
        patch("sys.argv", argv),
        patch("scripts.self_healing_dispatcher.dispatch") as _dispatch,
        patch("time.sleep", side_effect=[None, InterruptedError]) as _sleep,
        contextlib.suppress(InterruptedError),
    ):
        main()

    # Two iterations complete before the second sleep raises.
    assert _dispatch.call_count == 2
    _dispatch.assert_has_calls(
        [call("/usr/bin/juju-run", "mysql/0", "/charm"), call("/usr/bin/juju-run", "mysql/0", "/charm")]
    )
    assert _sleep.call_count == 2
    _sleep.assert_has_calls([call(120), call(120)])


def test_main_parses_run_command_unit_and_charm_directory_arguments():
    captured = {}

    def _fake_dispatch(run_command, unit, charm_directory):
        captured["run_command"] = run_command
        captured["unit"] = unit
        captured["charm_directory"] = charm_directory
        raise InterruptedError

    argv = ["self_healing_dispatcher.py", "/usr/bin/juju-run", "my-unit/1", "/some/charm/dir"]

    with (
        patch("sys.argv", argv),
        patch("scripts.self_healing_dispatcher.dispatch", side_effect=_fake_dispatch),
        patch("time.sleep"),
        contextlib.suppress(InterruptedError),
    ):
        main()

    assert captured == {
        "run_command": "/usr/bin/juju-run",
        "unit": "my-unit/1",
        "charm_directory": "/some/charm/dir",
    }
