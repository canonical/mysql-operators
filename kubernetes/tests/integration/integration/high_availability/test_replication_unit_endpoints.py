# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant_backports
from jubilant_backports import Juju

from ... import architecture
from ...helpers_ha import (
    CHARM_METADATA,
    get_app_units,
    get_k8s_endpoint_addresses,
    get_unit_address,
    wait_for_apps_status,
)

MYSQL_APP_NAME = "mysql-k8s"
MYSQL_APP_CLUSTER = "test-cluster"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60


def test_deploy_highly_available_clusters(juju: Juju, charm: str) -> None:
    """Deploy two mysql clusters with companion test apps with same cluster name."""
    logging.info("Deploying two MySQL cluster")
    constraints = {"arch": architecture.architecture}
    apps = []
    for i in ("1", "2"):
        mysql_app = f"{MYSQL_APP_NAME}{i}"
        test_app = f"{MYSQL_TEST_APP_NAME}{i}"
        apps.append(mysql_app)
        apps.append(test_app)
        juju.deploy(
            charm=charm,
            app=mysql_app,
            base="ubuntu@22.04",
            config={"cluster-name": MYSQL_APP_CLUSTER, "profile": "testing"},
            resources={
                "mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]
            },
            num_units=3,
            trust=True,
        )
        juju.deploy(
            charm=MYSQL_TEST_APP_NAME,
            app=test_app,
            base="ubuntu@22.04",
            channel="latest/edge",
            config={"sleep_interval": 1000},
            num_units=1,
            constraints=constraints,
        )

        juju.integrate(f"{mysql_app}:database", f"{test_app}:database")

    logging.info("Wait for applications to become active")
    juju.wait(
        ready=wait_for_apps_status(jubilant_backports.all_active, *apps),
        timeout=20 * MINUTE_SECS,
    )


def test_labeling_of_k8s_endpoints(juju: Juju) -> None:
    """Test the labeling of k8s endpoints when apps with same cluster-name deployed."""
    logging.info("Ensuring that the created k8s endpoints have correct addresses")
    for i in ("1", "2"):
        mysql_app = f"{MYSQL_APP_NAME}{i}"
        check_endpoint_addresses(juju, mysql_app)


def check_endpoint_addresses(juju: Juju, mysql_app_name: str) -> None:
    """Check that the endpoints have correct addresses."""
    cluster_ips = [
        get_unit_address(juju, mysql_app_name, unit_name)
        for unit_name in get_app_units(juju, mysql_app_name)
    ]

    cluster_primary_addresses = get_k8s_endpoint_addresses(juju, f"{mysql_app_name}-primary")
    cluster_replica_addresses = get_k8s_endpoint_addresses(juju, f"{mysql_app_name}-replicas")

    for address in cluster_primary_addresses:
        assert address in cluster_ips, f"{address} is not in cluster {mysql_app_name} addresses"

    assert set(cluster_primary_addresses + cluster_replica_addresses) == set(cluster_ips)
