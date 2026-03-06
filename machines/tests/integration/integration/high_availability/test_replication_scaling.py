# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju

from ...helpers import generate_random_string
from ...helpers_ha import (
    get_app_units,
    insert_mysql_test_data,
    remove_mysql_test_data,
    scale_app_units,
    verify_mysql_test_data,
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
        base="ubuntu@24.04",
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


def test_scaling_without_data_loss(juju: Juju) -> None:
    """Test that data is preserved during scale up and scale down."""
    table_name = "instance_state_replication"
    table_value = generate_random_string(255)

    insert_mysql_test_data(juju, MYSQL_APP_NAME, table_name, table_value)

    mysql_app_old_units = set(get_app_units(juju, MYSQL_APP_NAME))
    scale_app_units(juju, MYSQL_APP_NAME, 4)
    mysql_app_new_units = set(get_app_units(juju, MYSQL_APP_NAME))

    # Ensure that all units have the above inserted data
    verify_mysql_test_data(juju, MYSQL_APP_NAME, table_name, table_value)

    mysql_app_added_unit = (mysql_app_new_units - mysql_app_old_units).pop()
    juju.remove_unit(mysql_app_added_unit)
    juju.wait(
        ready=lambda status: len(status.apps[MYSQL_APP_NAME].units) == 3,
        timeout=20 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        error=jubilant.any_blocked,
        timeout=20 * MINUTE_SECS,
    )

    # Ensure that the data still exists in all the units
    verify_mysql_test_data(juju, MYSQL_APP_NAME, table_name, table_value)
    remove_mysql_test_data(juju, MYSQL_APP_NAME, table_name)
