# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import jubilant_backports
from jubilant_backports import Juju
from tenacity import Retrying, stop_after_delay, wait_fixed

from constants import CONTAINER_NAME, MYSQL_DATA_DIR

from ... import architecture
from ...helpers import execute_queries_on_unit
from ...helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    check_mysql_instances_online,
    check_mysql_units_writes_increment,
    force_kill_mysqld_service,
    get_app_units,
    get_mysql_server_credentials,
    get_unit_address,
    load_mysql_test_data,
    start_mysqld_service,
    update_interval,
    wait_for_apps_status,
    wait_for_unit_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TEST_APP_NAME = "mysql-test-app"

# ER_REPLICA_RELAY_LOG_READ_FAILURE
RELAY_LOG_READ_FAILURE = 13121


def test_deploy_highly_available_cluster(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@22.04",
        config={"profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=3,
        trust=True,
    )
    constraints = {"arch": architecture.architecture}
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
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
        ready=wait_for_apps_status(
            jubilant_backports.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME
        ),
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_full_cluster_crash_with_corrupted_relay_log(juju: Juju, continuous_writes) -> None:
    """Complete outage leaving a torn group replication applier relay log on every unit.

    Simulates a power loss in which every instance is killed and left with a
    corrupted applier relay log tail. Neither rejoin nor reboot from complete
    outage can succeed until the charm resets the applier relay log.
    """
    # Ensure continuous writes still incrementing for all units
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    mysql_units = get_app_units(juju, MYSQL_APP_NAME)

    # Keep update-status from healing the cluster before the fault is asserted
    with update_interval(juju, "60m"):
        logging.info("Killing all instances")
        for unit_name in mysql_units:
            force_kill_mysqld_service(juju, unit_name)

        logging.info("Corrupting the applier relay log on all instances")
        for unit_name in mysql_units:
            corrupt_applier_relay_log(juju, unit_name)

        logging.info("Starting all instances")
        for unit_name in mysql_units:
            start_mysqld_service(juju, unit_name)

        logging.info("Checking the applier fails reading the relay log on all instances")
        for unit_name in mysql_units:
            for attempt in Retrying(
                reraise=True,
                stop=stop_after_delay(5 * MINUTE_SECS),
                wait=wait_fixed(10),
            ):
                with attempt:
                    error_number = get_applier_last_error_number(juju, unit_name)
                    assert error_number == RELAY_LOG_READ_FAILURE

    with update_interval(juju, "10s"):
        logging.info("Waiting units to enter maintenance")
        juju.wait(
            ready=lambda status: all(
                wait_for_unit_status(MYSQL_APP_NAME, unit_name, "maintenance")(status)
                for unit_name in mysql_units
            ),
            timeout=20 * MINUTE_SECS,
        )
        logging.info("Waiting units to be back online")
        juju.wait(
            ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
            timeout=20 * MINUTE_SECS,
        )

    logging.info("Check that all units are online")
    assert check_mysql_instances_online(juju, MYSQL_APP_NAME, mysql_units)

    logging.info("Check the applier relay log error is cleared on all instances")
    for unit_name in mysql_units:
        assert get_applier_last_error_number(juju, unit_name) == 0

    # Ensure continuous writes still incrementing for all units
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)


def corrupt_applier_relay_log(juju: Juju, unit_name: str) -> None:
    """Append garbage to the latest applier relay log, simulating a torn write."""
    relay_log_pattern = f"{MYSQL_DATA_DIR}/*-relay-bin-group_replication_applier.0*"
    juju.ssh(
        command=(
            f"relay_log=$(ls {relay_log_pattern} | sort | tail -n 1) && "
            'head -c 512 /dev/urandom >> "$relay_log"'
        ),
        target=unit_name,
        container=CONTAINER_NAME,
    )


def get_applier_last_error_number(juju: Juju, unit_name: str) -> int:
    """Return the last error number of the group replication applier coordinator."""
    credentials = get_mysql_server_credentials(juju, unit_name)

    output = execute_queries_on_unit(
        get_unit_address(juju, MYSQL_APP_NAME, unit_name),
        credentials["username"],
        credentials["password"],
        [
            "SELECT LAST_ERROR_NUMBER"
            " FROM performance_schema.replication_applier_status_by_coordinator"
            " WHERE CHANNEL_NAME = 'group_replication_applier'"
        ],
    )
    return output[0]
