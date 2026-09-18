# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from collections.abc import Generator

import jubilant_backports
import pytest
from jubilant_backports import CLIError, Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    check_mysql_units_writes_increment,
    wait_for_apps_status,
)
from ...helpers_proxy import (
    PROXY_PORT,
    block_direct_egress,
    check_passwordless_sudo,
    check_proxy_relayed_traffic_to,
    get_cluster_cidrs,
    get_node_address,
    get_squid_access_log,
    install_squid,
    remove_squid,
    set_model_proxy,
    unblock_direct_egress,
    unset_model_proxy,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60

# Used to tell a working proxy route apart from a working direct route
EXTERNAL_HOST = "api.snapcraft.io"
EXTERNAL_PROBE = (
    'python3 -c "import urllib.request;'
    f" urllib.request.urlopen('https://{EXTERNAL_HOST}', timeout=30)\""
)


@pytest.fixture(scope="module", autouse=True)
def http_proxy(juju: Juju) -> Generator:
    """Route the model through a Squid proxy, and drop every other route out."""
    if not check_passwordless_sudo():
        pytest.skip("Configuring squid on the test runner requires sudo")

    node_address = get_node_address()
    pod_cidr, service_cidr = get_cluster_cidrs()
    proxy_url = f"http://{node_address}:{PROXY_PORT}"

    # Traffic from a pod to the node may leave with the pod address or, once masqueraded,
    # with the node address, so both are allowed through the proxy
    install_squid(allowed_sources=[pod_cidr, f"{node_address}/32"])
    try:
        set_model_proxy(
            juju,
            proxy_url,
            no_proxy=["127.0.0.1", "localhost", "::1", pod_cidr, service_cidr, node_address],
        )
        block_direct_egress(juju.model, node_address)

        yield proxy_url
    finally:
        logging.info("Squid access log:\n%s", get_squid_access_log())
        unblock_direct_egress(juju.model)
        unset_model_proxy(juju)
        remove_squid()


def test_deploy_highly_available_cluster(juju: Juju, charm: str) -> None:
    """Ensure that the MySQL and application charms deploy in a model behind a proxy."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@22.04",
        config={"profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=3,
        trust=True,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
        channel="latest/edge",
        config={"sleep_interval": 500},
        num_units=1,
        constraints={"arch": architecture.architecture},
    )

    juju.integrate(
        f"{MYSQL_APP_NAME}:database",
        f"{MYSQL_TEST_APP_NAME}:database",
    )

    logging.info("Wait for applications to become active")
    juju.wait(
        ready=wait_for_apps_status(
            jubilant_backports.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME
        ),
        timeout=30 * MINUTE_SECS,
    )


def test_proxy_is_the_only_route_out(juju: Juju, http_proxy: str) -> None:
    """Confirm that the cluster was deployed with the proxy as its only route out."""
    unit_name = f"{MYSQL_APP_NAME}/0"

    logging.info("Checking that %s cannot reach %s directly", unit_name, EXTERNAL_HOST)
    with pytest.raises(CLIError):
        juju.ssh(unit_name, EXTERNAL_PROBE)

    logging.info("Checking that %s can reach %s through the proxy", unit_name, EXTERNAL_HOST)
    juju.ssh(unit_name, f"https_proxy={http_proxy} {EXTERNAL_PROBE}")

    assert check_proxy_relayed_traffic_to(EXTERNAL_HOST), (
        f"No traffic to {EXTERNAL_HOST} in the proxy access log"
    )


def test_continuous_writes_increment(juju: Juju, continuous_writes) -> None:
    """Confirm that writes from the test application reach every unit of the cluster."""
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)
