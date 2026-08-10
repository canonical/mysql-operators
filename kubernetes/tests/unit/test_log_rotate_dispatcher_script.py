# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

# The log_rotate_dispatcher script lives in kubernetes/scripts/, which is not
# on PYTHONPATH. Add it so the module can be imported directly.
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.append(os.path.abspath(_SCRIPTS_DIR))

import log_rotate_dispatcher  # noqa: E402


class TestDispatch(unittest.TestCase):
    """Tests for the dispatch function."""

    @patch("log_rotate_dispatcher.subprocess.run")
    def test_dispatch_invokes_juju_exec_with_expected_arguments(self, mock_run):
        """Dispatch calls /usr/bin/juju-exec with the rotate_mysql_logs hook path."""
        log_rotate_dispatcher.dispatch("mysql-k8s/0", "/charm/dir")

        mock_run.assert_called_once_with(
            [
                "/usr/bin/juju-exec",
                "-u",
                "mysql-k8s/0",
                "JUJU_DISPATCH_PATH=hooks/rotate_mysql_logs",
                "/charm/dir/dispatch",
            ],
            check=True,
        )

    @patch("log_rotate_dispatcher.subprocess.run")
    def test_dispatch_propagates_subprocess_error(self, mock_run):
        """Dispatch raises when subprocess.run fails (check=True)."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["juju-exec"])

        with self.assertRaises(subprocess.CalledProcessError):
            log_rotate_dispatcher.dispatch("mysql/0", "/charm")


class TestMain(unittest.TestCase):
    """Tests for the main() entry point."""

    @patch("log_rotate_dispatcher.dispatch")
    @patch("log_rotate_dispatcher.time.sleep")
    @patch("log_rotate_dispatcher.time.monotonic")
    @patch("log_rotate_dispatcher.time.time")
    def test_main_initial_wait_and_loop_dispatch(
        self, mock_time, mock_monotonic, mock_sleep, mock_dispatch
    ):
        """main() waits till top of minute, then dispatches every 60s."""
        # Initial time.time() for the top-of-minute wait
        mock_time.return_value = 100.0
        # monotonic: start_time=1000, then after dispatch still within same minute
        mock_monotonic.side_effect = [1000.0, 1010.0, StopIteration]
        # Stop the loop on the third sleep call (the in-loop sleep of 2nd iteration)
        mock_sleep.side_effect = [None, None, StopIteration]

        with (
            patch("sys.argv", ["script", "mysql-k8s/0", "/charm"]),
            self.assertRaises(StopIteration),
        ):
            log_rotate_dispatcher.main()

        # First sleep: wait until top of the minute
        # 60 - (100 % 60) = 60 - 40 = 20
        self.assertEqual(mock_sleep.call_args_list[0].args[0], 20)
        # dispatch called once per loop iteration (2 iterations before stopping)
        self.assertEqual(mock_dispatch.call_count, 2)
        mock_dispatch.assert_called_with("mysql-k8s/0", "/charm")

    @patch("log_rotate_dispatcher.dispatch")
    @patch("log_rotate_dispatcher.time.sleep")
    @patch("log_rotate_dispatcher.time.monotonic")
    @patch("log_rotate_dispatcher.time.time")
    def test_main_parses_arguments_via_argparse(
        self, mock_time, mock_monotonic, mock_sleep, mock_dispatch
    ):
        """main() uses argparse to parse unit and charm_directory positional args."""
        mock_time.return_value = 0.0
        mock_monotonic.side_effect = [0.0, StopIteration]
        mock_sleep.side_effect = [None, StopIteration]

        with (
            patch("sys.argv", ["script", "myapp/2", "/opt/charm"]),
            self.assertRaises(StopIteration),
        ):
            log_rotate_dispatcher.main()

        mock_dispatch.assert_called_once_with("myapp/2", "/opt/charm")

    @patch("log_rotate_dispatcher.dispatch")
    @patch("log_rotate_dispatcher.time.sleep")
    @patch("log_rotate_dispatcher.time.monotonic")
    @patch("log_rotate_dispatcher.time.time")
    def test_main_initial_wait_at_top_of_minute(
        self, mock_time, mock_monotonic, mock_sleep, mock_dispatch
    ):
        """main() waits the correct remainder when already near top of minute."""
        # time.time() = 59.5 -> initial wait = 60 - (59.5 % 60) = 0.5
        mock_time.return_value = 59.5
        mock_monotonic.side_effect = [0.0, StopIteration]
        mock_sleep.side_effect = [None, StopIteration]

        with (
            patch("sys.argv", ["script", "mysql/0", "/charm"]),
            self.assertRaises(StopIteration),
        ):
            log_rotate_dispatcher.main()

        # Initial wait should be 0.5 seconds
        self.assertAlmostEqual(mock_sleep.call_args_list[0].args[0], 0.5)

    @patch("log_rotate_dispatcher.dispatch")
    @patch("log_rotate_dispatcher.time.sleep")
    @patch("log_rotate_dispatcher.time.monotonic")
    @patch("log_rotate_dispatcher.time.time")
    def test_main_loop_sleep_calculated_from_monotonic(
        self, mock_time, mock_monotonic, mock_sleep, mock_dispatch
    ):
        """main() computes in-loop sleep from monotonic elapsed time."""
        mock_time.return_value = 0.0
        # start_time=0, after dispatch monotonic=45 -> in-loop sleep = 60 - (45 % 60) = 15
        mock_monotonic.side_effect = [0.0, 45.0, StopIteration]
        mock_sleep.side_effect = [None, None, StopIteration]

        with (
            patch("sys.argv", ["script", "mysql/0", "/charm"]),
            self.assertRaises(StopIteration),
        ):
            log_rotate_dispatcher.main()

        # In-loop sleep (second sleep call) should be 15 seconds
        self.assertAlmostEqual(mock_sleep.call_args_list[1].args[0], 15.0)


if __name__ == "__main__":
    unittest.main()
