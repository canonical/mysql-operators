# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import shutil
import subprocess
import time
import zipfile
from ast import literal_eval
from pathlib import Path

import jubilant_backports
from jubilant_backports import Juju

from ...helpers_ha import (
    check_mysql_units_writes_increment,
    get_app_leader,
    get_relation_data,
    get_unit_by_number,
    get_unit_status_log,
    wait_for_apps_status,
    wait_for_unit_status,
)
from ...markers import amd64_only

MYSQL_APP_NAME = "mysql"
MYSQL_TEST_APP_NAME = "mysql-test-app"

MINUTE_SECS = 60

# TODO: support arm64 & s390x
BASELINE_CHARM_REVISIONS = {
    "amd64": 444,
}
BASELINE_SNAP_REVISIONS = {
    "amd64": 69,
}


# TODO: remove AMD64 marker after next incompatible MySQL server version is released in our snap
# (details: https://github.com/canonical/mysql-operator/pull/472#discussion_r1659300069)
@amd64_only
def test_build_and_deploy(juju: Juju) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    logging.info("Download baseline revision charm for rollback")
    # We use a specific combination of charm and snap revisions due:
    #   - snap from a version with a old incompatible MySQL version (8.0.34)
    #   - charm from a version that does not brake any interface with current and that does
    #     not initialize the snap.
    downloaded_charm = download_charm_revision(BASELINE_CHARM_REVISIONS["amd64"], MYSQL_APP_NAME)
    change_snap_revision_in_charm_zip(downloaded_charm, BASELINE_SNAP_REVISIONS["amd64"], "amd64")

    juju.deploy(
        charm=downloaded_charm.resolve(),
        app=MYSQL_APP_NAME,
        base="ubuntu@22.04",
        config={"profile": "testing", "plugin-audit-enabled": False},
        num_units=3,
        revision=BASELINE_CHARM_REVISIONS["amd64"],
    )
    juju.deploy(
        charm=MYSQL_TEST_APP_NAME,
        app=MYSQL_TEST_APP_NAME,
        base="ubuntu@22.04",
        channel="latest/edge",
        config={"auto_start_writes": False, "sleep_interval": 500},
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
        error=jubilant_backports.any_blocked,
        timeout=20 * MINUTE_SECS,
    )


# TODO: remove AMD64 marker after next incompatible MySQL server version is released in our snap
# (details: https://github.com/canonical/mysql-operator/pull/472#discussion_r1659300069)
@amd64_only
def test_pre_upgrade_check(juju: Juju) -> None:
    """Test that the pre-upgrade-check action runs successfully."""
    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)

    logging.info("Run pre-upgrade-check action")
    juju.run(unit=mysql_leader, action="pre-upgrade-check")


# TODO: remove AMD64 marker after next incompatible MySQL server version is released in our snap
# (details: https://github.com/canonical/mysql-operator/pull/472#discussion_r1659300069)
@amd64_only
def test_upgrade_to_failing(juju: Juju, charm: str, continuous_writes) -> None:
    logging.info("Ensure continuous_writes")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)

    with InjectFailure(
        path="src/upgrade.py",
        original_str="self.charm.recover_unit_after_restart()",
        replace_str="raise Exception",
    ):
        logging.info("Build charm with failure injected")
        new_charm = get_locally_built_charm(charm)

    logging.info("Refresh the charm")
    juju.refresh(app=MYSQL_APP_NAME, path=new_charm)

    logging.info("Wait for upgrade to start")
    juju.wait(
        ready=lambda status: jubilant_backports.any_maintenance(status, MYSQL_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )

    logging.info("Get first upgrading unit")
    relation_data = get_relation_data(juju, MYSQL_APP_NAME, "upgrade")
    upgrade_stack = relation_data[0]["application-data"]["upgrade-stack"]
    upgrade_unit = get_unit_by_number(juju, MYSQL_APP_NAME, literal_eval(upgrade_stack)[-1])

    logging.info("Wait for upgrade to fail on upgrading unit")
    juju.wait(
        ready=wait_for_unit_status(MYSQL_APP_NAME, upgrade_unit, "blocked"),
        timeout=10 * MINUTE_SECS,
    )


# TODO: remove AMD64 marker after next incompatible MySQL server version is released in our snap
# (details: https://github.com/canonical/mysql-operator/pull/472#discussion_r1659300069)
@amd64_only
def test_rollback(juju: Juju, charm, continuous_writes) -> None:
    """Test upgrade rollback to a healthy revision."""
    relation_data = get_relation_data(juju, MYSQL_APP_NAME, "upgrade")
    upgrade_stack = relation_data[0]["application-data"]["upgrade-stack"]
    upgrade_unit = get_unit_by_number(juju, MYSQL_APP_NAME, literal_eval(upgrade_stack)[-1])

    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)

    time.sleep(10)

    logging.info("Run pre-upgrade-check action")
    juju.run(unit=mysql_leader, action="pre-upgrade-check")

    time.sleep(20)

    # Use current charm with old snap to ensure treatment works in it
    local_charm = get_locally_built_charm(charm)
    local_charm_path = Path(local_charm)
    change_snap_revision_in_charm_zip(local_charm_path, BASELINE_SNAP_REVISIONS["amd64"], "amd64")

    logging.info("Refresh with current charm with old snap")
    juju.refresh(app=MYSQL_APP_NAME, path=local_charm)

    logging.info("Wait for upgrade to start")
    juju.wait(
        ready=lambda status: jubilant_backports.any_maintenance(status, MYSQL_APP_NAME),
        timeout=10 * MINUTE_SECS,
    )
    juju.wait(
        ready=lambda status: jubilant_backports.all_active(status, MYSQL_APP_NAME),
        timeout=20 * MINUTE_SECS,
    )

    logging.info("Ensure rollback has taken place")
    unit_status_logs = get_unit_status_log(juju, upgrade_unit, 100)

    upgrade_failed_index = get_unit_log_message(
        status_logs=unit_status_logs[:],
        unit_message="upgrade failed. Check logs for rollback instruction",
    )
    assert upgrade_failed_index is not None

    upgrade_complete_index = get_unit_log_message(
        status_logs=unit_status_logs[upgrade_failed_index:],
        unit_message="upgrade completed",
    )
    assert upgrade_complete_index is not None

    logging.info("Ensure continuous writes after rollback procedure")
    check_mysql_units_writes_increment(juju, MYSQL_APP_NAME)


