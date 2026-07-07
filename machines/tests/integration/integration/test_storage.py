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

from ..helpers import generate_random_string
from ..helpers_ha import (
    MINUTE_SECS,
    get_app_leader,
    get_mysql_server_credentials,
    insert_mysql_test_data,
    verify_mysql_test_data,
    wait_for_apps_status,
)

logger = logging.getLogger(__name__)

DATABASE_APP_NAME = "mysql"
TABLE_NAME = "test-table"
TIMEOUT = 15 * MINUTE_SECS


def test_build_and_deploy(juju: Juju, charm) -> None:
    logger.info(f"Deploying {DATABASE_APP_NAME} with 1 unit")
    juju.deploy(
        charm,
        DATABASE_APP_NAME,
        base="ubuntu@26.04",
        config={"profile": "testing"},
        storage={"data": "1G", "logs": "1G"},  # Necessary to detach storage later
        num_units=1,
    )

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        timeout=TIMEOUT,
    )


def test_charm_lists_expected_storage(juju: Juju) -> None:
    expected_storages = {"archive", "data", "temp", "logs"}

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
        "#innodb_temp",
        "#innodb_redo",
        "undo_001",
        "undo_002",
    }

    actual_content = set(list_vm_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_DATA_DIR))

    assert expected_content <= actual_content
    assert excluded_content.isdisjoint(actual_content)


def test_temp_directory_has_only_expected_file_extensions_after_initialization(juju: Juju) -> None:
    actual_content = set(list_vm_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_TEMP_DIR))

    assert all(fname.endswith(".ibt") for fname in actual_content)


def test_logs_directory_has_only_expected_contents_after_initialization(juju: Juju) -> None:
    expected_content = {
        "audit.log",
        "error.log",
        "binlog.index",
        "#innodb_redo",
    }

    actual_content = set(list_vm_files(juju, f"{DATABASE_APP_NAME}/0", MYSQL_LOGS_DIR))

    assert expected_content <= actual_content
    remaining_content = actual_content - expected_content

    undolog_pattern = re.compile(r"^undo_\d+$")
    assert all(
        (undolog_pattern.match(fname) or fname.startswith("binlog") or fname.startswith("audit"))
        for fname in remaining_content
    )

    redolog_pattern = re.compile(r"^#ib_redo\d+")
    actual_content = set(
        list_vm_files(juju, f"{DATABASE_APP_NAME}/0", f"{MYSQL_LOGS_DIR}/#innodb_redo")
    )

    assert all(redolog_pattern.match(fname) for fname in actual_content)


def test_scale_up_from_zero_preserves_attached_storage(juju: Juju) -> None:
    """Ensure scaling down to zero and back up can reuse storage."""
    logger.info("Creating test data")
    test_data = generate_random_string(255)
    insert_mysql_test_data(juju, DATABASE_APP_NAME, TABLE_NAME, test_data)
    verify_mysql_test_data(juju, DATABASE_APP_NAME, TABLE_NAME, test_data)

    mysql_app_leader = get_app_leader(juju, DATABASE_APP_NAME)
    old_credentials = get_mysql_server_credentials(juju, mysql_app_leader)

    storages = juju.status().storage.storage
    data_storage_id = next(storage_id for storage_id in storages if "data" in storage_id)
    logs_storage_id = next(storage_id for storage_id in storages if "logs" in storage_id)

    logger.info("Scaling down to 0 units")
    juju.remove_unit(mysql_app_leader, destroy_storage=False)

    # Sometimes the app will arrive to an "unknown" state, we can't check for "active"
    juju.wait(
        ready=lambda status: len(status.apps[DATABASE_APP_NAME].units) == 0,
        timeout=TIMEOUT,
    )

    juju.add_unit(DATABASE_APP_NAME, attach_storage=[data_storage_id, logs_storage_id])

    juju.wait(
        ready=wait_for_apps_status(jubilant.all_active, DATABASE_APP_NAME),
        error=jubilant.any_error,
        timeout=TIMEOUT,
    )

    # Check that credentials are the same
    mysql_app_leader = get_app_leader(juju, DATABASE_APP_NAME)
    new_credentials = get_mysql_server_credentials(juju, mysql_app_leader)

    assert new_credentials == old_credentials

    # Check that data is still there
    verify_mysql_test_data(juju, DATABASE_APP_NAME, TABLE_NAME, test_data)


def list_vm_files(
    juju: jubilant.Juju,
    unit_name: str,
    path: str,
) -> list[str]:
    task = juju.exec("ls", path, unit=unit_name)
    task.raise_on_failure()

    return task.stdout.split()
