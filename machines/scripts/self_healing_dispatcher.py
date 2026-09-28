# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Dispatch event for self-healing."""

import logging
import subprocess
import sys
import time

logger = logging.getLogger(__name__)


def dispatch(run_command, unit, charm_directory):
    """Use the juju-run command to dispatch :class:`SelfHealingMySQLEvent`."""
    dispatch_sub_command = "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster {}/dispatch"
    subprocess.run([run_command, "-u", unit, dispatch_sub_command.format(charm_directory)])  # noqa: S603


def main():
    """Main watch and dispatch loop.

    Dispatch a self-healing event every 120 seconds.
    """
    run_command, unit, charm_directory = sys.argv[1:]

    while True:
        dispatch(run_command, unit, charm_directory)
        time.sleep(120)


if __name__ == "__main__":
    main()
