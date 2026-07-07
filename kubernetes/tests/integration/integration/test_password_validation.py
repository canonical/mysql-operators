#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
import pytest
from jubilant import Juju, TaskError

from constants import MAX_PASSWORD_LENGTH, REPLICATION_USERNAME
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
        base="ubuntu@26.04",
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
    """Test that a password with less than 12 characters fails."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    old_password = old_credentials["password"]

    short_password = generate_random_password(8)
    logger.info(f"Attempting to set short password with length {len(short_password)}")

    with pytest.raises(TaskError) as excinfo:
        juju.run(
            unit=primary_unit_name,
            action="set-password",
            params={"username": REPLICATION_USERNAME, "password": short_password},
        )
    assert "MySQLUpdateUserError" in str(excinfo.value)

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    new_password = new_credentials["password"]

    assert new_password == old_password, (
        f"Password should not have changed with a short password. "
        f"Expected password to remain: {old_password[:5]}..., but got: {new_password[:5]}..."
    )


def test_password_too_long_fails(juju: Juju) -> None:
    """Test that a password with less than 24 characters fails."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    old_password = old_credentials["password"]

    short_password = generate_random_password(MAX_PASSWORD_LENGTH + 1)
    logger.info(f"Attempting to set exceedingly long password with length {len(short_password)}")

    with pytest.raises(TaskError) as excinfo:
        juju.run(
            unit=primary_unit_name,
            action="set-password",
            params={"username": REPLICATION_USERNAME, "password": short_password},
        )
    assert "MySQLUpdateUserError" in str(excinfo.value)

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    new_password = new_credentials["password"]

    assert new_password == old_password, (
        f"Password should not have changed with an exceedingly long password. "
        f"Expected password to remain: {old_password[:5]}..., but got: {new_password[:5]}..."
    )


def test_password_only_lowercase_fails(juju: Juju) -> None:
    """Test that a password with only lowercase letters fails."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    old_password = old_credentials["password"]

    # Create a password with more than 24 characters but only lowercase letters
    lowercase_password = (
        "verylonglowercasepasswordverylonglowercasepasswordverylonglowercasepassword"
    )
    logger.info(f"Attempting to set lowercase-only password with length {len(lowercase_password)}")

    with pytest.raises(TaskError) as excinfo:
        juju.run(
            unit=primary_unit_name,
            action="set-password",
            params={"username": REPLICATION_USERNAME, "password": lowercase_password},
        )
    assert "MySQLUpdateUserError" in str(excinfo.value)

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    new_password = new_credentials["password"]

    assert new_password == old_password, (
        f"Password should not have changed with a lowercase-only password. "
        f"Expected password to remain: {old_password[:5]}..., but got: {new_password[:5]}..."
    )


def test_password_valid_succeeds(juju: Juju) -> None:
    """Test that a valid password with 12 chars, mixed case and numbers succeeds."""
    primary_unit_name = get_mysql_primary_unit(juju, DATABASE_APP_NAME)

    old_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    old_password = old_credentials["password"]

    valid_password = generate_random_password(12)

    logger.info(
        f"Attempting to set valid password with length {len(valid_password)}: {valid_password}"
    )

    juju.run(
        unit=primary_unit_name,
        action="set-password",
        params={"username": REPLICATION_USERNAME, "password": valid_password},
    )

    new_credentials = get_mysql_server_credentials(juju, primary_unit_name, REPLICATION_USERNAME)
    new_password = new_credentials["password"]

    assert new_password != old_password, "Password should have changed with a valid password"
    assert new_password == valid_password, (
        f"Password should match the set password. Expected: {valid_password}, Got: {new_password}"
    )
