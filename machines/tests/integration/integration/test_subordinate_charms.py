# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test charms subordinated to MySQL charm."""

import logging
import os

import jubilant
from jubilant import Juju

from ..helpers_ha import MINUTE_SECS

logger = logging.getLogger(__name__)

DATABASE_APP_NAME = "mysql"
APPLICATION_APP_NAME = "mysql-test-app"
UBUNTU_PRO_APP_NAME = "ubuntu-advantage"
LANDSCAPE_CLIENT_APP_NAME = "landscape-client"


def test_ubuntu_pro(juju: Juju, charm):
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        config={"cluster-name": "test_cluster", "profile": "testing"},
        base="ubuntu@24.04",
        trust=True,
    )
    juju.deploy(
        APPLICATION_APP_NAME,
        APPLICATION_APP_NAME,
        channel="latest/edge",
        base="ubuntu@22.04",
    )
    juju.deploy(
        UBUNTU_PRO_APP_NAME,
        UBUNTU_PRO_APP_NAME,
        channel="latest/stable",
        config={"token": os.environ["UBUNTU_PRO_TOKEN"]},
        base="ubuntu@24.04",
    )

    juju.integrate(f"{DATABASE_APP_NAME}:database", f"{APPLICATION_APP_NAME}:database")
    juju.integrate(DATABASE_APP_NAME, UBUNTU_PRO_APP_NAME)

    juju.wait(
        jubilant.all_active,
        timeout=15 * MINUTE_SECS,
    )


def test_landscape_client(juju: Juju):
    juju.deploy(
        LANDSCAPE_CLIENT_APP_NAME,
        LANDSCAPE_CLIENT_APP_NAME,
        channel="latest/stable",
        config={
            "account-name": os.environ["LANDSCAPE_ACCOUNT_NAME"],
            "registration-key": os.environ["LANDSCAPE_REGISTRATION_KEY"],
            "ppa": "ppa:landscape/self-hosted-beta",
        },
        base="ubuntu@24.04",
    )
    juju.integrate(DATABASE_APP_NAME, LANDSCAPE_CLIENT_APP_NAME)

    juju.wait(
        jubilant.all_active,
        timeout=15 * MINUTE_SECS,
    )
