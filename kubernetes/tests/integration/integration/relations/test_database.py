#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju

from ...helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    get_relation_data,
    wait_for_apps_status,
)

DATABASE_APP_NAME = CHARM_METADATA["name"]
DATABASE_ENDPOINT = "database"
APPLICATION_APP_NAME = "mysql-test-app"
APPLICATION_ENDPOINT = "database"

APPS = [DATABASE_APP_NAME, APPLICATION_APP_NAME]


def test_build_and_deploy(juju: Juju, charm):
    """Build the charm and deploy 3 units to ensure a cluster is formed."""
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        config={"cluster-name": "test_cluster", "profile": "testing"},
        num_units=3,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        base="ubuntu@24.04",
        trust=True,
    )

    juju.deploy(
        APPLICATION_APP_NAME,
        num_units=2,
        channel="latest/edge",
        base="ubuntu@22.04",
    )


def test_relation_creation_eager(juju: Juju):
    """Relate charms before they have time to properly start.

    It simulates a Terraform-like deployment strategy
    """
    logging.info("Creating relation...")
    juju.integrate(
        f"{APPLICATION_APP_NAME}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )

    logging.info("Waiting for application app to be waiting...")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_waiting, APPLICATION_APP_NAME),
        error=jubilant.any_blocked,
        timeout=15 * MINUTE_SECS,
    )
    logging.info("Waiting for database app to be active...")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        error=jubilant.any_blocked,
        timeout=15 * MINUTE_SECS,
    )


def test_relation_creation(juju: Juju):
    """Relate charms and wait for the expected changes in status."""
    juju.wait(
        ready=jubilant.all_active,
        timeout=15 * MINUTE_SECS,
    )

    relation_data = get_relation_data(juju, APPLICATION_APP_NAME, "database")
    assert not {"password", "username"} <= set(relation_data[0]["application-data"])
    assert "secret-user" in relation_data[0]["application-data"]


def test_relation_broken(juju: Juju):
    """Remove relation and wait for the expected changes in status."""
    juju.remove_relation(
        f"{APPLICATION_APP_NAME}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        error=jubilant.any_blocked,
        timeout=15 * MINUTE_SECS,
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_waiting, APPLICATION_APP_NAME),
        error=jubilant.any_blocked,
        timeout=15 * MINUTE_SECS,
    )
