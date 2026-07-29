#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import time

import jubilant
from jubilant import Juju

from ... import architecture
from ...helpers_ha import (
    get_app_leader,
    get_app_units,
    get_mysql_cluster_status,
    get_mysql_max_written_value,
    load_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_1 = "db1"
MYSQL_APP_2 = "db2"
MYSQL_ROUTER_NAME = "mysql-router"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


def test_build_and_deploy(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL application charms get deployed."""
    configuration = {"profile": "testing"}
    constraints = {"arch": architecture.architecture}

    logging.info("Deploying mysql clusters")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_1,
        base="ubuntu@26.04",
        config={**configuration, "cluster-name": "lima"},
        constraints=constraints,
        num_units=1,
    )
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_2,
        base="ubuntu@26.04",
        config={**configuration, "cluster-name": "cuzco"},
        constraints=constraints,
        num_units=1,
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


def test_deploy_router_and_app(juju: Juju) -> None:
    """Deploy the router and the test application."""
    logging.info("Deploying the router and test application")
    juju.deploy(
        charm=MYSQL_ROUTER_NAME,
        app=MYSQL_ROUTER_NAME,
        base="ubuntu@26.04",
        channel="8.4/edge",
        num_units=1,
        trust=True,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@26.04",
        channel="latest/edge",
        num_units=1,
        trust=False,
    )

    logging.info("Relating the router and test application")
    juju.integrate(
        f"{MYSQL_ROUTER_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )
    juju.integrate(
        f"{MYSQL_ROUTER_NAME}:backend-database",
        f"{MYSQL_APP_1}:database",
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


def test_data_replication(juju: Juju, continuous_writes) -> None:
    """Test to write to primary, and read the same data back from replicas."""
    logging.info("Testing data replication")
    results = get_mysql_max_written_values(juju)

    assert len(results) == 2
    assert all(results[0] == x for x in results), "Data is not consistent across units"
    assert results[0] > 1, "No data was written to the database"


def test_standby_promotion(juju: Juju, continuous_writes) -> None:
    """Test graceful promotion of a standby cluster to primary."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_2)

    logging.info("Promoting standby cluster to primary")
    juju.run(
        unit=mysql_leader,
        action="promote-to-primary",
        params={"scope": "cluster"},
    )

    results = get_mysql_max_written_values(juju)
    assert len(results) == 2
    assert all(results[0] == x for x in results), "Data is not consistent across units"
    assert results[0] > 1, "No data was written to the database"

    cluster_set_status = get_mysql_cluster_status(
        juju=juju,
        unit=mysql_leader,
        cluster_set=True,
    )

    assert cluster_set_status["clusters"]["cuzco"]["clusterRole"] == "PRIMARY", (
        "standby not promoted to primary"
    )


def test_failover(juju: Juju) -> None:
    """Test switchover on primary cluster fail."""
    logging.info("Freezing mysqld on primary cluster units")
    mysql_units = get_app_units(juju, MYSQL_APP_2)

    # Simulating a failure on the primary cluster
    for unit_name in mysql_units:
        juju.ssh(command="sudo pkill -x mysqld --signal SIGSTOP", target=unit_name)

    logging.info("Promoting standby cluster to primary with force flag")
    mysql_leader = get_app_leader(juju, MYSQL_APP_1)

    juju.run(
        unit=mysql_leader,
        action="promote-to-primary",
        params={"scope": "cluster", "force": True},
        wait=5 * MINUTE_SECS,
    )

    # Restore mysqld process
    logging.info("Unfreezing mysqld on primary cluster units")
    for unit_name in mysql_units:
        juju.ssh(command="sudo pkill -x mysqld --signal SIGCONT", target=unit_name)

    logging.info("Checking clusters statuses")
    cluster_set_status = get_mysql_cluster_status(
        juju=juju,
        unit=mysql_leader,
        cluster_set=True,
    )

    assert cluster_set_status["clusters"]["lima"]["clusterRole"] == "PRIMARY", (
        "standby not promoted to primary",
    )
    assert cluster_set_status["clusters"]["cuzco"]["globalStatus"] == "INVALIDATED", (
        "old primary not invalidated"
    )


def test_rejoin_invalidated_cluster(juju: Juju, continuous_writes) -> None:
    """Test rejoin invalidated cluster with."""
    juju.run(
        unit=get_app_leader(juju, MYSQL_APP_1),
        action="rejoin-cluster",
        params={"cluster-name": "cuzco"},
        wait=5 * MINUTE_SECS,
    )

    results = get_mysql_max_written_values(juju)
    assert len(results) == 2
    assert all(results[0] == x for x in results), "Data is not consistent across units"
    assert results[0] > 1, "No data was written to the database"


def test_unrelate_and_relate(juju: Juju, continuous_writes) -> None:
    """Test removing and re-relating the two mysql clusters."""
    logging.info("Remove async relation")
    juju.remove_relation(
        f"{MYSQL_APP_1}:replication-offer",
        f"{MYSQL_APP_2}:replication",
    )

    logging.info("Waiting for the applications to settle")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_1),
        timeout=10 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_blocked, MYSQL_APP_2),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Re relating the two mysql clusters")
    juju.integrate(
        f"{MYSQL_APP_1}:replication-offer",
        f"{MYSQL_APP_2}:replication",
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.any_blocked, MYSQL_APP_1),
        timeout=5 * MINUTE_SECS,
    )

    logging.info("Running create replication action")
    juju.run(
        unit=get_app_leader(juju, MYSQL_APP_1),
        action="create-replication",
        wait=5 * MINUTE_SECS,
    )

    logging.info("Waiting for the applications to settle")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_1, MYSQL_APP_2),
        timeout=10 * MINUTE_SECS,
    )

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

    return results
