# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import tempfile
from pathlib import Path

import jubilant
from jubilant import Juju

from ...constants import MYSQL_ARCH_DIR, MYSQL_LOGS_DIR
from ...helpers_ha import (
    get_app_leader,
    get_mysql_instance_label,
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


def test_log_rotation(juju: Juju) -> None:
    """Test the log rotation of text files."""
    mysql_app_leader = get_app_leader(juju, MYSQL_APP_NAME)
    mysql_log_types = ["audit", "error"]

    logging.info("Stopping any running logrotate jobs")
    stop_log_rotate_dispatcher(juju, mysql_app_leader)

    for log_type in mysql_log_types:
        archive_log_dir = f"{MYSQL_ARCH_DIR}/archive_{log_type}"

        logging.info("Removing existing archive directories")
        delete_unit_file(juju, mysql_app_leader, archive_log_dir)

        logging.info("Writing some data to the text log files")
        write_unit_file(
            juju=juju,
            unit_name=mysql_app_leader,
            file_path=f"{MYSQL_LOGS_DIR}/{log_type}.log",
            file_data=f"{log_type} content",
        )

    logging.info("Executing logrotate")
    start_log_rotate_dispatcher(juju, mysql_app_leader)

    logging.info("Ensuring log files were rotated")
    for log_type in mysql_log_types:
        active_log_file_data = read_unit_file(
            juju=juju,
            unit_name=mysql_app_leader,
            file_path=f"{MYSQL_LOGS_DIR}/{log_type}.log",
        )
        assert f"{log_type} content" not in active_log_file_data

        archive_log_dir = f"{MYSQL_ARCH_DIR}/archive_{log_type}"
        archive_log_files_listed = list_unit_files(juju, mysql_app_leader, archive_log_dir)

        assert len(archive_log_files_listed) == 1

        archive_log_file_name = archive_log_files_listed[0].split()[-1]
        archive_log_file_data = read_unit_file(
            juju=juju,
            unit_name=mysql_app_leader,
            file_path=f"{archive_log_dir}/{archive_log_file_name}",
        )
        assert f"{log_type} content" in archive_log_file_data


def delete_unit_file(juju: Juju, unit_name: str, file_path: str) -> None:
    """Delete a path in the provided unit.

    Args:
        juju: The Juju instance
        unit_name: The unit on which to delete the file
        file_path: The path or file to delete
    """
    if file_path.strip() in ["/", "."]:
        return

    juju.exec(f"sudo find {file_path} -maxdepth 1 -delete", unit=unit_name)


def list_unit_files(juju: Juju, unit_name: str, file_path: str) -> list[str]:
    """Returns the list of files in the given path.

    Args:
        juju: The Juju instance
        unit_name: The unit in which to list the files
        file_path: The path at which to list the files
    """
    task = juju.exec(f"sudo ls -la {file_path}", unit=unit_name)
    output = task.stdout.split("\n")[1:]

    return [
        line.strip("\r")
        for line in output
        if len(line.strip()) > 0 and line.split()[-1] not in [".", ".."]
    ]


def read_unit_file(juju: Juju, unit_name: str, file_path: str) -> str:
    """Read contents from file in the provided unit.

    Args:
        juju: The Juju instance
        unit_name: The name of the unit to read the file from
        file_path: The path of the unit to read the file
    """
    temp_path = "/tmp/file"

    juju.exec(f"sudo cp {file_path} {temp_path}", unit=unit_name)
    juju.exec(f"sudo chown ubuntu:ubuntu {temp_path}", unit=unit_name)

    with tempfile.NamedTemporaryFile(mode="r+", dir=Path.home()) as temp_file:
        juju.scp(
            f"{unit_name}:{temp_path}",
            f"{temp_file.name}",
        )
        contents = temp_file.read()

    juju.exec(f"sudo rm {temp_path}", unit=unit_name)
    return contents


def write_unit_file(juju: Juju, unit_name: str, file_path: str, file_data: str):
    """Write content to the file in the provided unit.

    Args:
        juju: The Juju instance
        unit_name: The name of the unit to write the file into
        file_path: The path of the unit to write the file
        file_data: The data to write to the file.
    """
    temp_path = "/tmp/file"

    with tempfile.NamedTemporaryFile(mode="w", dir=Path.home()) as temp_file:
        temp_file.write(file_data)
        temp_file.flush()

        juju.scp(
            f"{temp_file.name}",
            f"{unit_name}:{temp_path}",
        )

    juju.exec(f"sudo mv {temp_path} {file_path}", unit=unit_name)
    juju.exec(f"sudo chown snap_daemon:root {file_path}", unit=unit_name)


def start_log_rotate_dispatcher(juju: Juju, unit_name: str) -> None:
    """Start the logrotate dispatcher."""
    unit_label = get_mysql_instance_label(unit_name)

    dispatch_cmd = "juju-exec"
    dispatch_hook = "hooks/log_rotation"
    dispatch_path = f"/var/lib/juju/agents/unit-{unit_label}/charm/dispatch"

    juju.ssh(
        command=f"sudo {dispatch_cmd} JUJU_DISPATCH_PATH={dispatch_hook} {dispatch_path}",
        target=unit_name,
    )


def stop_log_rotate_dispatcher(juju: Juju, unit_name: str) -> None:
    """Stop the logrotate dispatcher."""
    juju.ssh(
        command="sudo pkill -f logrotate/main.py --signal SIGTERM",
        target=unit_name,
    )
