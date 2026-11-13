# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant_backports
from jubilant_backports import Juju

from ...helpers import generate_random_string
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_instances_online,
    get_app_units,
    get_mysql_variable_value,
    insert_mysql_test_data,
    remove_mysql_test_data,
    verify_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TABLE_NAME = "restart_during_scale_up"

# Changing the audit log strategy requires a mysqld restart,
# without the memory footprint of changing the buffer pool size
AUDIT_STRATEGY_CONFIG = "plugin-audit-strategy"
AUDIT_STRATEGY_VALUES = {
    "async": "ASYNCHRONOUS",
    "semi-async": "SEMISYNCHRONOUS",
}

MINUTE_SECS = 60


def test_deploy_single_unit(juju: Juju, charm: str) -> None:
    """Deploy a single unit MySQL cluster."""
    logging.info("Deploying single unit MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@22.04",
        config={"profile": "testing", AUDIT_STRATEGY_CONFIG: "async"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=1,
        trust=True,
    )

    logging.info("Wait for application to become active")
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )


def test_restart_during_scale_up(juju: Juju) -> None:
    """Restart the single cluster member while the application scales up.

    Units are added before the config change, so the restart callback runs
    while Juju already plans 3 units but the cluster only has 1 member.
    The restarted member must reboot the cluster, letting the new units join.
    """
    table_value = generate_random_string(255)
    insert_mysql_test_data(juju, MYSQL_APP_NAME, MYSQL_TABLE_NAME, table_value)

    logging.info("Scaling up and changing a restart-requiring config")
    juju.add_unit(MYSQL_APP_NAME, num_units=2)
    juju.config(MYSQL_APP_NAME, {AUDIT_STRATEGY_CONFIG: "semi-async"})

    juju.wait(
        ready=lambda status: len(status.apps[MYSQL_APP_NAME].units) == 3,
        timeout=5 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
        error=jubilant_backports.any_blocked,
        timeout=20 * MINUTE_SECS,
    )

    assert check_mysql_instances_online(juju, MYSQL_APP_NAME), "Not all instances online"
    verify_mysql_test_data(juju, MYSQL_APP_NAME, MYSQL_TABLE_NAME, table_value)
    check_audit_strategy(juju, "semi-async")

    remove_mysql_test_data(juju, MYSQL_APP_NAME, MYSQL_TABLE_NAME)


def test_rolling_restart_multi_unit(juju: Juju) -> None:
    """Rolling restart the cluster members through a config change."""
    table_value = generate_random_string(255)
    insert_mysql_test_data(juju, MYSQL_APP_NAME, MYSQL_TABLE_NAME, table_value)

    logging.info("Changing a restart-requiring config")
    juju.config(MYSQL_APP_NAME, {AUDIT_STRATEGY_CONFIG: "async"})

    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
        error=jubilant_backports.any_blocked,
        timeout=20 * MINUTE_SECS,
    )

    assert check_mysql_instances_online(juju, MYSQL_APP_NAME), "Not all instances online"
    verify_mysql_test_data(juju, MYSQL_APP_NAME, MYSQL_TABLE_NAME, table_value)
    check_audit_strategy(juju, "async")

    remove_mysql_test_data(juju, MYSQL_APP_NAME, MYSQL_TABLE_NAME)


def check_audit_strategy(juju: Juju, config_value: str) -> None:
    """Check every unit runs with the given audit strategy, proving the restart."""
    for unit_name in get_app_units(juju, MYSQL_APP_NAME):
        value = get_mysql_variable_value(juju, MYSQL_APP_NAME, unit_name, "audit_log_strategy")
        assert value == AUDIT_STRATEGY_VALUES[config_value], f"{unit_name} not restarted"
