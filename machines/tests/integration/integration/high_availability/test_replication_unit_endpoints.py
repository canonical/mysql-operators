# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import jubilant
import urllib3
from jubilant import Juju
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_fixed,
)

from constants import (
    CHARMED_MYSQL_SNAP_NAME,
    CHARMED_MYSQLD_EXPORTER_SERVICE,
    MYSQL_EXPORTER_PORT,
)

from ...helpers_ha import (
    get_app_units,
    get_unit_ip,
    load_mysql_test_data,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


def test_deploy_highly_available_cluster(juju: Juju, charm: str) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Deploying MySQL cluster")
    juju.deploy(
        charm=charm,
        app=MYSQL_APP_NAME,
        base="ubuntu@26.04",
        config={"profile": "testing"},
        num_units=3,
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@26.04",
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
        ready=wait_for_apps_status(jubilant.all_active, MYSQL_APP_NAME, MYSQL_TEST_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    if path := os.getenv("DATA_SOURCE_PATH"):
        logging.info("Loading test database")
        load_mysql_test_data(juju, MYSQL_APP_NAME, path)


def test_exporter_endpoints(juju: Juju) -> None:
    """Test that exporter endpoints are running."""
    http_client = urllib3.PoolManager()
    service_name = f"{CHARMED_MYSQL_SNAP_NAME}.{CHARMED_MYSQLD_EXPORTER_SERVICE}"

    for unit_name in get_app_units(juju, MYSQL_APP_NAME):
        # Exporter is enabled by default, verify it is active
        for attempt in Retrying(stop=stop_after_attempt(45), wait=wait_fixed(2)):
            with attempt:
                task = juju.exec(f"sudo snap services {service_name}", unit=unit_name)
                assert task.stdout.split("\n")[1].split()[2] == "active"

        mysql_unit_address = get_unit_ip(juju, MYSQL_APP_NAME, unit_name)
        mysql_unit_exporter_url = f"http://{mysql_unit_address}:{MYSQL_EXPORTER_PORT}/metrics"
        mysql_unit_response = http_client.request("GET", mysql_unit_exporter_url)

        assert mysql_unit_response.status == 200
