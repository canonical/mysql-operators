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

    @abstractmethod
    def get_process_id(self) -> int | None:
        """Get the service process ID."""
        raise NotImplementedError()

    @abstractmethod
    def set_process_id(self, pid: int) -> None:
        """Set the service process ID."""
        raise NotImplementedError()

    @abstractmethod
    def delete_process_id(self) -> None:
        """Delete the service process ID."""
        raise NotImplementedError()

    @property
    def running(self) -> bool:
        """Check whether the service is running."""
        process_id = self.get_process_id()
        if not process_id:
            return False

        try:
            subprocess.run(["ps", "--pid", str(process_id)], check=True)
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
        self.set_process_id(process.pid)

    def stop(self) -> None:
        """Stop the service."""
        process_id = self.get_process_id()
        if not process_id:
            return

        try:
            os.kill(process_id, signal.SIGTERM)
        except OSError:
            logger.error(f"Failed to stop the {self.name} service with PID {process_id}")
        else:
            logger.info(f"Stopped the {self.name} service with PID {process_id}")
            self.delete_process_id()
