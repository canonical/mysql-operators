# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging

import jubilant
from jubilant import Juju

from constants import REPLICATION_USERNAME

from ..helpers import (
    is_connection_possible,
)
from ..helpers_ha import (
    MINUTE_SECS,
    get_app_units,
    get_mysql_server_credentials,
    get_unit_info,
    get_unit_ip,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

APP_NAME = "mysql"
TLS_APP_NAME = "self-signed-certificates"
CLUSTER_NAME = "test_cluster"
TIMEOUT = 15 * MINUTE_SECS

config = {}


def test_build_and_deploy(juju: Juju, charm) -> None:
    """Build the charm and deploy 3 units to ensure a cluster is formed."""
    logger.info(f"Deploying {APP_NAME}")
    juju.deploy(
        charm,
        APP_NAME,
        base="ubuntu@24.04",
        config={"cluster-name": CLUSTER_NAME, "profile": "testing"},
        num_units=3,
        trust=True,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME),
        timeout=TIMEOUT,
    )


def test_connection_before_tls(juju: Juju) -> None:
    """Ensure connections (with and without ssl) are possible before relating with TLS operator."""
    app_units = get_app_units(juju, APP_NAME)

    # set global config dict once
    global config
    password = get_mysql_server_credentials(juju, app_units[0], REPLICATION_USERNAME)["password"]
    config = {
        "username": REPLICATION_USERNAME,
        "password": password,
    }

    # Before relating to TLS charm both encrypted and unencrypted connection should be possible
    logger.info("Asserting connections before relation")
    for unit_name in app_units:
        unit_ip = get_unit_ip(juju, APP_NAME, unit_name)
        config["host"] = unit_ip

        assert is_connection_possible(config, **{"ssl_disabled": False}), (
            f"❌ Encrypted connection not possible to unit {unit_name} with disabled TLS"
        )

        assert is_connection_possible(config, **{"ssl_disabled": True}), (
            f"❌ Unencrypted connection not possible to unit {unit_name} with disabled TLS"
        )


def test_enable_tls(juju: Juju) -> None:
    """Test for encryption enablement when relation to TLS charm."""
    app_units = get_app_units(juju, APP_NAME)

    # Deploy TLS Certificates operator.
    logger.info("Deploy TLS operator")
    juju.deploy(
        TLS_APP_NAME,
        channel="1/stable",
        config={"ca-common-name": "Test CA"},
        base="ubuntu@24.04",
    )
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, TLS_APP_NAME),
        timeout=TIMEOUT,
    )

    # Relate with TLS charm
    logger.info("Relate to TLS operator")
    juju.integrate(f"{APP_NAME}:client-certificates", f"{TLS_APP_NAME}:certificates")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
        delay=5,
    )

    juju.integrate(f"{APP_NAME}:peer-certificates", f"{TLS_APP_NAME}:certificates")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
        delay=5,
    )

    # After relating to only encrypted connection should be possible
    logger.info("Asserting connections after relation")
    for unit_name in app_units:
        unit_ip = get_unit_ip(juju, APP_NAME, unit_name)
        config["host"] = unit_ip
        assert is_connection_possible(config, **{"ssl_disabled": False}), (
            f"❌ Encrypted connection not possible to unit {unit_name} with enabled TLS"
        )

        assert not is_connection_possible(config, **{"ssl_disabled": True}), (
            f"❌ Unencrypted connection possible to unit {unit_name} with enabled TLS"
        )

    # test for ca presence in a given unit
    logger.info("Assert TLS file exists")
    assert get_tls_ca(juju, app_units[0]), "❌ No CA found after TLS relation"


def test_disable_tls(juju: Juju) -> None:
    # Remove the relation
    app_units = get_app_units(juju, APP_NAME)

    logger.info("Removing relation")
    juju.remove_relation(f"{APP_NAME}:client-certificates", f"{TLS_APP_NAME}:certificates")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
        delay=5,
    )

    juju.remove_relation(f"{APP_NAME}:peer-certificates", f"{TLS_APP_NAME}:certificates")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
        delay=5,
    )

    # After relation removal both encrypted and unencrypted connection should be possible
    for unit_name in app_units:
        unit_ip = get_unit_ip(juju, APP_NAME, unit_name)
        config["host"] = unit_ip
        assert is_connection_possible(config, **{"ssl_disabled": False}), (
            f"❌ Encrypted connection not possible to unit {unit_name} after relation removal"
        )

        assert is_connection_possible(config, **{"ssl_disabled": True}), (
            f"❌ Unencrypted connection not possible to unit {unit_name} after relation removal"
        )


def get_tls_ca(juju: Juju, unit_name: str) -> str:
    """Returns the TLS CA used by the unit.

    Args:
        juju: The Juju instance
        unit_name: The name of the unit

    Returns:
        TLS CA or an empty string if there is no CA.
    """
    unit_info = get_unit_info(juju, unit_name)
    if not unit_info:
        raise ValueError(f"no unit info could be grabbed for {unit_name}")

    # Filter the data based on the relation name.
    relation_data = [
        v for v in unit_info[unit_name]["relation-info"] if v["endpoint"] == "client-certificates"
    ]
    if len(relation_data) == 0:
        return ""
    return json.loads(relation_data[0]["application-data"]["certificates"])[0].get("ca")
