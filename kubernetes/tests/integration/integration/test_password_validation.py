#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju, TaskError

from constants import CLUSTER_ADMIN_USERNAME, PASSWORD_LENGTH
from utils import generate_random_password

from ..helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    get_mysql_primary_unit,
    get_mysql_server_credentials,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

DATABASE_APP_NAME = "mysql-k8s"
CLUSTER_NAME = "test_cluster"
TIMEOUT = 15 * MINUTE_SECS


def test_build_and_deploy(juju: Juju, charm) -> None:
    """Build the mysql charm and deploy it with 3 units."""
    logger.info(f"Deploying {DATABASE_APP_NAME} with 3 units")
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        base="ubuntu@22.04",
        config={"cluster-name": CLUSTER_NAME, "profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=3,
        trust=True,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        timeout=TIMEOUT,
    )


def test_password_too_short_fails(juju: Juju) -> None:
    """Test that a password with less than 24 characters fails."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, CLUSTER_ADMIN_USERNAME)
    old_password = old_credentials["password"]

    short_password = generate_random_password(20)
    logger.info(f"Attempting to set short password with length {len(short_password)}")

    try:
        juju.run(
            unit=primary_unit_name,
            action="set-password",
            params={"username": CLUSTER_ADMIN_USERNAME, "password": short_password},
        )
    except TaskError as e:
        logger.info(f"Action failed as expected with exception: {e}")
    else:
        raise AssertionError("set-password task should have failed")

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, CLUSTER_ADMIN_USERNAME)
    new_password = new_credentials["password"]

    assert new_password == old_password, (
        f"Password should not have changed with a short password. "
        f"Expected password to remain: {old_password[:5]}..., but got: {new_password[:5]}..."
    )


def test_password_only_lowercase_fails(juju: Juju) -> None:
    """Test that a password with only lowercase letters fails."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, CLUSTER_ADMIN_USERNAME)
    old_password = old_credentials["password"]

    # Create a password with more than 24 characters but only lowercase letters
    lowercase_password = (
        "verylonglowercasepasswordverylonglowercasepasswordverylonglowercasepassword"
    )
    logger.info(f"Attempting to set lowercase-only password with length {len(lowercase_password)}")

    try:
        juju.run(
            unit=primary_unit_name,
            action="set-password",
            params={"username": CLUSTER_ADMIN_USERNAME, "password": lowercase_password},
        )
    except Exception as e:
        logger.info(f"Action failed as expected with exception: {e}")
    else:
        raise AssertionError("set-password task should have failed")

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, CLUSTER_ADMIN_USERNAME)
    new_password = new_credentials["password"]

    assert new_password == old_password, (
        f"Password should not have changed with a lowercase-only password. "
        f"Expected password to remain: {old_password[:5]}..., but got: {new_password[:5]}..."
    )


def test_password_valid_succeeds(juju: Juju) -> None:
    """Test that a valid password with 24 chars, mixed case and numbers succeeds."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, CLUSTER_ADMIN_USERNAME)
    old_password = old_credentials["password"]

    valid_password = generate_random_password(PASSWORD_LENGTH)

    logger.info(
        f"Attempting to set valid password with length {len(valid_password)}: {valid_password}"
    )

    juju.run(
        unit=primary_unit_name,
        action="set-password",
        params={"username": CLUSTER_ADMIN_USERNAME, "password": valid_password},
    )

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, CLUSTER_ADMIN_USERNAME)
    new_password = new_credentials["password"]

    assert new_password != old_password, "Password should have changed with a valid password"
    assert new_password == valid_password, (
        f"Password should match the set password. Expected: {valid_password}, Got: {new_password}"
    )
