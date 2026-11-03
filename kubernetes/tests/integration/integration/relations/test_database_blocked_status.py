#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Regression tests for https://github.com/canonical/mysql-operators/issues/327.

When `database-relation-changed` fails midway, the charm must remain blocked
while the situation persists: `update-status` must not silently clear the
blocked status of a relation whose setup never completed.
"""

import logging
import time

import jubilant
from jubilant import Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    wait_for_apps_status,
)

DATABASE_APP_NAME = CHARM_METADATA["name"]
DATABASE_ENDPOINT = "database"
APPLICATION_APP_NAME = "mysql-test-app"
APPLICATION_ENDPOINT = "database"

# MySQL identifiers are limited to 64 characters: requesting a longer database
# name makes `create_database` fail on the provider, which sets a blocked status
# without ever publishing credentials or endpoints to the relation.
INVALID_DATABASE_NAME = "a" * 65

UPDATE_STATUS_INTERVAL = "15s"


def test_build_and_deploy(juju: Juju, charm):
    """Build the charm and deploy one provider and one consumer unit."""
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        config={"cluster-name": "test_cluster", "profile": "testing"},
        num_units=1,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        storage={"data": "500M", "archive": "250M", "logs": "250M", "temp": "250M"},
        base="ubuntu@26.04",
        trust=True,
    )

    constraints = {"arch": architecture.architecture}
    juju.deploy(
        APPLICATION_APP_NAME,
        num_units=1,
        channel="latest/edge",
        config={"database_name": INVALID_DATABASE_NAME},
        base="ubuntu@26.04",
        constraints=constraints,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        timeout=15 * MINUTE_SECS,
    )


def test_failed_database_setup_retains_blocked_status(juju: Juju):
    """A failed database setup must not be silently cleared by update-status."""
    juju.integrate(
        f"{APPLICATION_APP_NAME}:{APPLICATION_ENDPOINT}",
        f"{DATABASE_APP_NAME}:{DATABASE_ENDPOINT}",
    )

    logging.info("Waiting for database app to be blocked...")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_blocked, DATABASE_APP_NAME),
        timeout=15 * MINUTE_SECS,
    )

    # Speed up update-status so that several cycles run within the test.
    juju.model_config({"update-status-hook-interval": UPDATE_STATUS_INTERVAL})

    # Without the fix, update-status re-derives the unit status from the
    # (healthy) cluster state and overwrites `blocked` with `active`, even
    # though the relation setup never completed.
    logging.info("Letting several update-status cycles run...")
    time.sleep(3 * 60)

    status = juju.status()
    units = status.apps[DATABASE_APP_NAME].units
    leader_unit = next(unit for unit, info in units.items() if info.leader)
    unit_status = units[leader_unit].workload_status

    try:
        assert unit_status.current == "blocked", (
            f"Expected {leader_unit} to remain blocked after a failed relation "
            f"setup, got '{unit_status.current}: {unit_status.message}'"
        )
        assert "Failed to create database" in unit_status.message
    finally:
        juju.model_config(reset="update-status-hook-interval")
