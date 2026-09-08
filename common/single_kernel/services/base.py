# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import signal
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseOperatorService(ABC):
    """Abstract class to deal with the operator services."""

    name: str

    @property
    @abstractmethod
    def state(self):
        """Return the relation state."""
        raise NotImplementedError()

    @property
    def running(self) -> bool:
        """Check whether the service is running."""
        manager_pid = self.state.get_manager_pid()
        if not manager_pid:
            return False

        try:
            subprocess.run(["ps", "--pid", str(manager_pid)], check=True)
        except subprocess.CalledProcessError:
            return False
        else:
            return True

    def start(self, unit_name: str, operator_path: str) -> None:
        """Start the service."""
        if self.running:
            return

        # The entrypoint script needs to be place alongside the service
        entrypoint_path = Path(__file__).parent.absolute() / "main.py"

        # We need to trick Juju into thinking that we are not running
        # in a hook context, as Juju will disallow use of juju-run.
        pruned_env = os.environ.copy()
        pruned_env.pop("JUJU_CONTEXT_ID")

        process = subprocess.Popen(
            ["/usr/bin/python3", entrypoint_path, unit_name, operator_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=pruned_env,
        )

        logger.info(f"Started the {self.name} service with PID {process.pid}")
        self.state.set_manager_pid(process.pid)

    def stop(self) -> None:
        """Stop the service."""
        manager_pid = self.state.get_manager_pid()
        if not manager_pid:
            return

        try:
            os.kill(manager_pid, signal.SIGTERM)
        except OSError:
            logger.error(f"Failed to stop the {self.name} service with PID {manager_pid}")
        else:
            logger.info(f"Stopped the {self.name} service with PID {manager_pid}")
            self.state.delete_manager_pid()
