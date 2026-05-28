#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


import jubilant
from jubilant import Juju

from .. import markers

MYSQL_APP_NAME = "myqsl"


@markers.amd64_only
def test_arm_charm_on_amd_host(juju: Juju) -> None:
    """Tries deploying an arm64 charm on amd64 host."""
    charm = "./mysql_ubuntu@26.04-arm64.charm"

    juju.deploy(
        charm,
        MYSQL_APP_NAME,
        num_units=1,
        config={"profile": "testing"},
        base="ubuntu@26.04",
    )

    juju.wait(ready=jubilant.all_error, timeout=300)


@markers.arm64_only
def test_amd_charm_on_arm_host(juju: Juju) -> None:
    """Tries deploying an amd64 charm on arm64 host."""
    charm = "./mysql_ubuntu@26.04-amd64.charm"

    juju.deploy(
        charm,
        MYSQL_APP_NAME,
        num_units=1,
        config={"profile": "testing"},
        base="ubuntu@26.04",
    )

    juju.wait(ready=jubilant.all_error, timeout=300)


# TODO: add s390x test
