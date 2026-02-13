#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import re

import jubilant
from jubilant import Juju

from constants import (
    CONTAINER_NAME,
    MYSQL_BINLOGS_DIR,
    MYSQL_DATA_DIR,
    MYSQL_LOG_DIR,
    MYSQL_REDOLOGS_DIR,
    MYSQL_TEMP_DIR,
)

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
    expected_storages = ["data", "temp", "binlogs", "redologs", "logs"]

    assert len(juju.status().storage.storage) == len(expected_storages)


def test_data_directory_has_expected_contents_after_initialization(juju: Juju) -> None:
    expected_content = {
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
    }
    excluded_content = {
        "'#innodb_temp'",
        "'#innodb_redo'",
        "undo_001",
        "undo_002",
    }

    actual_content = set(list_container_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_DATA_DIR))

    assert expected_content <= actual_content
    assert excluded_content.isdisjoint(actual_content)


def test_temp_directory_has_only_expected_file_extensions_after_initialization(juju: Juju) -> None:
    actual_content = set(list_container_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_TEMP_DIR))

    assert all(fname.endswith(".ibt") for fname in actual_content)


def test_binlogs_directory_has_only_expected_file_names_after_initialization(juju: Juju) -> None:
    actual_content = set(list_container_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_BINLOGS_DIR))

    assert all(fname.startswith("binlog") for fname in actual_content)
    assert "binlog.index" in actual_content


def test_redologs_directory_has_only_expected_files_after_initialization(
    juju: Juju,
) -> None:
    redolog_pattern = re.compile(r"^\'\#ib_redo\d+")
    undolog_pattern = re.compile(r"^undo_\d+$")

    actual_content = set(list_container_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_REDOLOGS_DIR))

    assert all(
        (undolog_pattern.match(fname) or (fname == "'#innodb_redo'")) for fname in actual_content
    )

    result = juju.ssh(
        f"{DATABASE_APP_NAME}/0",
        "ls",
        f"{MYSQL_REDOLOGS_DIR}/#innodb_redo",
        container=CONTAINER_NAME,
    )
    actual_content = set(result.strip().split())

    assert all(redolog_pattern.match(fname) for fname in actual_content)


def test_logs_directory_has_only_expected_contents_after_initialization(
    juju: Juju,
) -> None:
    expected_content = {
        "archive_audit",
        "archive_error",
        "audit.log",
        "error.log",
    }
    actual_content = set(list_container_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_LOG_DIR))

    assert expected_content <= actual_content


def list_container_files(
    juju, unit_name: str, path: str, container: str = CONTAINER_NAME
) -> list[str]:
    result = juju.ssh(unit_name, "ls", path, container=container)
    return result.strip().split()
