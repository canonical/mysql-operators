# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant_backports
import pytest
from jubilant_backports import Juju
from mysql.connector.errorcode import ER_CON_COUNT_ERROR
from mysql.connector.errors import OperationalError
from tenacity import Retrying, stop_after_delay, wait_fixed

from .. import architecture
from ..connector import create_db_connections
from ..helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    get_app_units,
    get_unit_address,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

MYSQL_APP_NAME = "mysql"
TEST_APP_NAME = "app"
CONNECTIONS = 10


def test_build_and_deploy(juju: Juju, charm) -> None:
    """Build the charm and deploy 1 units to ensure a cluster is formed."""
    juju.deploy(
        charm,
        MYSQL_APP_NAME,
        config={"profile-limit-memory": "2000", "experimental-max-connections": CONNECTIONS},
        num_units=1,
        base="ubuntu@22.04",
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        trust=True,
    )


def test_deploy_and_relate_test_app(juju: Juju) -> None:
    config = {"auto_start_writes": False, "sleep_interval": "500"}
    constraints = {"arch": architecture.architecture}
    logger.info("Deploying test app")
    juju.deploy(
        "mysql-test-app",
        TEST_APP_NAME,
        num_units=1,
        base="ubuntu@22.04",
        config=config,
        channel="latest/edge",
        constraints=constraints,
    )

    logger.info("Relating test app to mysql")
    juju.integrate(MYSQL_APP_NAME, f"{TEST_APP_NAME}:database")

    logger.info("Waiting all to be active")
    juju.wait(
        wait_for_apps_status(jubilant_backports.all_active, MYSQL_APP_NAME, TEST_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )


def test_saturate_max_connections(juju: Juju) -> None:
    app_unit_name = get_app_units(juju, TEST_APP_NAME)[0]
    mysql_unit_name = get_app_units(juju, MYSQL_APP_NAME)[0]

    host_ip = get_unit_address(juju, MYSQL_APP_NAME, mysql_unit_name)

    logger.info("Running action to get app connection data")
    credentials = juju.run(app_unit_name, "get-client-connection-data").results
    if "return-code" in credentials:
        # juju 2.9 dont have the return-code key
        del credentials["return-code"]
    if "Code" in credentials:
        del credentials["Code"]
    credentials["host"] = host_ip

    logger.info("Opening first connection")
    # The charm may briefly hold some of the few available slots (e.g. on hooks
    # or periodic log rotation), so retry until a slot is free
    for attempt in Retrying(
        stop=stop_after_delay(2 * MINUTE_SECS), wait=wait_fixed(5), reraise=True
    ):
        with attempt:
            connections = create_db_connections(1, **credentials)

    logger.info("Ensure max_connections is applied")
    cursor = connections[0].cursor()
    cursor.execute("SELECT @@max_connections")
    assert cursor.fetchone()[0] == CONNECTIONS, "max_connections not applied"
    cursor.close()

    logger.info("Saturate connections until the server refuses them")
    with pytest.raises(OperationalError) as exc_info:
        # upper bound ensures the loop ends even if the limit is not enforced
        for _ in range(CONNECTIONS + 5):
            connections.extend(create_db_connections(1, **credentials))

    assert exc_info.value.errno == ER_CON_COUNT_ERROR, "Unexpected error on saturation"
    assert len(connections) <= CONNECTIONS, "More connections than allowed were established"

    logger.info("Get cluster status while connections are saturated")
    juju.run(mysql_unit_name, "get-cluster-status")

    for conn in connections:
        conn.close()
