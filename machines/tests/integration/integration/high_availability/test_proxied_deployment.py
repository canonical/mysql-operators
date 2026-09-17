# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from collections.abc import Generator

import jubilant_backports
import pytest
from jubilant_backports import Juju, TaskError

from ...helpers_ha import check_mysql_units_writes_increment, wait_for_apps_status
from ...helpers_proxy import (
    PROXY_PORT,
    block_direct_egress,
    check_passwordless_sudo,
    check_proxy_relayed_traffic_to,
    get_controller_addresses,
    get_lxd_bridge,
    get_squid_access_log,
    install_squid,
    remove_squid,
    set_model_proxy,
    unblock_direct_egress,
    unset_model_proxy,
)

MYSQL_APP_NAME = "mysql"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60

# The charm installs its snap from the store, so this traffic has to show up in the proxy
# access log if the charm honours the model proxy configuration
SNAP_STORE_HOSTS = ("api.snapcraft.io", "snapcraft.io")

# Used to tell a working proxy route apart from a working direct route
EXTERNAL_URL = "https://api.snapcraft.io"


@pytest.fixture(scope="module", autouse=True)
def http_proxy(juju: Juju) -> Generator:
    """Route the model through a Squid proxy, and drop every other route out."""
    if not check_passwordless_sudo():
        pytest.skip("Configuring squid and iptables on the test runner requires sudo")

    bridge, host_address, network_cidr = get_lxd_bridge()
    proxy_url = f"http://{host_address}:{PROXY_PORT}"

    install_squid(allowed_cidr=network_cidr)
    try:
        set_model_proxy(
            juju,
            proxy_url,
            no_proxy=["127.0.0.1", "localhost", "::1", network_cidr],
        )
        block_direct_egress(bridge, exempt_sources=get_controller_addresses())

        yield proxy_url
    finally:
        logging.info("Squid access log:\n%s", get_squid_access_log())
        unblock_direct_egress(bridge)
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
        num_units=3,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
        channel="latest/edge",
        config={"sleep_interval": 500},
        num_units=1,
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
    curl = "curl --silent --show-error --output /dev/null --max-time 30"

    logging.info("Checking that %s cannot reach %s directly", unit_name, EXTERNAL_URL)
    with pytest.raises(TaskError):
        juju.exec(f"{curl} {EXTERNAL_URL}", unit=unit_name)

    logging.info("Checking that %s can reach %s through the proxy", unit_name, EXTERNAL_URL)
    juju.exec(f"{curl} --proxy {http_proxy} {EXTERNAL_URL}", unit=unit_name)


def test_snap_was_installed_through_proxy() -> None:
    """Confirm that the charm snap traffic was relayed by the proxy."""
    assert check_proxy_relayed_traffic_to(*SNAP_STORE_HOSTS), (
        f"No traffic to any of {SNAP_STORE_HOSTS} in the proxy access log"
    )


def test_continuous_writes_increment(juju: Juju, continuous_writes) -> None:
    """Confirm that writes from the test application reach every unit of the cluster."""
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)
