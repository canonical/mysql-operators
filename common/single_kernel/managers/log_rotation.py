# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import signal
import subprocess

from ..state import LogRotationState
from ..workload import BaseSystem

logger = logging.getLogger(__name__)


class LogRotationManager:
    """Class to deal with the log-rotation process."""

    def __init__(self, state: LogRotationState, system: BaseSystem):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

    def _check_process(self) -> bool:
        """Check whether the process exists."""
        manager_pid = self._state.get_manager_pid()
        if not manager_pid:
            return False

        try:
            subprocess.run(["ps", "--pid", str(manager_pid)], check=True)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def get_synced_flag(self) -> bool | None:
        """Get the synchronization flag."""
        self._state.get_sync_flag()

    def set_synced_flag(self, flag: bool) -> None:
        """Set the synchronization flag."""
        self._state.set_sync_flag(flag)

    def delete_synced_flag(self) -> None:
        """Delete the synchronization flag."""
        self._state.delete_sync_flag()

    def start_process(self, unit_name: str, operator_path: str) -> None:
        """Start the process."""
        if self._check_process():
            return

        # We need to trick Juju into thinking that we are not running
        # in a hook context, as Juju will disallow use of juju-run.
        pruned_env = os.environ.copy()
        pruned_env.pop("JUJU_CONTEXT_ID")

        process = subprocess.Popen(
            ["/usr/bin/python3", "scripts/log_rotate_dispatcher.py", unit_name, operator_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=pruned_env,
        )

        logger.info(f"Started the log-rotate manager with PID {process.pid}")
        self._state.set_manager_pid(process.pid)

    def stop_process(self) -> None:
        """Stop the process."""
        manager_pid = self._state.get_manager_pid()
        if not manager_pid:
            return

        try:
            os.kill(manager_pid, signal.SIGTERM)
        except OSError:
            logger.error(f"Failed to stop the log-rotate manager with PID {manager_pid}")
        else:
            logger.info(f"Stopped the log-rotate manager with PID {manager_pid}")
            self._state.delete_manager_pid()