class InjectFailure:
    def __init__(self, path: str, original_str: str, replace_str: str):
        self.path = path
        self.original_str = original_str
        self.replace_str = replace_str
        with open(path) as file:
            self.original_content = file.read()

    def __enter__(self):
        logging.info("Injecting failure")
        assert self.original_str in self.original_content, "replace content not found"
        new_content = self.original_content.replace(self.original_str, self.replace_str)
        assert self.original_str not in new_content, "original string not replaced"
        with open(self.path, "w") as file:
            file.write(new_content)

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info("Reverting failure")
        with open(self.path, "w") as file:
            file.write(self.original_content)


def get_unit_log_message(status_logs: list[dict], unit_message: str) -> int | None:
    """Returns the index of a status log containing the desired message."""
    for index, status_log in enumerate(status_logs):
        if status_log.get("message") == unit_message:
            return index

    return None


def get_locally_built_charm(charm: str) -> str:
    """Wrapper for a local charm build zip file updating."""
    local_charm_paths = Path().glob("local-*.charm")

    # Clean up local charms from previous runs
    # to avoid pytest_operator_cache globbing them
    for charm_path in local_charm_paths:
        charm_path.unlink()

    # Create a copy of the charm to avoid modifying the original
    local_charm_path = shutil.copy(charm, f"local-{Path(charm).stem}.charm")
    local_charm_path = Path(local_charm_path)

    for path in ["snap_revisions.json", "src/upgrade.py"]:
        with open(path) as f:
            content = f.read()
        with zipfile.ZipFile(local_charm_path, mode="a") as charm_zip:
            charm_zip.writestr(path, content)

    return f"{local_charm_path.resolve()}"


def download_charm_revision(revision: int, charm_name: str) -> Path:
    """Downloads a specific charm revision and returns the path to the downloaded charm."""
    downloaded_charm_path = Path(f"./{charm_name}_r{revision}.charm")
    if not downloaded_charm_path.exists():
        subprocess.run(
            [
                "juju",
                "download",
                charm_name,
                f"--revision={revision}",
                f"--filepath={downloaded_charm_path}",
            ],
            check=True,
        )
    return downloaded_charm_path


def change_snap_revision_in_charm_zip(
    charm_path: Path, revision: int, arch: str = "amd64"
) -> None:
    """Modify a snap revision inside a charm zip file."""
    arch_mapping = {
        "amd64": "x86_64",
        "arm64": "aarch64",
        "s390x": "s390x",
    }
    platform_arch = arch_mapping.get(arch)
    with zipfile.ZipFile(charm_path, "r") as charm_zip:
        snap_revisions = json.loads(charm_zip.read("snap_revisions.json"))

    snap_revisions[platform_arch] = str(revision)

    with zipfile.ZipFile(charm_path, mode="a") as charm_zip:
        charm_zip.writestr("snap_revisions.json", json.dumps(snap_revisions, indent=2))
