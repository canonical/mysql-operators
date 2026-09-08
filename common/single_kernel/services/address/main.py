# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import argparse
import logging
import socket
import subprocess
import time

logger = logging.getLogger(__name__)


def _dispatch_event(operator_unit: str, operator_path: str) -> None:
    """Dispatch the `ip-address-change` event."""
    dispatch_path = f"JUJU_DISPATCH_PATH=hooks/rotate_mysql_logs"
    operator_path = f"{operator_path}/dispatch"

    subprocess.run(
        ["/usr/bin/juju-exec", "--unit", operator_unit, dispatch_path, operator_path],
        check=True,
    )


def _resolve_local_address() -> str:
    """Resolve the local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)

    try:
        s.connect(("10.10.10.10", 1))
        address = s.getsockname()[0]
    except Exception as e:
        logger.exception(f"Failed to resolve local address: {e}")
        address = "127.0.0.1"

    return address


def main():
    """Main watch and dispatch loop.

    Determine the host IP address every 30s and dispatch an event if it changes.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("operator_unit", help="name of the operator unit")
    parser.add_argument("operator_path", help="path to the operator directory")
    arguments = parser.parse_args()

    previous_address = None

    while True:
        address = _resolve_local_address()

        if not previous_address:
            logger.info(f"Setting initial address to {address}")
            previous_address = address
        elif previous_address != address:
            logger.info(f"Detected address change to {address}")
            previous_address = address
            _dispatch_event(arguments.operator_unit, arguments.operator_path)

        time.sleep(30)


if __name__ == "__main__":
    main()
