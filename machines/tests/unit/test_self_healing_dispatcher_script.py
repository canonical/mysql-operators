# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import sys
import unittest
from unittest.mock import patch

# The self_healing_dispatcher script lives in machines/scripts/, which is not on
# PYTHONPATH. Add it so the module can be imported directly.
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.append(os.path.abspath(_SCRIPTS_DIR))

import self_healing_dispatcher  # noqa: E402


class TestDispatch(unittest.TestCase):
    """Tests for the dispatch function."""

    @patch("self_healing_dispatcher.subprocess.run")
    def test_dispatch_invokes_subprocess_with_expected_arguments(self, mock_run):
        """Dispatch builds the juju-run command and runs it via subprocess."""
        self_healing_dispatcher.dispatch("juju-run", "mysql/0", "/charm/dir")

        expected_sub_command = "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster /charm/dir/dispatch"
        mock_run.assert_called_once_with(["juju-run", "-u", "mysql/0", expected_sub_command])


class TestMain(unittest.TestCase):
    """Tests for the main() entry point."""

    @patch("self_healing_dispatcher.dispatch")
    @patch("self_healing_dispatcher.time.sleep")
    def test_main_dispatches_and_sleeps_in_loop(self, mock_sleep, mock_dispatch):
        """main() dispatches the self-healing event every 120 seconds."""
        # Stop the loop after the second iteration
        mock_sleep.side_effect = [None, StopIteration]

        with (
            patch(
                "self_healing_dispatcher.sys.argv",
                ["script", "juju-run", "mysql/0", "/charm"],
            ),
            self.assertRaises(StopIteration),
        ):
            self_healing_dispatcher.main()

        # dispatch called once per loop iteration (2 iterations before stopping)
        self.assertEqual(mock_dispatch.call_count, 2)
        mock_dispatch.assert_called_with("juju-run", "mysql/0", "/charm")
        mock_sleep.assert_called_with(120)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("self_healing_dispatcher.dispatch")
    @patch("self_healing_dispatcher.time.sleep")
    def test_main_passes_argv_arguments_to_dispatch(self, mock_sleep, mock_dispatch):
        """main() forwards run_command, unit, and charm_directory from sys.argv."""
        mock_sleep.side_effect = StopIteration

        with (
            patch(
                "self_healing_dispatcher.sys.argv",
                ["script", "juju-exec", "myapp/2", "/opt/charm"],
            ),
            self.assertRaises(StopIteration),
        ):
            self_healing_dispatcher.main()

        mock_dispatch.assert_called_once_with("juju-exec", "myapp/2", "/opt/charm")
