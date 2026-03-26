#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from time import sleep

import jubilant_backports
from jubilant_backports import Juju

from ... import architecture
from ...helpers_ha import (
    MINUTE_SECS,
    execute_queries_on_unit,
    get_app_leader,
    get_mysql_primary_unit,
    get_mysql_server_credentials,
    get_unit_ip,
    wait_for_apps_status,
)

DATABASE_APP_NAME = "mysql"
MYSQL_ROUTER_APP_NAME = "mysql-router"
MYSQL_TEST_APP_NAME = "mysql-test-app"

OLD_MYSQL_REVISIONS = {
    "amd64": 366,
    "arm64": 367,
}
OLD_MYSQL_REVISION = OLD_MYSQL_REVISIONS[architecture.architecture]

TIMEOUT = 10 * MINUTE_SECS


def test_build_and_deploy(juju: Juju) -> None:
    """Deploy an old MySQL revision without predefined roles support."""
    logging.info(f"Deploying MySQL cluster revision {OLD_MYSQL_REVISION}")
    juju.deploy(
        charm=DATABASE_APP_NAME,
        app=DATABASE_APP_NAME,
        base="ubuntu@22.04",
        channel="8.0/stable",
        revision=OLD_MYSQL_REVISION,
        config={"profile": "testing"},
        num_units=3,
    )
    # Allow some time between deploy and status call. Avoids:
    # ERROR getting details for storage database/0: filesystem for storage instance "database/0" not found
    sleep(30)

    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, DATABASE_APP_NAME),
        timeout=TIMEOUT,
    )


def test_verify_no_predefined_roles_in_old_revision(juju: Juju):
    """Verify that predefined roles don't exist in the old revision."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)
    primary_unit_address = get_unit_ip(juju, DATABASE_APP_NAME, primary_unit_name)
    server_config_credentials = get_mysql_server_credentials(juju, primary_unit_name)

    logging.info("Checking that predefined roles don't exist in old revision")
    rows = execute_queries_on_unit(
        primary_unit_address,
        server_config_credentials["username"],
        server_config_credentials["password"],
        [
            "SELECT user AS role_name FROM mysql.user "
            "WHERE account_locked='Y' AND password_expired='Y' AND authentication_string='' "
            "AND user IN ('mysqlrouter', 'charmed_router', 'charmed_read', 'charmed_dml', "
            "'charmed_ddl', 'charmed_dba', 'charmed_backup', 'charmed_stats')"
        ],
        commit=False,
    )

    predefined_roles = {
        "charmed_backup",
        "charmed_dba",
        "charmed_ddl",
        "charmed_dml",
        "charmed_read",
        "charmed_router",
        "charmed_stats",
        "mysqlrouter",
    }

    assert set(rows).isdisjoint(predefined_roles), (
        f"Expected no predefined roles in revision {OLD_MYSQL_REVISION}, but found: {rows}"
    )


def test_verify_predefined_roles_present_after_refresh(juju: Juju, charm):
    """Verify that predefined roles are present after refresh."""
    mysql_leader = get_app_leader(juju, DATABASE_APP_NAME)

    logging.info("Running pre-upgrade-check action")
    juju.run(unit=mysql_leader, action="pre-upgrade-check")

    logging.info("Refreshing MySQL to new charm with predefined roles support")
    juju.refresh(
        app=DATABASE_APP_NAME,
        path=charm,
    )

    logging.info("Wait for upgrade to start")
    juju.wait(
        ready=lambda status: jubilant_backports.any_maintenance(status, DATABASE_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Wait for upgrade to complete")
    juju.wait(
        ready=lambda status: jubilant_backports.all_active(status, DATABASE_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)
    primary_unit_address = get_unit_ip(juju, DATABASE_APP_NAME, primary_unit_name)
    server_config_credentials = get_mysql_server_credentials(juju, primary_unit_name)

    logging.info("Checking if predefined roles exist after refresh")
    rows = execute_queries_on_unit(
        primary_unit_address,
        server_config_credentials["username"],
        server_config_credentials["password"],
        ["SELECT user AS role_name FROM mysql.user"],
        commit=False,
    )

    expected_roles = {
        "charmed_backup",
        "charmed_dba",
        "charmed_ddl",
        "charmed_dml",
        "charmed_read",
        "charmed_router",
        "charmed_stats",
        "mysqlrouter",
    }

    existing_roles = set(rows)
    assert expected_roles <= set(existing_roles), (
        f"Expected roles {expected_roles} to be a subset of existing roles {existing_roles}"
    )


def test_integrate_mysql_router_and_test_app(juju: Juju):
    """Integrate MySQL Router with MySQL and verify they work."""
    logging.info("Deploying MySQL Router")
    juju.deploy(
        charm=MYSQL_ROUTER_APP_NAME,
        app=MYSQL_ROUTER_APP_NAME,
        base="ubuntu@22.04",
        channel="dpe/edge",
        num_units=1,
        trust=True,
    )

    logging.info("Deploying MySQL test application")
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
        channel="latest/edge",
        num_units=1,
        config={"database_name": "test"},
    )

    logging.info("Waiting for applications to be ready")
    juju.wait(
        ready=lambda status: all((
            jubilant_backports.all_agents_idle(status, MYSQL_ROUTER_APP_NAME),
            jubilant_backports.all_agents_idle(status, MYSQL_TEST_APP_NAME),
        )),
        timeout=TIMEOUT,
    )

    logging.info("Integrating mysql-router with mysql-test-app")
    juju.integrate(
        f"{MYSQL_ROUTER_APP_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    logging.info("Integrating mysql-router with mysql")
    juju.integrate(
        f"{MYSQL_ROUTER_APP_NAME}:backend-database",
        f"{DATABASE_APP_NAME}:database",
    )

    logging.info("Waiting for all apps to become active")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant_backports.all_active,
            DATABASE_APP_NAME,
            MYSQL_ROUTER_APP_NAME,
            MYSQL_TEST_APP_NAME,
        ),
        timeout=TIMEOUT,
    )
