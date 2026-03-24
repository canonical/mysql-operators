# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

import jubilant
import pytest
from jubilant import Juju

from ... import architecture, markers
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    get_app_leader,
    get_app_units,
    get_mysql_primary_unit,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


@contextmanager
def continuous_writes(juju: Juju) -> Generator:
    """Starts continuous writes to the MySQL cluster for a test and clear the writes at the end."""
    test_app_leader = get_app_leader(juju, MYSQL_TEST_APP_NAME)

    logging.info("Clearing continuous writes")
    juju.run(test_app_leader, "clear-continuous-writes")
    logging.info("Starting continuous writes")
    juju.run(test_app_leader, "start-continuous-writes")

    yield

    logging.info("Clearing continuous writes")
    juju.run(test_app_leader, "clear-continuous-writes")


@markers.amd64_only
def test_refresh_from_stable_amd(juju: Juju, charm: str):
    """Simple test to ensure that all MySQL stable revisions can be upgraded."""
    image = os.getenv("MYSQL_IMAGE")
    revision = os.getenv("CHARM_REVISION_AMD64")
    if revision is None:
        pytest.skip(f"No revision for {architecture.architecture} architecture")

    deploy_stable(juju, int(revision), image)
    run_refresh_check(juju)

    with continuous_writes(juju):
        refresh_from_stable(juju, charm)


@markers.arm64_only
def test_refresh_from_stable_arm(juju: Juju, charm: str):
    """Simple test to ensure that all MySQL stable revisions can be upgraded."""
    image = os.getenv("MYSQL_IMAGE")
    revision = os.getenv("CHARM_REVISION_ARM64")
    if revision is None:
        pytest.skip(f"No revision for {architecture.architecture} architecture")

    deploy_stable(juju, int(revision), image)
    run_refresh_check(juju)

    with continuous_writes(juju):
        refresh_from_stable(juju, charm)


# TODO: add s390x test


def deploy_stable(juju: Juju, revision: int, image: str) -> None:
    """Ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=MYSQL_APP_NAME,
        app=MYSQL_APP_NAME,
        base="ubuntu@24.04",
        channel="8.4/stable",
        config={"profile": "testing"},
        resources={"mysql-image": image},
        revision=revision,
        num_units=3,
        trust=True,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@24.04",
        channel="latest/edge",
        num_units=1,
        trust=False,
    )

    juju.integrate(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    logging.info("Wait for applications to become active")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME),
        error=jubilant.any_blocked,
        timeout=20 * MINUTE_SECS,
    )


def run_refresh_check(juju: Juju) -> None:
    """Test that the pre-refresh-check action runs successfully."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)

    logging.info("Run pre-refresh-check action")
    juju.run(unit=mysql_leader, action="pre-refresh-check")

    logging.info("Assert primary is set to leader")
    mysql_primary = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    assert mysql_primary == f"{MYSQL_APP_NAME}/0", "Primary unit not set to unit 0"


def refresh_from_stable(juju: Juju, charm: str) -> None:
    """Refresh the cluster."""
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
        timeout=10 * MINUTE_SECS,
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
