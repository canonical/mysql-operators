# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from time import sleep

import jubilant
from jubilant import Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    get_app_name,
    get_app_units,
    get_mysql_primary_unit,
    load_mysql_test_data,
    start_mysqld_service,
    stop_mysqld_service,
    update_interval,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


def test_deploy_highly_available_cluster(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@24.04",
        config={"profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=3,
        trust=True,
    )
    constraints = {"arch": architecture.architecture}
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@24.04",
        channel="latest/edge",
        config={"sleep_interval": 300},
        num_units=1,
        constraints=constraints,
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
    app_name = get_app_name(juju, MYSQL_APP_NAME)
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
    app_name = get_app_name(juju, MYSQL_APP_NAME)
    assert app_name, "MySQL application not found in the cluster"

    app_units = set(get_app_units(juju, app_name))
    assert len(app_units) > 1, "Not enough units to perform a switchover"

    primary_unit = get_mysql_primary_unit(juju, app_name)
    assert primary_unit, "No primary unit found in the cluster"
    logging.info(f"Current primary unit: {primary_unit}")

    non_primary_units = app_units - {primary_unit}

    unit_to_promote = non_primary_units.pop()

    logging.info(f"Unit selected for promotion: {unit_to_promote}")

    logging.info("Simulate quorum loss")
    units_to_stop = [non_primary_units.pop(), primary_unit]

    # ensure no update-status is triggered
    with update_interval(juju, "30m"):
        # Stop mysqld via Pebble on a majority of units:
        # `pebble stop` is honoured until an explicit `pebble start`,
        # so the survivor stays in NO_QUORUM until we restart mysqld below
        for unit in units_to_stop:
            stop_mysqld_service(juju, unit)
        # allow time to cluster settled in no_quorum
        sleep(10)
        logging.info("Attempting to promote a unit to primary after quorum loss...")
        juju.run(
            unit=unit_to_promote,
            action="promote-to-primary",
            params={"scope": "unit", "force": True},
            wait=600,
        )
        # Bring mysqld back on the stopped units
        # so they can rejoin the new primary;
        # otherwise the cluster never reaches all-active
        for unit in units_to_stop:
            start_mysqld_service(juju, unit)

    with update_interval(juju, "15s"):
        logging.info("Waiting for all units to become active after switchover...")
        juju.wait(
            ready=jubilant.all_active,
            timeout=10 * MINUTE_SECS,
            delay=5,
        )

    assert get_mysql_primary_unit(juju, app_name) == unit_to_promote, "Failover failed"
