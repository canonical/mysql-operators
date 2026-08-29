# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import sys
import unittest
from unittest.mock import patch

# The self_healing_dispatcher script lives in kubernetes/scripts/, which is not
# on PYTHONPATH. Add it so the module can be imported directly.
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.append(os.path.abspath(_SCRIPTS_DIR))

import self_healing_dispatcher  # noqa: E402


class TestDispatch(unittest.TestCase):
    """Tests for the dispatch function."""

    @patch("self_healing_dispatcher.subprocess.run")
    def test_dispatch_invokes_juju_exec_with_expected_arguments(self, mock_run):
        """Dispatch calls /usr/bin/juju-exec with the heal_mysql_cluster hook path."""
        self_healing_dispatcher.dispatch("mysql-k8s/0", "/charm/dir")

        mock_run.assert_called_once_with(
            [
                "/usr/bin/juju-exec",
                "-u",
                "mysql-k8s/0",
                "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster",
                "/charm/dir/dispatch",
            ],
            check=True,
        )

    @patch("self_healing_dispatcher.subprocess.run")
    def test_dispatch_propagates_subprocess_error(self, mock_run):
        """Dispatch raises when subprocess.run fails (check=True)."""
        import subprocess as _subprocess

        mock_run.side_effect = _subprocess.CalledProcessError(1, ["juju-exec"])

        with self.assertRaises(_subprocess.CalledProcessError):
            self_healing_dispatcher.dispatch("mysql/0", "/charm")


class TestMain(unittest.TestCase):
    """Tests for the main() entry point."""

    @patch("self_healing_dispatcher.dispatch")
    @patch("self_healing_dispatcher.time.sleep")
    def test_main_dispatches_and_sleeps_in_loop(self, mock_sleep, mock_dispatch):
        """main() dispatches the self-healing event every 120 seconds."""
        # Stop the loop after the second iteration
        mock_sleep.side_effect = [None, StopIteration]

        with (
            patch("sys.argv", ["script", "mysql-k8s/0", "/charm"]),
            self.assertRaises(StopIteration),
        ):
            self_healing_dispatcher.main()

        self.assertEqual(mock_dispatch.call_count, 2)
        mock_dispatch.assert_called_with("mysql-k8s/0", "/charm")
        mock_sleep.assert_called_with(120)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("self_healing_dispatcher.dispatch")
    @patch("self_healing_dispatcher.time.sleep")
    def test_main_parses_arguments_via_argparse(self, mock_sleep, mock_dispatch):
        """main() uses argparse to parse unit and charm_directory positional args."""
        mock_sleep.side_effect = StopIteration

        with (
            patch("sys.argv", ["script", "myapp/2", "/opt/charm"]),
            self.assertRaises(StopIteration),
        ):
            self_healing_dispatcher.main()

        mock_dispatch.assert_called_once_with("myapp/2", "/opt/charm")
