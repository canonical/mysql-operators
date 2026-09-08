# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import argparse
import subprocess
import time


def _dispatch_event(operator_unit: str, operator_path: str) -> None:
    """Dispatch the `rotate-mysql-logs` event."""
    dispatch_path = f"JUJU_DISPATCH_PATH=hooks/rotate_mysql_logs"
    operator_path = f"{operator_path}/dispatch"

    subprocess.run(
        ["/usr/bin/juju-exec", "--unit", operator_unit, dispatch_path, operator_path],
        check=True,
    )


def _sleep_minute(start_time: float) -> None:
    """Sleep until the top of the minute."""
    elapsed_secs = time.monotonic() - start_time
    rounded_secs = 60.0 - (elapsed_secs % 60.0)

    time.sleep(rounded_secs)


def main():
    """Main watch and dispatch loop.

    Wakes up at the top of the minute every 60s and dispatch an event.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("operator_unit", help="name of the operator unit")
    parser.add_argument("operator_path", help="path to the operator directory")
    arguments = parser.parse_args()

    start_time = time.monotonic()

    while True:
        _sleep_minute(start_time)
        _dispatch_event(arguments.operator_unit, arguments.operator_path)


if __name__ == "__main__":
    main()
