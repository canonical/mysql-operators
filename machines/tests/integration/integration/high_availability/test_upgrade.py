# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import platform
import shutil
import zipfile
from pathlib import Path

import jubilant
import tomli
import tomli_w
from jubilant import Juju

from ...helpers_ha import (
    check_mysql_units_writes_increment,
    get_app_leader,
    get_app_units,
    get_mysql_primary_unit,
    get_mysql_variable_value,
    load_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql"
MYSQL_TEST_APP_NAME = "mysql-test-app"
MYSQL_ROUTER_APP_NAME = "mysql-router"

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
        num_units=3,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@26.04",
        channel="latest/edge",
        num_units=1,
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
    assert mysql_primary == mysql_leader, "Primary unit not set to leader"


def test_refresh_from_edge(juju: Juju, charm: str, continuous_writes) -> None:
    """Refresh using the locally built charm."""
    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    mysql_units = get_app_units(juju, MYSQL_APP_NAME)
    mysql_units.sort()

    logging.info("Refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=charm)

    try:
        logging.info("Wait for refresh to start")
        juju.wait(
            ready=wait_for_apps_status(jubilant.all_blocked, MYSQL_APP_NAME),
            timeout=5 * MINUTE_SECS,
        )

        if "Refresh incompatible" in juju.status().apps[MYSQL_APP_NAME].app_status.message:
            logging.info("Application refresh is blocked due to incompatibility")
            juju.run(
                unit=mysql_units[-1],
                action="force-refresh-start",
                params={"check-compatibility": False},
                wait=5 * MINUTE_SECS,
            )
    except TimeoutError:
        logging.info("Refresh completed without snap refresh (Python code only)")
    else:
        logging.info("Wait for refresh to finish on first unit")
        juju.wait(
            ready=jubilant.all_agents_idle,
            timeout=5 * MINUTE_SECS,
        )

        logging.info("Resume refresh")
        juju.run(
            unit=mysql_units[-2],
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
    """Test that a fresh relation routed through mysql-router works after refresh."""
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

    logging.info("Deploying mysql-router")
    juju.deploy(
        charm=MYSQL_ROUTER_APP_NAME,
        app=MYSQL_ROUTER_APP_NAME,
        base="ubuntu@26.04",
        channel="8.4/edge",
        num_units=1,
    )

    logging.info("Relating mysql and mysql-test-app through the router")
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

    logging.info("Start continuous writes through the router-mediated relation")
    test_app_leader = get_app_leader(juju, MYSQL_TEST_APP_NAME)
    juju.run(test_app_leader, "clear-continuous-writes")
    juju.run(test_app_leader, "start-continuous-writes")

    logging.info("Ensure continuous writes are incrementing through the router")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    logging.info("Clearing continuous writes")
    juju.run(test_app_leader, "clear-continuous-writes")


def test_fail_and_rollback(juju: Juju, charm: str, continuous_writes) -> None:
    """Test a refresh failure and its rollback."""
    mysql_app_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_app_units = get_app_units(juju, MYSQL_APP_NAME)

    logging.info("Run pre-refresh-check action")
    juju.run(unit=mysql_app_leader, action="pre-refresh-check")

    tmp_folder = Path("tmp")
    tmp_folder.mkdir(exist_ok=True)
    tmp_folder_charm = Path(tmp_folder, charm).absolute()

    shutil.copy(charm, tmp_folder_charm)

    logging.info("Inject dependency fault")
    inject_dependency_fault(tmp_folder_charm)

    logging.info("Refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=tmp_folder_charm)

    logging.info("Wait for refresh to fail on leader")
    juju.wait(
        ready=wait_for_apps_status(jubilant.any_blocked, MYSQL_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes on all units")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME, mysql_app_units)

    logging.info("Re-refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=charm)

    logging.info("Wait for refresh to complete")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes after rollback procedure")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME, mysql_app_units)

    # Remove fault charm file
    tmp_folder_charm.unlink()


def inject_dependency_fault(charm_file: str | Path) -> None:
    """Inject a dependency fault into the mysql charm."""
    with Path("refresh_versions.toml").open("rb") as file:
        versions = tomli.load(file)

    versions["charm"] = "8.4/0.0.0"
    versions["snap"]["revisions"][platform.machine()] = "1"

    # Overwrite refresh_versions.toml with incompatible version.
    with zipfile.ZipFile(charm_file, mode="a") as charm_zip:
        charm_zip.writestr("refresh_versions.toml", tomli_w.dumps(versions))
