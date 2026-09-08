# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju

from ... import architecture
from ...helpers_ha import (
    check_mysql_units_writes_increment,
    get_app_leader,
    get_mysql_primary_unit,
    refresh_mysql_server,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TEST_APP_NAME = "mysql-test-app"
MYSQL_ROUTER_APP_NAME = "mysql-router-k8s"

MINUTE_SECS = 60


def test_deploy_latest(juju: Juju) -> None:
    """Deploy MySQL, mysql-router-k8s, and mysql-test-app with a router-mediated relation."""
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
    juju.deploy(
        charm=MYSQL_ROUTER_APP_NAME,
        app=MYSQL_ROUTER_APP_NAME,
        base="ubuntu@26.04",
        channel="8.4/candidate",
        num_units=1,
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

    logging.info("Relating applications through the router")
    juju.integrate(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_ROUTER_APP_NAME}:backend-database",
    )
    juju.integrate(
        f"{MYSQL_TEST_APP_NAME}:database",
        f"{MYSQL_ROUTER_APP_NAME}:database",
    )

    logging.info("Wait for applications to become active")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant.all_active,
            MYSQL_APP_NAME,
            MYSQL_ROUTER_APP_NAME,
            MYSQL_TEST_APP_NAME,
        ),
        timeout=20 * MINUTE_SECS,
    )


def test_pre_refresh_check(juju: Juju) -> None:
    """Test that the pre-refresh-check action runs successfully."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)

    logging.info("Run pre-refresh-check action")
    juju.run(unit=mysql_leader, action="pre-refresh-check")

    logging.info("Assert primary is set to leader")
    mysql_primary = get_mysql_primary_unit(juju, MYSQL_APP_NAME)
    assert mysql_primary == mysql_leader, "Primary unit not set to leader"


def test_refresh_router_first(juju: Juju, charm: str, continuous_writes) -> None:
    """Refresh mysql-router-k8s first, then mysql-k8s, asserting writes increment after each."""
    logging.info("Ensure continuous writes are incrementing")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    logging.info("Refreshing mysql-router-k8s (candidate -> edge)")
    juju.refresh(app=MYSQL_ROUTER_APP_NAME, channel="8.4/edge")

    logging.info("Wait for refresh to complete")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant.all_active,
            MYSQL_APP_NAME,
            MYSQL_ROUTER_APP_NAME,
            MYSQL_TEST_APP_NAME,
        ),
        timeout=20 * MINUTE_SECS,
    )
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    logging.info("Refreshing mysql-k8s")
    refresh_mysql_server(juju, MYSQL_APP_NAME, charm)

    logging.info("Wait for all apps to be active")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant.all_active,
            MYSQL_APP_NAME,
            MYSQL_ROUTER_APP_NAME,
            MYSQL_TEST_APP_NAME,
        ),
        timeout=5 * MINUTE_SECS,
    )
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)
