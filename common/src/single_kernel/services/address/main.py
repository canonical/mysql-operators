# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import argparse
import logging
import socket
import subprocess
import time

logger = logging.getLogger(__name__)


def _dispatch_event(operator_unit: str, operator_path: str) -> bool:
    """Dispatch the `address-changed` event."""
    dispatch_path = f"JUJU_DISPATCH_PATH=hooks/address_changed"
    operator_path = f"{operator_path}/dispatch"

    process = subprocess.run(
        ["/usr/bin/juju-exec", "-u", operator_unit, dispatch_path, operator_path],
        check=False,
    )

    return process.returncode == 0


def _resolve_local_address() -> str:
    """Resolve the local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)

    try:
        s.connect(("10.10.10.10", 1))
        address = s.getsockname()[0]
    except Exception as e:
        logger.error(f"Failed to resolve local address: {e}")
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

    previous_address = _resolve_local_address()

    while True:
        current_address = _resolve_local_address()
        if current_address == previous_address:
            time.sleep(30)
            continue

        logger.info(f"Detected address change to {current_address}")

        if _dispatch_event(arguments.operator_unit, arguments.operator_path):
            previous_address = current_address
            time.sleep(30)
        else:
            time.sleep(30)


if __name__ == "__main__":
    main()
