#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import jubilant_backports
from jubilant_backports import Juju

from ...helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    get_app_units,
    get_mysql_variable_value,
    load_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"


def test_build_and_deploy(juju: Juju, charm) -> None:
    """Build the mysql charm and deploy it."""
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

    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME),
        error=jubilant_backports.any_blocked,
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_custom_variables(juju: Juju) -> None:
    """Query database for custom variables."""
    app_units = get_app_units(juju, MYSQL_APP_NAME)

    custom_vars = {}
    custom_vars["max_connections"] = 100
    custom_vars["innodb_buffer_pool_size"] = 20971520
    custom_vars["innodb_buffer_pool_chunk_size"] = 1048576
    custom_vars["group_replication_message_cache_size"] = 134217728

    for unit_name in app_units:
        for k, v in custom_vars.items():
            logging.info(f"Checking that {k} is set to {v} on {unit_name}")
            value = get_mysql_variable_value(juju, MYSQL_APP_NAME, unit_name, k)
            assert int(value) == v, f"Variable {k} is not set to {v}"
