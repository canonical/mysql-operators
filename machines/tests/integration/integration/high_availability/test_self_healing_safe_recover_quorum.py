# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import jubilant_backports
from jubilant_backports import Juju

from ...helpers_ha import (
    check_mysql_units_writes_increment,
    get_app_name,
    get_app_units,
    get_mysql_primary_unit,
    load_mysql_test_data,
    restart_unit_machine,
    update_interval,
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
        base="ubuntu@22.04",
        config={"profile": "testing"},
        num_units=3,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
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
        ready=wait_for_apps_status(
            jubilant_backports.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME
        ),
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_auto_recover_on_quorum_loss(juju: Juju, continuous_writes) -> None:
    """Test safe auto-recover after quorum loss."""
    app_name = get_app_name(juju, MYSQL_APP_NAME)
    assert app_name, "MySQL application not found in the cluster"

    app_units = set(get_app_units(juju, app_name))

    primary_unit = get_mysql_primary_unit(juju, app_name)
    assert primary_unit, "No primary unit found in the cluster"
    logging.info(f"Current primary unit: {primary_unit}")

    non_primary_units = app_units - {primary_unit}

    unit_to_survive = non_primary_units.pop()

    logging.info("Simulate quorum loss")
    logging.info(f"Unit selected for survival: {unit_to_survive}")

    for unit_name in [non_primary_units.pop(), primary_unit]:
        restart_unit_machine(juju, app_name, unit_name)

    with update_interval(juju, "15s"):
        logging.info("Waiting for all units to become active after switchover...")
        juju.wait(
            ready=jubilant_backports.all_active,
            timeout=10 * MINUTE_SECS,
            delay=5,
        )

    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)
