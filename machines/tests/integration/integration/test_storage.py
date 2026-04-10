#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import re

import jubilant
from jubilant import Juju

from constants import (
    MYSQL_DATA_DIR,
    MYSQL_LOGS_DIR,
    MYSQL_TEMP_DIR,
)

from ..helpers_ha import (
    MINUTE_SECS,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

DATABASE_APP_NAME = "mysql"
CLUSTER_NAME = "test_cluster"
TIMEOUT = 15 * MINUTE_SECS


def test_build_and_deploy(juju: Juju, charm) -> None:
    logger.info(f"Deploying {DATABASE_APP_NAME} with 1 unit")
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        base="ubuntu@24.04",
        config={"cluster-name": CLUSTER_NAME, "profile": "testing"},
        num_units=1,
        trust=True,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        timeout=TIMEOUT,
    )


def test_charm_lists_expected_storage(juju: Juju) -> None:
    expected_storages = ["data", "temp", "logs"]

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

    actual_content = set(list_vm_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_DATA_DIR))

    assert expected_content <= actual_content
    assert excluded_content.isdisjoint(actual_content)


def test_temp_directory_has_only_expected_file_extensions_after_initialization(juju: Juju) -> None:
    actual_content = set(list_vm_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_TEMP_DIR))

    assert all(fname.endswith(".ibt") for fname in actual_content)


def test_logs_directory_has_only_expected_contents_after_initialization(
    juju: Juju,
) -> None:
    expected_content = {
        "archive_audit",
        "archive_error",
        "audit.log",
        "error.log",
        "binlog.index",
        "'#innodb_redo'",
    }

    actual_content = set(list_vm_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_LOGS_DIR))

    assert expected_content <= actual_content
    remaining_content = actual_content - expected_content

    undolog_pattern = re.compile(r"^undo_\d+$")
    assert all(
        (undolog_pattern.match(fname) or fname.startswith("binlog") or fname.startswith("audit"))
        for fname in remaining_content
    )

    redolog_pattern = re.compile(r"^\'\#ib_redo\d+")
    result = juju.ssh(
        f"{DATABASE_APP_NAME}/0",
        "ls",
        f"{MYSQL_LOGS_DIR}/#innodb_redo",
    )
    actual_content = set(result.strip().split())

    assert all(redolog_pattern.match(fname) for fname in actual_content)


def list_vm_files(
    juju,
    unit_name: str,
    path: str,
) -> list[str]:
    result = juju.ssh(unit_name, "ls", path)
    return result.strip().split()
