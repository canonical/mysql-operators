# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Self healing event dispatcher."""

import argparse
import subprocess
import time


def dispatch(unit: str, charm_directory: str):
    """Dispatch custom event to flush mysql logs."""
    dispatch_sub_command = f"{charm_directory}/dispatch"

    subprocess.run(  # noqa: S603
        [
            "/usr/bin/juju-exec",
            "-u",
            unit,
            "JUJU_DISPATCH_PATH=hooks/heal_mysql_cluster",
            dispatch_sub_command,
        ],
        check=True,
    )


def main():
    """Main watch and dispatch loop.

    Roughly every 120s, dispatch the custom self_heal_mysql event.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("unit", help="name of unit")
    parser.add_argument("charm_directory", help="base directory of the charm")
    arguments = parser.parse_args()

    while True:
        dispatch(arguments.unit, arguments.charm_directory)
        time.sleep(120)


if __name__ == "__main__":
    main()
