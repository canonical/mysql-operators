#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant_backports
from jubilant_backports import Juju

from ... import markers
from ...architecture import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    get_app_leader,
    get_unit_relation_data,
    wait_for_apps_status,
    wait_for_unit_status,
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
        base="ubuntu@22.04",
        trust=True,
    )

    constraints = {"arch": architecture}
    juju.deploy(
        APPLICATION_APP_NAME,
        num_units=2,
        channel="latest/edge",
        base="ubuntu@22.04",
        constraints=constraints,
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

    logging.info("Waiting for apps to be active...")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant_backports.all_active,
            DATABASE_APP_NAME,
            APPLICATION_APP_NAME,
        ),
        timeout=15 * MINUTE_SECS,
    )


@markers.only_without_juju_secrets
def test_relation_creation_databag(juju: Juju):
    """Relate charms and wait for the expected changes in status."""
    juju.wait(
        ready=jubilant_backports.all_active,
        timeout=15 * MINUTE_SECS,
    )

    app_leader = get_app_leader(juju, APPLICATION_APP_NAME)
    relation_data = get_unit_relation_data(juju, app_leader, "database")

    assert {"password", "username"} <= set(relation_data["application-data"])


@markers.only_with_juju_secrets
def test_relation_creation(juju: Juju):
    """Relate charms and wait for the expected changes in status."""
    juju.wait(
        ready=jubilant_backports.all_active,
        timeout=15 * MINUTE_SECS,
    )

    app_leader = get_app_leader(juju, APPLICATION_APP_NAME)
    relation_data = get_unit_relation_data(juju, app_leader, "database")

    assert not {"password", "username"} <= set(relation_data["application-data"])
    assert "secret-user" in relation_data["application-data"]


def test_relation_broken(juju: Juju):
    """Remove relation and wait for the expected changes in status."""
    juju.remove_relation(
        f"{APPLICATION_APP_NAME}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )

    logging.info("Wait for change in application statuses")
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, DATABASE_APP_NAME),
        timeout=5 * MINUTE_SECS,
    )
    # juju-2.9 has inconsistent app and unit status
    # use unit status
    juju.wait(
        ready=wait_for_unit_status(
            APPLICATION_APP_NAME,
            f"{APPLICATION_APP_NAME}/0",
            "blocked",
        ),
        timeout=5 * MINUTE_SECS,
    )

    juju.remove_application(APPLICATION_APP_NAME, destroy_storage=True, force=True)


def test_relation_broken_connectivity(juju: Juju):
    """Remove one out of multiple relation and check expected connectivity."""
    test_app_1 = f"{APPLICATION_APP_NAME}1"
    test_app_2 = f"{APPLICATION_APP_NAME}2"

    logging.info("Deploying applications...")
    juju.deploy(
        APPLICATION_APP_NAME,
        test_app_1,
        num_units=1,
        channel="latest/edge",
        config={"database_name": "test_database_1"},
        base="ubuntu@22.04",
    )

    juju.deploy(
        APPLICATION_APP_NAME,
        test_app_2,
        num_units=1,
        channel="latest/edge",
        config={"database_name": "test_database_2"},
        base="ubuntu@22.04",
    )

    logging.info("Creating relations...")
    juju.integrate(
        f"{test_app_1}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )
    juju.integrate(
        f"{test_app_2}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )

    logging.info("Waiting for application app to be active...")
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, test_app_1, test_app_2),
        timeout=15 * MINUTE_SECS,
        delay=2,
    )

    logging.info("Removing relation...")
    juju.remove_relation(
        f"{test_app_2}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )

    juju.run(f"{test_app_1}/0", "clear-continuous-writes")
    juju.run(f"{test_app_1}/0", "start-continuous-writes")
