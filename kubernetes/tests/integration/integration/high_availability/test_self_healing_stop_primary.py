# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import jubilant
from jubilant import Juju

from constants import CONTAINER_NAME

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    get_mysql_primary_unit,
    get_unit_process_id,
    load_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_PROCESS_NAME = "mysqld"
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
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        storage={"data": "500M", "archive": "250M", "logs": "250M", "temp": "250M"},
        num_units=3,
        trust=True,
    )
    constraints = {"arch": architecture.architecture}
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@26.04",
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


def test_graceful_crash_of_primary(juju: Juju, continuous_writes) -> None:
    """Test to send SIGTERM to primary instance and then verify recovery."""
    # Ensure continuous writes still incrementing for all units
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    mysql_primary_unit = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    mysql_primary_unit_pid = get_unit_process_id(juju, mysql_primary_unit, MYSQL_PROCESS_NAME)

    logging.info(f"Terminating process id {mysql_primary_unit_pid}")
    juju.ssh(
        target=mysql_primary_unit,
        container=CONTAINER_NAME,
        command=f"pkill -x {MYSQL_PROCESS_NAME} --signal SIGTERM",
    )

    new_mysql_primary_unit_pid = get_unit_process_id(juju, mysql_primary_unit, MYSQL_PROCESS_NAME)
    assert new_mysql_primary_unit_pid == mysql_primary_unit_pid

    logging.info("Waiting until there are 3 online mysql instances again")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    new_mysql_primary_unit = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    assert new_mysql_primary_unit != mysql_primary_unit

    # Ensure continuous writes still incrementing for all units
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)
