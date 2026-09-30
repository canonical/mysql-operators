# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import contextlib
from unittest.mock import call, patch

from scripts.log_rotate_dispatcher import dispatch, main


def test_dispatch_invokes_juju_exec_with_rotate_event():
    with patch("subprocess.run") as _run:
        dispatch("mysql-k8s/0", "/charm")

    _run.assert_called_once_with(
        [
            "/usr/bin/juju-exec",
            "-u",
            "mysql-k8s/0",
            "JUJU_DISPATCH_PATH=hooks/rotate_mysql_logs",
            "/charm/dispatch",
        ],
        check=True,
    )


def test_main_loops_dispatching_until_interrupted():
    argv = ["log_rotate_dispatcher.py", "mysql-k8s/0", "/charm"]

    with (
        patch("sys.argv", argv),
        patch("scripts.log_rotate_dispatcher.dispatch") as _dispatch,
        patch("time.sleep", side_effect=[None, InterruptedError]) as _sleep,
        patch("time.time", return_value=0.0) as _time,
        patch("time.monotonic", return_value=0.0) as _monotonic,
        contextlib.suppress(InterruptedError),
    ):
        main()

    # First sleep aligns to the top of the minute; subsequent sleeps pace the loop.
    assert _sleep.call_count == 2
    _sleep.assert_has_calls([call(60 - (0.0 % 60)), call(60.0 - ((0.0 - 0.0) % 60.0))])
    # dispatch is invoked once per loop iteration before sleep interrupts.
    _dispatch.assert_called_once_with("mysql-k8s/0", "/charm")
    _time.assert_called_once_with()
    # monotonic is called once for start_time and once inside the pacing expression.
    assert _monotonic.call_count == 2


def test_main_parses_unit_and_charm_directory_arguments():
    captured = {}

    def _fake_dispatch(unit, charm_directory):
        captured["unit"] = unit
        captured["charm_directory"] = charm_directory
        raise InterruptedError

    argv = ["log_rotate_dispatcher.py", "my-unit/1", "/some/charm/dir"]

    with (
        patch("sys.argv", argv),
        patch("scripts.log_rotate_dispatcher.dispatch", side_effect=_fake_dispatch),
        patch("time.sleep"),
        patch("time.time", return_value=0.0),
        patch("time.monotonic", return_value=0.0),
        contextlib.suppress(InterruptedError),
    ):
        main()

    assert captured == {"unit": "my-unit/1", "charm_directory": "/some/charm/dir"}


def test_main_sleeps_until_top_of_minute_before_first_dispatch():
    argv = ["log_rotate_dispatcher.py", "mysql-k8s/0", "/charm"]

    with (
        patch("sys.argv", argv),
        patch("scripts.log_rotate_dispatcher.dispatch", side_effect=InterruptedError),
        patch("time.sleep") as _sleep,
        # 30 seconds into the minute -> must wait 30s to reach the top.
        patch("time.time", return_value=30.0),
        patch("time.monotonic", return_value=0.0),
        contextlib.suppress(InterruptedError),
    ):
        main()

    # First sleep aligns to the top of the minute (60 - 30 = 30s), then dispatch
    # raises InterruptedError before the pacing sleep is reached.
    _sleep.assert_called_once_with(30.0)
