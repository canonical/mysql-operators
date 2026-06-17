#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant_backports
from jubilant_backports import Juju

from .. import architecture
from ..helpers_ha import CHARM_METADATA, MINUTE_SECS, wait_for_apps_status, wait_for_unit_status

MYSQL_APP_NAME = "mysql"
SCALE_APPS = 7
SCALE_UNITS = 3


def test_build_and_deploy(juju: Juju, charm):
    """Build the charm and deploy 1 units to ensure a cluster is formed."""
    config = {"profile": "testing"}

    juju.deploy(
        charm,
        MYSQL_APP_NAME,
        config=config,
        num_units=1,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        base="ubuntu@22.04",
        trust=True,
    )

    constraints = {"arch": architecture.architecture}
    for idx in range(SCALE_APPS):
        juju.deploy(
            "mysql-test-app",
            f"app{idx}",
            num_units=1,
            channel="latest/edge",
            config={"database_name": f"database{idx}", "sleep_interval": "2000"},
            base="ubuntu@22.04",
            constraints=constraints,
        )
        juju.deploy(
            "mysql-router-k8s",
            f"router{idx}",
            num_units=1,
            channel="8.0/edge",
            trust=True,
            base="ubuntu@22.04",
            constraints=constraints,
        )

    # Wait until deployment is complete in attempt to reduce CPU stress
    logging.info("Wait for mysql")
    juju.wait(
        wait_for_apps_status(
            jubilant_backports.all_active,
            MYSQL_APP_NAME,
        ),
        delay=5.0,
        timeout=25 * MINUTE_SECS,
    )

    logging.info("Wait for app")
    juju.wait(
        ready=lambda status: all((
            *(
                wait_for_unit_status(f"app{idx}", unit_name, "blocked")(status)
                for idx in range(SCALE_APPS)
                for unit_name in status.get_units(f"app{idx}")
            ),
        )),
        delay=5.0,
        timeout=25 * MINUTE_SECS,
    )

    logging.info("Wait for mysql-router")
    juju.wait(
        ready=lambda status: all((
            *(
                wait_for_unit_status(f"router{idx}", unit_name, "waiting")(status)
                for idx in range(SCALE_APPS)
                for unit_name in status.get_units(f"router{idx}")
            ),
        )),
        delay=5.0,
        timeout=25 * MINUTE_SECS,
    )


def test_relate_all(juju: Juju):
    """Relate all the applications to the database."""
    logging.info("Relating all")
    for idx in range(SCALE_APPS):
        juju.integrate(f"{MYSQL_APP_NAME}:database", f"router{idx}:backend-database")
        juju.integrate(f"app{idx}:database", f"router{idx}:database")

    juju.wait(
        jubilant_backports.all_active,
        delay=5.0,
        timeout=25 * MINUTE_SECS,
    )


def test_scale_out(juju: Juju):
    """Scale database and routers."""
    juju.add_unit(MYSQL_APP_NAME, num_units=SCALE_UNITS - 1)
    for idx in range(SCALE_APPS):
        juju.add_unit(f"router{idx}", num_units=SCALE_UNITS - 1)

    juju.wait(
        jubilant_backports.all_active,
        delay=5.0,
        timeout=30 * MINUTE_SECS,
    )


def test_scale_in(juju: Juju):
    """Scale database and routers."""
    juju.remove_unit(MYSQL_APP_NAME, num_units=SCALE_UNITS - 1)
    for idx in range(SCALE_APPS):
        juju.remove_unit(f"router{idx}", num_units=SCALE_UNITS - 1)

    juju.wait(
        jubilant_backports.all_active,
        delay=5.0,
        timeout=15 * MINUTE_SECS,
    )
