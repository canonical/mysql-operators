# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju

from ...helpers_ha import (
    CHARM_METADATA,
    delete_k8s_pod,
    get_mysql_primary_unit,
    wait_for_apps_status,
    wait_for_unit_message,
)

MYSQL_APP_NAME = "mysql-k8s"
MINUTE_SECS = 60


def test_build_and_deploy(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@26.04",
        config={"profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        storage={"data": "500M", "archive": "250M", "logs": "250M", "temp": "250M"},
        num_units=3,
        trust=True,
    )

    logging.info("Wait for the first unit to be configured as primary")
    juju.wait(
        ready=lambda status: any((
            *(
                wait_for_unit_message(MYSQL_APP_NAME, unit_name, "Primary")(status)
                for unit_name in status.get_units(MYSQL_APP_NAME)
            ),
        )),
        error=jubilant.any_blocked,
        timeout=20 * MINUTE_SECS,
    )


def test_crash_during_cluster_setup_and_recover(juju: Juju) -> None:
    mysql_primary = get_mysql_primary_unit(juju, MYSQL_APP_NAME)

    logging.info("Deleting pod")
    delete_k8s_pod(juju, mysql_primary)

    logging.info("Waiting until cluster is fully active")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )
