# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
import os
import shutil
import zipfile
from contextlib import suppress
from pathlib import Path

import jubilant_backports
from jubilant_backports import Juju, TaskError

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    get_app_leader,
    get_app_units,
    get_k8s_stateful_set_partitions,
    get_mysql_primary_unit,
    get_mysql_variable_value,
    get_unit_by_number,
    get_unit_relation_data,
    load_mysql_test_data,
    wait_for_apps_status,
    wait_for_unit_message,
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
        base="ubuntu@22.04",
        channel="8.0/edge",
        config={"profile": "testing"},
        num_units=3,
        trust=True,
    )
    constraints = {"arch": architecture.architecture}
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
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
        ready=wait_for_apps_status(
            jubilant_backports.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME
        ),
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_pre_upgrade_check(juju: Juju) -> None:
    """Test that the pre-upgrade-check action runs successfully."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_units = get_app_units(juju, MYSQL_APP_NAME)

    logging.info("Run pre-upgrade-check action")
    juju.run(unit=mysql_leader, action="pre-upgrade-check")

    logging.info("Assert slow shutdown is enabled")
    for unit_name in mysql_units:
        value = get_mysql_variable_value(juju, MYSQL_APP_NAME, unit_name, "innodb_fast_shutdown")
        assert value == 0

    logging.info("Assert primary is set to leader")
    mysql_primary = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    assert mysql_primary == f"{MYSQL_APP_NAME}/0", "Primary unit not set to unit 0"

    logging.info("Assert partition is set to 2")
    assert get_k8s_stateful_set_partitions(juju, MYSQL_APP_NAME) == 2, "Partition not set to 2"


def test_upgrade_from_edge(juju: Juju, charm: str, continuous_writes) -> None:
    """Update the second cluster."""
    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    logging.info("Refresh the charm")
    juju.refresh(
        app=MYSQL_APP_NAME,
        path=charm,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
    )

    mysql_app_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_upgrade_unit = get_unit_by_number(juju, MYSQL_APP_NAME, 2)

    logging.info("Wait for upgrade to complete on first upgrading unit")
    juju.wait(
        ready=wait_for_unit_message(MYSQL_APP_NAME, mysql_upgrade_unit, "upgrade completed"),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Resume upgrade")
    while get_k8s_stateful_set_partitions(juju, MYSQL_APP_NAME) == 2:
        # ignore action return error as it is expected when
        # the leader unit is the next one to be upgraded
        # due it being immediately rolled when the partition
        # is patched in the stateful set
        with suppress(TaskError):
            juju.run(unit=mysql_app_leader, action="resume-upgrade")

    logging.info("Wait for upgrade to complete")
    juju.wait(
        ready=lambda status: jubilant_backports.all_active(status, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)


def test_relation_through_router(juju: Juju) -> None:
    """Test that a fresh relation routed through mysql-router-k8s works after upgrade."""
    logging.info("Removing pre-existing direct relation to mysql-test-app")
    juju.remove_relation(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    logging.info("Waiting for mysql-test-app to be blocked (no database)")
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_blocked, MYSQL_TEST_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Deploying mysql-router-k8s")
    constraints = {"arch": architecture.architecture}
    juju.deploy(
        charm=MYSQL_ROUTER_APP_NAME,
        app=MYSQL_ROUTER_APP_NAME,
        base="ubuntu@22.04",
        channel="8.0/edge",
        num_units=1,
        trust=True,
        constraints=constraints,
    )

    logging.info("Waiting for router unit to be waiting (no backend relation yet)")
    router_units = get_app_units(juju, MYSQL_ROUTER_APP_NAME)
    juju.wait(
        ready=lambda status: all(
            wait_for_unit_status(MYSQL_ROUTER_APP_NAME, unit_name, "waiting")(status)
            for unit_name in router_units
        ),
        timeout=10 * MINUTE_SECS,
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
            jubilant_backports.all_active,
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
    """Test an upgrade failure and its rollback."""
    mysql_app_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_app_units = get_app_units(juju, MYSQL_APP_NAME)
    mysql_upgrade_unit = get_unit_by_number(juju, MYSQL_APP_NAME, 2)

    logging.info("Run pre-upgrade-check action")
    juju.run(unit=mysql_app_leader, action="pre-upgrade-check")

    tmp_folder = Path("tmp")
    tmp_folder.mkdir(exist_ok=True)
    tmp_folder_charm = Path(tmp_folder, charm).absolute()

    shutil.copy(charm, tmp_folder_charm)

    logging.info("Inject dependency fault")
    inject_dependency_fault(juju, mysql_app_leader, tmp_folder_charm)

    logging.info("Refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=tmp_folder_charm)

    logging.info("Wait for upgrade to fail on first upgrading unit")
    juju.wait(
        ready=wait_for_unit_status(MYSQL_APP_NAME, mysql_upgrade_unit, "blocked"),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes on remaining units")
    mysql_remaining_units = [unit for unit in mysql_app_units if unit != mysql_upgrade_unit]
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME, mysql_remaining_units)

    logging.info("Re-run pre-upgrade-check action")
    juju.run(unit=mysql_app_leader, action="pre-upgrade-check")

    logging.info("Re-refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=charm)

    logging.info("Wait for upgrade to complete on first upgrading unit")
    juju.wait(
        ready=wait_for_unit_message(MYSQL_APP_NAME, mysql_upgrade_unit, "upgrade completed"),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Resume upgrade")
    while get_k8s_stateful_set_partitions(juju, MYSQL_APP_NAME) == 2:
        # ignore action return error as it is expected when
        # the leader unit is the next one to be upgraded
        # due it being immediately rolled when the partition
        # is patched in the stateful set
        with suppress(TaskError):
            juju.run(unit=mysql_app_leader, action="resume-upgrade")

    logging.info("Wait for upgrade to recover")
    juju.wait(
        ready=lambda status: jubilant_backports.all_active(status, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure continuous writes after rollback procedure")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME, mysql_app_units)

    # Remove fault charm file
    tmp_folder_charm.unlink()


def inject_dependency_fault(juju: Juju, unit_name: str, charm_file: str | Path) -> None:
    """Inject a dependency fault into the mysql charm."""
    # Open dependency.json and load current charm version
    with open("src/dependency.json") as dependency_file:
        current_charm_version = json.load(dependency_file)["charm"]["version"]

    # Query running dependency to overwrite with incompatible version
    relation_data = get_unit_relation_data(juju, unit_name, "upgrade")

    loaded_dependency_dict = json.loads(relation_data["application-data"]["dependencies"])
    loaded_dependency_dict["charm"]["upgrade_supported"] = f">{current_charm_version}"
    loaded_dependency_dict["charm"]["version"] = "999.999.999"

    # Overwrite dependency.json with incompatible version
    with zipfile.ZipFile(charm_file, mode="a") as charm_zip:
        charm_zip.writestr("src/dependency.json", json.dumps(loaded_dependency_dict))
