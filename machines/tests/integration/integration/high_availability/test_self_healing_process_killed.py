# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju

from ...helpers import generate_random_string
from ...helpers_ha import (
    check_mysql_units_writes_increment,
    get_mysql_primary_unit,
    get_unit_process_id,
    insert_mysql_test_data,
    remove_mysql_test_data,
    update_interval,
    verify_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql"
MYSQL_PROCESS_NAME = "mysqld"
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
        base="ubuntu@24.04",
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
        error=jubilant.any_blocked,
        timeout=20 * MINUTE_SECS,
    )


def test_kill_db_process(juju: Juju, continuous_writes) -> None:
    """Kill mysqld process and check for auto cluster recovery."""
    # Ensure continuous writes still incrementing for all units
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    mysql_primary_unit = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    mysql_primary_unit_pid = get_unit_process_id(juju, mysql_primary_unit, MYSQL_PROCESS_NAME)

    logging.info(f"Killing process id {mysql_primary_unit_pid}")
    juju.exec(f"sudo kill --signal SIGKILL {mysql_primary_unit_pid}", unit=mysql_primary_unit)

    new_mysql_primary_unit_pid = get_unit_process_id(juju, mysql_primary_unit, MYSQL_PROCESS_NAME)
    assert new_mysql_primary_unit_pid != mysql_primary_unit_pid

    # Ensure continuous writes still incrementing for all units
    with update_interval(juju, "10s"):
        check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    # Ensure that we are able to insert data into the primary
    table_name = "data"
    table_value = generate_random_string(255)

    insert_mysql_test_data(juju, MYSQL_APP_NAME, table_name, table_value)
    verify_mysql_test_data(juju, MYSQL_APP_NAME, table_name, table_value)
    remove_mysql_test_data(juju, MYSQL_APP_NAME, table_name)
