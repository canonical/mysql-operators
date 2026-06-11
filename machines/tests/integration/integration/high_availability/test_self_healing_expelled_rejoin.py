# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import time

import jubilant_backports
from jubilant_backports import Juju

from ...helpers_ha import (
    check_mysql_units_writes_increment,
    execute_queries_on_unit,
    get_mysql_primary_unit,
    get_mysql_server_credentials,
    get_unit_ip,
    get_unit_process_id,
    load_mysql_test_data,
    update_interval,
    wait_for_apps_status,
    wait_for_unit_status,
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


def test_expelled_member_rejoin(juju: Juju, continuous_writes) -> None:
    """Test that an expelled member can rejoin the cluster.

    Disable autorejoin on one unit, freeze mysqld long enough to be expelled
    from the group, then unfreeze and verify automatic rejoin via charm.
    """
    target_unit = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    target_ip = get_unit_ip(juju, MYSQL_APP_NAME, target_unit)

    credentials = get_mysql_server_credentials(juju, target_unit)

    logging.info(f"Disabling autorejoin on {target_unit}")
    execute_queries_on_unit(
        unit_address=target_ip,
        username=credentials["username"],
        password=credentials["password"],
        queries=["SET PERSIST group_replication_autorejoin_tries=0"],
        commit=True,
    )

    target_pid = get_unit_process_id(juju, target_unit, MYSQL_PROCESS_NAME)
    logging.info(f"Sending SIGSTOP to mysqld (pid={target_pid}) on {target_unit}")
    juju.exec(f"sudo kill --signal SIGSTOP {target_pid}", unit=target_unit)

    logging.info("Waiting 30 seconds for unit to be expelled from group")
    time.sleep(30)

    logging.info(f"Sending SIGCONT to mysqld on {target_unit}")
    juju.exec(f"sudo kill --signal SIGCONT {target_pid}", unit=target_unit)

    logging.info(f"Waiting for {target_unit} to enter maintenance")
    juju.wait(
        ready=wait_for_unit_status(MYSQL_APP_NAME, target_unit, "maintenance"),
        timeout=10 * MINUTE_SECS,
    )

    logging.info(f"Waiting for {target_unit} to rejoin and become active")
    with update_interval(juju, "10s"):
        juju.wait(
            ready=wait_for_unit_status(MYSQL_APP_NAME, target_unit, "active"),
            timeout=10 * MINUTE_SECS,
        )

    logging.info("Ensuring all units have incrementing continuous writes")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)
