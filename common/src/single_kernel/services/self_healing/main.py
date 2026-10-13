# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import argparse
import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def _dispatch_event(operator_unit: str, operator_path: str) -> None:
    """Dispatch the `heal-mysql-cluster` event."""
    dispatch_path = "JUJU_DISPATCH_PATH=hooks/self_healing"
    operator_path = f"{operator_path}/dispatch"

    try:
        subprocess.run(
            ["/usr/bin/juju-exec", "-u", operator_unit, dispatch_path, operator_path],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        # A failed dispatch must not kill the self-healing loop, as it is
        # precisely when the unit is unhealthy that healing is most needed.
        logger.error(f"Failed to dispatch the self-healing event: {e}")


def main():
    """Main watch and dispatch loop.

    Wakes up every 120s and dispatch an event.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("operator_unit", help="name of the operator unit")
    parser.add_argument("operator_path", help="path to the operator directory")
    arguments = parser.parse_args()

    while True:
        _dispatch_event(arguments.operator_unit, arguments.operator_path)
        time.sleep(120)


if __name__ == "__main__":
    main()
