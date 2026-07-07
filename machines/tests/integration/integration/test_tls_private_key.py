# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import json
import logging

import jubilant
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from jubilant import Juju

from constants import (
    TLS_CLIENT_RELATION,
    TLS_PEER_RELATION,
)

from ..helpers import is_connection_possible
from ..helpers_ha import (
    MINUTE_SECS,
    create_app_secret,
    get_app_leader,
    get_app_units,
    get_mysql_server_credentials,
    get_unit_ip,
    get_unit_relation_data,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

APP_NAME = "mysql"
TLS_APP_NAME = "self-signed-certificates"
CLUSTER_NAME = "test_cluster"
TIMEOUT = 15 * MINUTE_SECS


def test_build_and_deploy(juju: Juju, charm) -> None:
    """Build the charm and deploy with TLS enabled."""
    juju.deploy(
        charm,
        APP_NAME,
        base="ubuntu@26.04",
        config={"cluster-name": CLUSTER_NAME, "profile": "testing"},
        num_units=3,
        trust=True,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME),
        timeout=TIMEOUT,
    )


def test_tls_enabled(juju: Juju) -> None:
    """Verify TLS is enabled and the cluster is accessible."""
    app_units = get_app_units(juju, APP_NAME)

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

    logger.info("Relate to TLS operator")
    juju.integrate(f"{APP_NAME}:{TLS_CLIENT_RELATION}", f"{TLS_APP_NAME}:certificates")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
        delay=5,
    )

    juju.integrate(f"{APP_NAME}:{TLS_PEER_RELATION}", f"{TLS_APP_NAME}:certificates")
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
        delay=5,
    )

    credentials = get_mysql_server_credentials(juju, app_units[0])
    config = {
        "username": credentials["username"],
        "password": credentials["password"],
    }

    logger.info("Asserting connections after relation")
    for unit_name in app_units:
        config["host"] = get_unit_ip(juju, APP_NAME, unit_name)
        assert is_connection_possible(config, **{"ssl_disabled": False})

    logger.info("Asserting TLS relation data exists")
    assert get_unit_relation_data(juju, app_units[0], TLS_CLIENT_RELATION)
    assert get_unit_relation_data(juju, app_units[0], TLS_PEER_RELATION)


def test_set_private_key(juju: Juju) -> None:
    """Set a new private key and verify the cluster remains accessible."""
    leader_unit = get_app_leader(juju, APP_NAME)
    credentials = get_mysql_server_credentials(juju, leader_unit)

    config = {
        "username": credentials["username"],
        "password": credentials["password"],
    }

    first_client_certs = get_unit_certificates_cert(juju, leader_unit, TLS_CLIENT_RELATION)
    first_peer_certs = get_unit_certificates_cert(juju, leader_unit, TLS_PEER_RELATION)

    logger.info("Generating new private key")
    private_key = create_private_key()

    logger.info("Creating secret with the new private key")
    secret_uri = create_app_secret(juju, APP_NAME, {"private-key": private_key})

    logger.info("Configuring the application with the new client private key")
    juju.config(app=APP_NAME, values={"tls-client-private-key": secret_uri})
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
    )

    second_client_certs = get_unit_certificates_cert(juju, leader_unit, TLS_CLIENT_RELATION)
    second_peer_certs = get_unit_certificates_cert(juju, leader_unit, TLS_PEER_RELATION)
    assert first_client_certs != second_client_certs
    assert first_peer_certs == second_peer_certs

    logger.info("Configuring the application with the new peer private key")
    juju.config(app=APP_NAME, values={"tls-peer-private-key": secret_uri})
    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, APP_NAME, TLS_APP_NAME),
        timeout=TIMEOUT,
    )

    third_client_certs = get_unit_certificates_cert(juju, leader_unit, TLS_CLIENT_RELATION)
    third_peer_certs = get_unit_certificates_cert(juju, leader_unit, TLS_PEER_RELATION)
    assert second_client_certs == third_client_certs
    assert second_peer_certs != third_peer_certs

    logger.info("Verifying cluster accessibility after client key rotation")
    for unit_name in get_app_units(juju, APP_NAME):
        config["host"] = get_unit_ip(juju, APP_NAME, unit_name)
        assert is_connection_possible(config, **{"ssl_disabled": False})


def test_disable_tls(juju: Juju) -> None:
    """Verify TLS is disabled and the cluster is accessible."""
    leader_unit = get_app_leader(juju, APP_NAME)
    credentials = get_mysql_server_credentials(juju, leader_unit)

    config = {
        "username": credentials["username"],
        "password": credentials["password"],
    }

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

    for unit_name in get_app_units(juju, APP_NAME):
        config["host"] = get_unit_ip(juju, APP_NAME, unit_name)
        assert is_connection_possible(config, **{"ssl_disabled": False})
        assert is_connection_possible(config, **{"ssl_disabled": True})


def create_private_key() -> str:
    """Generates a private key using the PEM format (valid for certificates)."""
    private_key = generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_key = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return base64.b64encode(private_key).decode()


def get_unit_certificates_cert(juju: Juju, unit_name: str, relation_name: str) -> str:
    """Returns the TLS Certificate used by the unit.

    Args:
        juju: The Juju instance
        unit_name: The name of the unit
        relation_name: name of the relation to get data from

    Returns:
        TLS Certificate or an empty string if there is no Certificate.
    """
    relation_data = get_unit_relation_data(juju, unit_name, relation_name)
    relation_fields = json.loads(relation_data["application-data"]["certificates"])
    if not relation_fields:
        raise ValueError(f"No relation data could be grabbed for relation {relation_name}")

    return relation_fields[0].get("certificate", "")
