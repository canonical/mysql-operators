# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import subprocess

import jubilant_backports
from jubilant_backports import Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    get_app_name,
    get_app_units,
    get_mysql_instance_label,
    get_mysql_primary_unit,
    load_mysql_test_data,
    update_interval,
    wait_for_apps_status,
    wait_for_unit_status,
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
        error=jubilant_backports.any_blocked,
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

    unit_to_survive = non_primary_units.pop()
    units_to_freeze = [non_primary_units.pop(), primary_unit]

    logging.info(f"Unit selected for promotion: {unit_to_survive}")

    logging.info("Simulating quorum loss via SIGSTOP on mysqld")
    freeze_mysql(juju, units_to_freeze)

    with update_interval(juju, "45s"):
        logging.info("Waiting for surviving unit to detect quorum loss")
        juju.wait(
            ready=lambda status: wait_for_unit_status(app_name, unit_to_survive, "active")(status),
            timeout=5 * MINUTE_SECS,
            delay=10,
        )

    logging.info("Attempting to promote surviving unit to primary after quorum loss...")
    juju.run(
        unit=unit_to_survive,
        action="promote-to-primary",
        params={"scope": "unit", "force": True},
        wait=600,
    )

    logging.info("Resuming frozen units so they can rejoin the cluster")
    unfreeze_mysql(juju, units_to_freeze)

    with update_interval(juju, "15s"):
        logging.info("Waiting for all units to become active after switchover...")
        juju.wait(
            ready=jubilant_backports.all_active,
            timeout=10 * MINUTE_SECS,
            delay=5,
        )

    assert get_mysql_primary_unit(juju, app_name) == unit_to_survive, "Failover failed"


def freeze_mysql(juju: Juju, unit_names: list[str]) -> None:
    """Freeze mysqld in the mysql container via SIGSTOP to simulate unreachable members."""
    for unit in unit_names:
        pod = get_mysql_instance_label(unit)
        subprocess.check_call(
            [
                "kubectl",
                "exec",
                pod,
                "-n",
                juju.model or "testing",
                "-c",
                "mysql",
                "--",
                "bash",
                "-c",
                "kill -STOP $(pgrep -x mysqld)",
            ],
        )


def unfreeze_mysql(juju: Juju, unit_names: list[str]) -> None:
    """Resume frozen mysqld in the mysql container via SIGCONT."""
    for unit in unit_names:
        pod = get_mysql_instance_label(unit)
        subprocess.check_call(
            [
                "kubectl",
                "exec",
                pod,
                "-n",
                juju.model or "testing",
                "-c",
                "mysql",
                "--",
                "bash",
                "-c",
                "kill -CONT $(pgrep -x mysqld)",
            ],
        )
