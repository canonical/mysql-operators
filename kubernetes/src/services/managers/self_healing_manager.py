# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Self healing manager."""

import logging
import os
import signal
import subprocess
import typing

from ops.framework import Object

if typing.TYPE_CHECKING:
    from charm import MySQLOperatorCharm

logger = logging.getLogger(__name__)


class SelfHealingManager(Object):
    """Manages self-healing for the charm.

    Dispatches a custom event every 60s to self-heal the mysql cluster.
    """

    def __init__(self, charm: "MySQLOperatorCharm"):
        super().__init__(charm, "self-healing-manager")
        self.charm = charm

    def start_self_healing_manager(self):
        """Forks off a process that periodically dispatch a custom event to self-heal."""
        if not self.charm.peers or not self.charm.unit_initialized():
            return

        if "self-healing-manager-pid" in self.charm.unit_peer_data:
            pid = int(self.charm.unit_peer_data["self-healing-manager-pid"])
            try:
                os.kill(pid, 0)  # Check if the process exists
                return
            except OSError:
                pass

        logger.info("Starting the self-healing-process")

        # We need to trick Juju into thinking that we are not running
        # in a hook context, as Juju will disallow use of juju-run.
        new_env = os.environ.copy()
        new_env.pop("JUJU_CONTEXT_ID", None)

        # Use Popen instead of run as the self-healing dispatcher is a long running
        # process that shouldn't block the event handler
        process = subprocess.Popen(  # noqa: S603
            [
                "/usr/bin/python3",
                "scripts/self_healing_dispatcher.py",
                self.charm.unit.name,
                self.charm.charm_dir,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=new_env,
        )

        self.charm.unit_peer_data.update({"self-healing-manager-pid": str(process.pid)})
        logger.info(f"Started self-healing process with PID {process.pid}")

    def stop_self_healing_manager(self):
        """Stop the self-healing manager process."""
        if self.charm.peers is None or "self-healing-manager-pid" not in self.charm.unit_peer_data:
            return

        self_healing_manager_pid = int(self.charm.unit_peer_data["self-healing-manager-pid"])

        try:
            os.kill(self_healing_manager_pid, signal.SIGTERM)
            logger.info(f"Stopped self-healing process with PID {self_healing_manager_pid}")
            del self.charm.unit_peer_data["self-healing-manager-pid"]
        except OSError:
            pass
