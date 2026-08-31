# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import shutil
import zipfile
from pathlib import Path

import jubilant
import tomli
import tomli_w
from jubilant import Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    continuous_writes_ctx,
    get_app_leader,
    get_app_units,
    get_mysql_primary_unit,
    get_mysql_variable_value,
    load_mysql_test_data,
    wait_for_apps_status,
    wait_for_unit_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TEST_APP_NAME = "mysql-test-app"
MYSQL_ROUTER_APP_NAME = "mysql-router-k8s"

MINUTE_SECS = 60


def test_deploy_latest(juju: Juju) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=MYSQL_APP_NAME,
        app=MYSQL_APP_NAME,
        base="ubuntu@26.04",
        channel="8.4/edge",
        config={"profile": "testing"},
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
        num_units=1,
        trust=False,
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


def test_pre_refresh_check(juju: Juju) -> None:
    """Test that the pre-refresh-check action runs successfully."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_units = get_app_units(juju, MYSQL_APP_NAME)

    logging.info("Run pre-refresh-check action")
    juju.run(unit=mysql_leader, action="pre-refresh-check")

    logging.info("Assert slow shutdown is enabled")
    for unit_name in mysql_units:
        value = get_mysql_variable_value(juju, MYSQL_APP_NAME, unit_name, "innodb_fast_shutdown")
        assert value == 0

    logging.info("Assert primary is set to leader")
    mysql_primary = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    assert mysql_primary == f"{MYSQL_APP_NAME}/0", "Primary unit not set to unit 0"


def test_refresh_from_edge(juju: Juju, charm: str, continuous_writes) -> None:
    """Refresh using the locally built charm."""
    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_units = get_app_units(juju, MYSQL_APP_NAME)
    mysql_units.sort()

    logging.info("Refresh the charm")
    juju.refresh(
        app=MYSQL_APP_NAME,
        path=charm,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
    )

    logging.info("Wait for refresh to start")
    juju.wait(
        ready=wait_for_apps_status(jubilant.any_blocked, MYSQL_APP_NAME),
        timeout=5 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_unit_status(MYSQL_APP_NAME, mysql_units[-1], "blocked"),
        timeout=5 * MINUTE_SECS,
    )

    mysql_status = juju.status().apps[MYSQL_APP_NAME]
    upgrade_unit_status = mysql_status.units[mysql_units[-1]]
    upgrade_unit_message = upgrade_unit_status.workload_status.message

    if "Refresh incompatible" in upgrade_unit_message:
        logging.info("Application refresh is blocked due to incompatibility")
        juju.run(
            unit=mysql_units[-1],
            action="force-refresh-start",
            params={"check-compatibility": False},
            wait=5 * MINUTE_SECS,
        )

    logging.info("Wait for refresh to finish on first unit")
    juju.wait(
        ready=jubilant.all_agents_idle,
        timeout=5 * MINUTE_SECS,
    )

    logging.info("Resume refresh")
    juju.run(
        unit=mysql_leader,
        action="resume-refresh",
        wait=5 * MINUTE_SECS,
    )

    logging.info("Wait for refresh to complete")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)


def test_relation_through_router(juju: Juju) -> None:
    """Test that a fresh relation routed through mysql-router-k8s works after refresh."""
    logging.info("Removing pre-existing direct relation to mysql-test-app")
    juju.remove_relation(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    logging.info("Waiting for mysql-test-app to be blocked (no database)")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_blocked, MYSQL_TEST_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Deploying mysql-router-k8s")
    juju.deploy(
        charm=MYSQL_ROUTER_APP_NAME,
        app=MYSQL_ROUTER_APP_NAME,
        base="ubuntu@26.04",
        channel="8.4/edge",
        num_units=1,
        trust=True,
    )

    logging.info("Relating mysql-k8s and mysql-test-app through the router")
    juju.integrate(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_ROUTER_APP_NAME}:backend-database",
    )
    juju.integrate(
        f"{MYSQL_TEST_APP_NAME}:database",
        f"{MYSQL_ROUTER_APP_NAME}:database",
    )

    logging.info("Waiting for all applications to become active")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant.all_active,
            MYSQL_APP_NAME,
            MYSQL_ROUTER_APP_NAME,
            MYSQL_TEST_APP_NAME,
        ),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes are incrementing through the router")
    with continuous_writes_ctx(juju, MYSQL_TEST_APP_NAME):
        check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)


def test_fail_and_rollback(juju: Juju, charm: str, continuous_writes) -> None:
    """Test a refresh failure and its rollback."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_units = get_app_units(juju, MYSQL_APP_NAME)
    mysql_units.sort()

    logging.info("Run pre-refresh-check action")
    juju.run(unit=mysql_leader, action="pre-refresh-check")

    tmp_folder = Path("tmp")
    tmp_folder.mkdir(exist_ok=True)
    tmp_folder_charm = Path(tmp_folder, charm).absolute()

    shutil.copy(charm, tmp_folder_charm)

    logging.info("Inject dependency fault")
    inject_dependency_fault(tmp_folder_charm)

    logging.info("Refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=tmp_folder_charm)

    logging.info("Wait for upgrade to fail on first upgrading unit")
    juju.wait(
        ready=wait_for_unit_status(MYSQL_APP_NAME, mysql_units[-1], "blocked"),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes on remaining units")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME, mysql_units[0:-1])

    logging.info("Re-refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=charm)

    logging.info("Wait for refresh to start")
    juju.wait(
        ready=wait_for_apps_status(jubilant.any_blocked, MYSQL_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Wait for refresh to finish on first unit")
    juju.wait(
        ready=jubilant.all_agents_idle,
        timeout=5 * MINUTE_SECS,
    )

    logging.info("Resume refresh")
    juju.run(
        unit=mysql_leader,
        action="resume-refresh",
        wait=5 * MINUTE_SECS,
    )

    logging.info("Wait for refresh to complete")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes after rollback procedure")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME, mysql_units)

    # Remove fault charm file
    tmp_folder_charm.unlink()


def inject_dependency_fault(charm_file: str | Path) -> None:
    """Inject a dependency fault into the MySQL charm."""
    with Path("refresh_versions.toml").open("rb") as file:
        versions = tomli.load(file)

    versions["charm"] = "8.4/0.0.0"
    versions["workload"] = "8.4"

    # Overwrite refresh_versions.toml with incompatible version.
    with zipfile.ZipFile(charm_file, mode="a") as charm_zip:
        charm_zip.writestr("refresh_versions.toml", tomli_w.dumps(versions))
