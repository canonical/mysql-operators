#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import time

import jubilant
from jubilant import Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    get_app_leader,
    get_app_units,
    get_mysql_max_written_value,
    get_mysql_variable_value,
    load_mysql_test_data,
    wait_for_apps_status,
    wait_for_unit_status,
)

MYSQL_APP_1 = "db1"
MYSQL_APP_2 = "db2"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


def test_build_and_deploy(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL application charms get deployed."""
    configuration = {"profile": "testing"}
    constraints = {"arch": architecture.architecture}

    logging.info("Deploying mysql clusters")
    juju.deploy(
        charm="mysql-k8s",
        app=MYSQL_APP_1,
        base="ubuntu@26.04",
        channel="8.4/edge",
        config={**configuration, "cluster-name": "lima"},
        constraints=constraints,
        num_units=1,
        trust=True,
    )
    juju.deploy(
        charm="mysql-k8s",
        app=MYSQL_APP_2,
        base="ubuntu@26.04",
        channel="8.4/edge",
        config={**configuration, "cluster-name": "cuzco"},
        constraints=constraints,
        num_units=1,
        trust=True,
    )

    logging.info("Waiting for the applications to settle")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_1, MYSQL_APP_2),
        timeout=10 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_1, path)


def test_async_relate(juju: Juju) -> None:
    """Relate the two MySQL clusters."""
    logging.info("Relating the two mysql clusters")
    juju.integrate(
        f"{MYSQL_APP_1}:replication-offer",
        f"{MYSQL_APP_2}:replication",
    )

    logging.info("Waiting for the applications to settle")
    juju.wait(
        ready=wait_for_apps_status(jubilant.any_blocked, MYSQL_APP_1),
        timeout=5 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.any_waiting, MYSQL_APP_2),
        timeout=5 * MINUTE_SECS,
    )


def test_deploy_test_app(juju: Juju) -> None:
    """Deploy the test application."""
    logging.info("Deploying the test application")
    constraints = {"arch": architecture.architecture}
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@26.04",
        channel="latest/edge",
        num_units=1,
        constraints=constraints,
    )

    logging.info("Relating the test application")
    juju.integrate(
        f"{MYSQL_APP_1}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_TEST_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )


def test_create_replication(juju: Juju) -> None:
    """Run the create-replication action and wait for the applications to settle."""
    logging.info("Running create replication action")
    juju.run(
        unit=get_app_leader(juju, MYSQL_APP_1),
        action="create-replication",
        wait=5 * MINUTE_SECS,
    )

    logging.info("Waiting for the applications to settle")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_1, MYSQL_APP_2),
        timeout=5 * MINUTE_SECS,
    )


def test_refresh_from_edge(juju: Juju, charm: str, continuous_writes) -> None:
    """Upgrade the two MySQL clusters."""
    run_pre_refresh_checks(juju, MYSQL_APP_1)
    run_refresh_from_edge(juju, MYSQL_APP_1, charm)

    run_pre_refresh_checks(juju, MYSQL_APP_2)
    run_refresh_from_edge(juju, MYSQL_APP_2, charm)


def test_data_replication(juju: Juju, continuous_writes) -> None:
    """Test to write to primary, and read the same data back from replicas."""
    logging.info("Testing data replication")
    results = get_mysql_max_written_values(juju)

    assert len(results) == 2
    assert all(results[0] == x for x in results), "Data is not consistent across units"
    assert results[0] > 1, "No data was written to the database"


def get_mysql_max_written_values(juju: Juju) -> list[int]:
    """Return list with max written value from all units."""
    logging.info("Stopping continuous writes")
    juju.run(
        unit=get_app_leader(juju, MYSQL_TEST_APP_NAME),
        action="stop-continuous-writes",
        params={},
    )

    time.sleep(5)
    results = []

    logging.info(f"Querying max value on all {MYSQL_APP_1} units")
    for unit_name in get_app_units(juju, MYSQL_APP_1):
        unit_max_value = get_mysql_max_written_value(juju, MYSQL_APP_1, unit_name)
        results.append(unit_max_value)

    logging.info(f"Querying max value on all {MYSQL_APP_2} units")
    for unit_name in get_app_units(juju, MYSQL_APP_2):
        unit_max_value = get_mysql_max_written_value(juju, MYSQL_APP_2, unit_name)
        results.append(unit_max_value)

    return results


def run_pre_refresh_checks(juju: Juju, app_name: str) -> None:
    """Run the pre-refresh-check actions."""
    app_leader = get_app_leader(juju, app_name)
    app_units = get_app_units(juju, app_name)

    logging.info("Run pre-refresh-check action")
    juju.run(unit=app_leader, action="pre-refresh-check")

    logging.info("Assert slow shutdown is enabled")
    for unit_name in app_units:
        value = get_mysql_variable_value(juju, app_name, unit_name, "innodb_fast_shutdown")
        assert value == 0


def run_refresh_from_edge(juju: Juju, app_name: str, charm: str) -> None:
    """Refresh the second cluster."""
    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, app_name)

    logging.info("Refresh the charm")
    juju.refresh(
        app=app_name,
        path=charm,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
    )

    unit = f"{app_name}/0"
    logging.info("Wait for refresh to start")
    juju.wait(
        ready=wait_for_unit_status(app_name, unit, "maintenance"),
        timeout=10 * MINUTE_SECS,
    )

    app_status = juju.status().apps[app_name]
    upgrade_unit_status = app_status.units[unit]
    upgrade_unit_message = upgrade_unit_status.workload_status.message

    if "Refresh incompatible" in upgrade_unit_message:
        logging.info("Application refresh is blocked due to incompatibility")
        juju.run(
            unit=unit,
            action="force-refresh-start",
            params={"check-compatibility": False},
            wait=5 * MINUTE_SECS,
        )

    logging.info("Wait for refresh to complete")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, app_name),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, app_name)
