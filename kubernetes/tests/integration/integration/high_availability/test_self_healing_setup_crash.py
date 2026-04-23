# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import jubilant_backports
from jubilant_backports import Juju

from ...helpers_ha import (
    CHARM_METADATA,
    delete_k8s_pod,
    get_mysql_primary_unit,
    load_mysql_test_data,
    update_interval,
    wait_for_apps_status,
    wait_for_unit_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MINUTE_SECS = 60


def test_deploy_single_unit_cluster(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@22.04",
        config={"profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=1,
        trust=True,
    )

    logging.info("Wait for applications to become active")
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
        error=jubilant_backports.any_blocked,
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_crash_during_cluster_setup(juju: Juju, charm: str) -> None:
    """Test primary crash during startup.

    It must recover/end setup when the primary got offline.
    """
    mysql_primary = get_mysql_primary_unit(juju, MYSQL_APP_NAME)

    logging.info("Scaling to 3 units")
    juju.add_unit(MYSQL_APP_NAME, num_units=2)
    # NOTE: This is prone to race conditions:
    # if the units clear the "waiting" phase too quickly,
    # this status function will never activate
    juju.wait(
        ready=lambda status: any((
            *(
                wait_for_unit_status(MYSQL_APP_NAME, unit_name, "waiting")(status)
                for unit_name in status.get_units(MYSQL_APP_NAME)
            ),
        )),
        error=jubilant_backports.any_blocked,
        timeout=20 * MINUTE_SECS,
        successes=1,
    )

    logging.info("Deleting pod")
    delete_k8s_pod(juju, mysql_primary)

    with update_interval(juju, "60s"):
        logging.info("Waiting until cluster is fully active")
        juju.wait(
            ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
            timeout=20 * MINUTE_SECS,
        )
