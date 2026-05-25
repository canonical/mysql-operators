# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import random

import jubilant
from jubilant import Juju
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_fixed,
)

from constants import CONTAINER_NAME

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    exec_k8s_container_command,
    get_app_units,
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


def test_freeze_db_process(juju: Juju, continuous_writes) -> None:
    """Test to send a SIGSTOP to the primary db process and ensure that the cluster self heals."""
    logging.info("Ensuring that all instances have incrementing continuous writes")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    mysql_units = get_app_units(juju, MYSQL_APP_NAME)
    mysql_primary_unit = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    mysql_primary_unit_pid = get_unit_process_id(juju, mysql_primary_unit, MYSQL_PROCESS_NAME)

    logging.info(f"Stopping process id {mysql_primary_unit_pid}")
    exec_k8s_container_command(
        juju=juju,
        unit_name=mysql_primary_unit,
        container_name=CONTAINER_NAME,
        command=f"pkill -f {MYSQL_PROCESS_NAME} --signal SIGSTOP",
    )

    # Ensure that the mysqld process is stopped after receiving the sigstop
    # (see https://man7.org/linux/man-pages/man1/ps.1.html under PROCESS STATE CODES)
    assert "T" in get_process_stat(
        juju=juju,
        unit_name=mysql_primary_unit,
        container_name=CONTAINER_NAME,
        process_name=MYSQL_PROCESS_NAME,
    )

    online_units = set(mysql_units) - {mysql_primary_unit}
    online_units = list(online_units)
    random_unit = random.choice(online_units)

    logging.info("Waiting for new primary to be elected")
    for attempt in Retrying(stop=stop_after_attempt(10), wait=wait_fixed(10)):
        with attempt:
            new_mysql_primary_unit = get_mysql_primary_unit(juju, MYSQL_APP_NAME, random_unit)
            assert new_mysql_primary_unit != mysql_primary_unit

    logging.info(f"Continuing process id {mysql_primary_unit_pid}")
    exec_k8s_container_command(
        juju=juju,
        unit_name=mysql_primary_unit,
        container_name=CONTAINER_NAME,
        command=f"pkill -f {MYSQL_PROCESS_NAME} --signal SIGCONT",
    )

    # Ensure that the mysqld process has started after receiving the sigstop
    # (see https://man7.org/linux/man-pages/man1/ps.1.html under PROCESS STATE CODES)
    # T = stopped by job control signal
    # R = running or runnable
    # S = interruptible sleep
    # I = idle kernel thread
    mysql_process_stat = get_process_stat(
        juju=juju,
        unit_name=mysql_primary_unit,
        container_name=CONTAINER_NAME,
        process_name=MYSQL_PROCESS_NAME,
    )
    assert all((
        "T" not in mysql_process_stat,
        "R" in mysql_process_stat or "S" in mysql_process_stat or "I" in mysql_process_stat,
    ))

    new_mysql_primary_unit_pid = get_unit_process_id(juju, mysql_primary_unit, MYSQL_PROCESS_NAME)
    assert new_mysql_primary_unit_pid == mysql_primary_unit_pid

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensuring that all instances have incrementing continuous writes")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)


def get_process_stat(juju: Juju, unit_name: str, container_name: str, process_name: str) -> str:
    """Retrieve the STAT column of a process on a pod container.

    Args:
        juju: The Juju instance
        unit_name: The name of the unit for the process
        container_name: The name of the container for the process
        process_name: The name of the process to get the STAT for
    """
    return juju.ssh(
        command=f"ps -eo comm,stat | grep {process_name} | awk '{{print $2}}'",
        target=unit_name,
        container=container_name,
    )
