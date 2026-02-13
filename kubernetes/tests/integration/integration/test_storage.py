#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import jubilant
from jubilant import Juju

from constants import CONTAINER_NAME, MYSQL_DATA_DIR, MYSQL_TEMP_DIR

from ..helpers_ha import (
    CHARM_METADATA,
    MINUTE_SECS,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

DATABASE_APP_NAME = "mysql-k8s"
CLUSTER_NAME = "test_cluster"
TIMEOUT = 15 * MINUTE_SECS


def test_build_and_deploy(juju: Juju, charm) -> None:
    logger.info(f"Deploying {DATABASE_APP_NAME} with 1 unit")
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        base="ubuntu@22.04",
        config={"cluster-name": CLUSTER_NAME, "profile": "testing"},
        resources={"mysql-image": CHARM_METADATA["resources"]["mysql-image"]["upstream-source"]},
        num_units=1,
        trust=True,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        timeout=TIMEOUT,
    )


def test_charm_lists_expected_storage(juju: Juju) -> None:
    expected_storages = ["data", "temp"]

    assert len(juju.status().storage.storage) == len(expected_storages)


def test_data_directory_has_expected_contents_after_initialization(juju: Juju) -> None:
    expected_content = {
        "'#innodb_redo'",
        "auto.cnf",
        "ca-key.pem",
        "ca.pem",
        "client-cert.pem",
        "client-key.pem",
        "ib_buffer_pool",
        "mysql",
        "mysql.ibd",
        "performance_schema",
        "private_key.pem",
        "public_key.pem",
        "server-cert.pem",
        "server-key.pem",
        "sys",
        "undo_001",
        "undo_002",
    }
    excluded_content = {
        "'#innodb_temp'",
    }

    result = juju.ssh(f"{DATABASE_APP_NAME}/0", "ls", MYSQL_DATA_DIR, container=CONTAINER_NAME)
    actual_content = set(result.strip().split())

    assert expected_content <= actual_content
    assert excluded_content.isdisjoint(actual_content)


def test_temp_directory_has_only_expected_file_extensions_after_initialization(juju: Juju) -> None:
    result = juju.ssh(f"{DATABASE_APP_NAME}/0", "ls", MYSQL_TEMP_DIR, container=CONTAINER_NAME)
    actual_content = set(result.strip().split())

    assert all(fname.endswith(".ibt") for fname in actual_content)
