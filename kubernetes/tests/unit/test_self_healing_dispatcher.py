# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import contextlib
from unittest.mock import call, patch

from scripts.self_healing_dispatcher import dispatch, main


def test_dispatch_prefers_juju_exec_over_juju_run():
    with (
        patch("scripts.self_healing_dispatcher.shutil.which", side_effect=["/usr/bin/juju-run", "/usr/bin/juju-exec"]) as _which,
        patch("subprocess.run") as _run,
    ):
        dispatch("mysql-k8s/0", "/charm")

    _which.assert_any_call("juju-run")
    _which.assert_any_call("juju-exec")
    _run.assert_called_once_with(
        [
            "/usr/bin/juju-exec",
            "-u",
            "mysql-k8s/0",
            "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster",
            "/charm/dispatch",
        ],
        check=True,
    )


def test_dispatch_falls_back_to_juju_run_when_exec_absent():
    with (
        patch("scripts.self_healing_dispatcher.shutil.which", side_effect=["/usr/bin/juju-run", None]),
        patch("subprocess.run") as _run,
    ):
        dispatch("mysql-k8s/0", "/charm")

    _run.assert_called_once_with(
        [
            "/usr/bin/juju-run",
            "-u",
            "mysql-k8s/0",
            "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster",
            "/charm/dispatch",
        ],
        check=True,
    )


def test_dispatch_uses_empty_string_when_no_juju_binary_found():
    with (
        patch("scripts.self_healing_dispatcher.shutil.which", side_effect=[None, None]),
        patch("subprocess.run") as _run,
    ):
        dispatch("mysql-k8s/0", "/charm")

    _run.assert_called_once_with(
        [
            "",
            "-u",
            "mysql-k8s/0",
            "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster",
            "/charm/dispatch",
        ],
        check=True,
    )


def test_main_loops_dispatching_every_120s_until_interrupted():
    argv = ["self_healing_dispatcher.py", "mysql-k8s/0", "/charm"]

    with (
        patch("sys.argv", argv),
        patch("scripts.self_healing_dispatcher.dispatch") as _dispatch,
        patch("time.sleep", side_effect=[None, InterruptedError]) as _sleep,
        contextlib.suppress(InterruptedError),
    ):
        main()

    # Two iterations complete before the second sleep raises.
    assert _dispatch.call_count == 2
    _dispatch.assert_has_calls([call("mysql-k8s/0", "/charm"), call("mysql-k8s/0", "/charm")])
    assert _sleep.call_count == 2
    _sleep.assert_has_calls([call(120), call(120)])


def test_main_parses_unit_and_charm_directory_arguments():
    captured = {}

    def _fake_dispatch(unit, charm_directory):
        captured["unit"] = unit
        captured["charm_directory"] = charm_directory
        raise InterruptedError

    argv = ["self_healing_dispatcher.py", "my-unit/1", "/some/charm/dir"]

    with (
        patch("sys.argv", argv),
        patch("scripts.self_healing_dispatcher.dispatch", side_effect=_fake_dispatch),
        patch("time.sleep"),
        contextlib.suppress(InterruptedError),
    ):
        main()

    assert captured == {"unit": "my-unit/1", "charm_directory": "/some/charm/dir"}
