# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging

import jubilant
from jubilant import Juju

from constants import REPLICATION_USERNAME

from ..helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    get_app_units,
    get_mysql_server_credentials,
    get_unit_relation_data,
    is_connection_possible,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

APP_NAME = CHARM_METADATA["name"]
TLS_APP_NAME = "self-signed-certificates"
CLUSTER_NAME = "test_cluster"
TIMEOUT = 15 * MINUTE_SECS


def test_build_and_deploy(juju: Juju, charm) -> None:
    """Build the charm and deploy 3 units to ensure a cluster is formed."""
    logger.info(f"Deploying {APP_NAME}")
    juju.deploy(
        charm,
        APP_NAME,
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        base="ubuntu@26.04",
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
    password = get_mysql_server_credentials(juju, app_units[0], REPLICATION_USERNAME)["password"]

    # Before relating to TLS charm both encrypted and unencrypted connection should be possible
    logger.info("Asserting connections before relation")
    for unit_name in app_units:
        assert is_connection_possible(
            juju,
            unit_name,
            REPLICATION_USERNAME,
            password,
            ssl_enabled=True,
        ), f"❌ Encrypted connection not possible to unit {unit_name} with disabled TLS"

        assert is_connection_possible(
            juju,
            unit_name,
            REPLICATION_USERNAME,
            password,
            ssl_enabled=False,
        ), f"❌ Unencrypted connection not possible to unit {unit_name} with disabled TLS"


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

    password = get_mysql_server_credentials(juju, app_units[0], REPLICATION_USERNAME)["password"]

    # After relating to only encrypted connection should be possible
    logger.info("Asserting connections after relation")
    for unit_name in app_units:
        assert is_connection_possible(
            juju,
            unit_name,
            REPLICATION_USERNAME,
            password,
            ssl_enabled=True,
        ), f"❌ Encrypted connection not possible to unit {unit_name} with enabled TLS"
        assert not is_connection_possible(
            juju,
            unit_name,
            REPLICATION_USERNAME,
            password,
            ssl_enabled=False,
        ), f"❌ Unencrypted connection possible to unit {unit_name} with enabled TLS"

    # test for ca presence in a given unit
    logger.info("Assert TLS files exists")
    assert get_unit_relation_data(juju, app_units[0], "client-certificates")
    assert get_unit_relation_data(juju, app_units[0], "peer-certificates")


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

    password = get_mysql_server_credentials(juju, app_units[0], REPLICATION_USERNAME)["password"]

    # After relation removal both encrypted and unencrypted connection should be possible
    for unit_name in app_units:
        assert is_connection_possible(
            juju,
            unit_name,
            REPLICATION_USERNAME,
            password,
            ssl_enabled=True,
        ), f"❌ Encrypted connection not possible to unit {unit_name} after relation removal"
        assert is_connection_possible(
            juju,
            unit_name,
            REPLICATION_USERNAME,
            password,
            ssl_enabled=False,
        ), f"❌ Unencrypted connection not possible to unit {unit_name} after relation removal"


def get_unit_certificates_ca(juju: Juju, unit_name: str, relation_name: str) -> str:
    """Returns the TLS CA used by the unit.

    Args:
        juju: The Juju instance
        unit_name: The name of the unit
        relation_name: name of the relation to get data from

    Returns:
        TLS CA or an empty string if there is no CA.
    """
    relation_data = get_unit_relation_data(juju, unit_name, relation_name)
    relation_fields = json.loads(relation_data["application-data"]["certificates"])
    if not relation_fields:
        raise ValueError(f"No relation data could be grabbed for relation {relation_name}")

    return relation_fields[0].get("ca", "")
