# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from time import sleep

import jubilant
from jubilant import Juju

from ...helpers_ha import (
    get_app_name,
    get_app_units,
    get_mysql_primary_unit,
    load_mysql_test_data,
    stop_unit_machine,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


def test_deploy_highly_available_cluster(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@26.04",
        config={"profile": "testing"},
        num_units=3,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@26.04",
        channel="latest/edge",
        config={"sleep_interval": 500},
        num_units=1,
    )

    juju.integrate(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    logging.info("Wait for applications to become active")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_cluster_switchover(juju: Juju) -> None:
    """Test that the primary node can be switched over."""
    logging.info("Testing cluster switchover...")
    app_name = get_app_name(juju, "mysql")
    assert app_name, "MySQL application not found in the cluster"

    app_units = set(get_app_units(juju, app_name))
    assert len(app_units) > 1, "Not enough units to perform a switchover"

    primary_unit = get_mysql_primary_unit(juju, app_name)
    assert primary_unit, "No primary unit found in the cluster"
    logging.info(f"Current primary unit: {primary_unit}")

    logging.info("Selecting a new primary unit for switchover...")
    app_units.discard(primary_unit)
    new_primary_unit = app_units.pop()
    logging.info(f"New primary unit selected: {new_primary_unit}")

    juju.run(
        unit=new_primary_unit,
        action="promote-to-primary",
        params={"scope": "unit"},
    )

    assert get_mysql_primary_unit(juju, app_name) == new_primary_unit, "Switchover failed"


def test_cluster_failover_after_majority_loss(juju: Juju) -> None:
    """Test the promote-to-primary command after losing the majority of nodes, with force flag."""
    app_name = get_app_name(juju, "mysql")
    assert app_name, "MySQL application not found in the cluster"

    app_units = set(get_app_units(juju, app_name))
    assert len(app_units) > 1, "Not enough units to perform a switchover"

    primary_unit = get_mysql_primary_unit(juju, app_name)
    assert primary_unit, "No primary unit found in the cluster"
    logging.info(f"Current primary unit: {primary_unit}")

    non_primary_units = app_units - {primary_unit}

    unit_to_promote = non_primary_units.pop()
    logging.info(f"Unit selected for promotion: {unit_to_promote}")

    logging.info("Kill all but one unit to simulate majority loss...")
    for unit_name in [non_primary_units.pop(), primary_unit]:
        stop_unit_machine(juju, app_name, unit_name)

    # allow time to cluster settled in no_quorum
    sleep(10)
    logging.info("Attempting to promote a unit to primary after quorum loss...")
    juju.run(
        unit=unit_to_promote,
        action="promote-to-primary",
        params={"scope": "unit", "force": True},
        wait=600,
    )

    assert get_mysql_primary_unit(juju, app_name, unit_to_promote) == unit_to_promote, (
        "Failover failed"
    )
