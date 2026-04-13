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
BASELINE_REVISIONS = {
    "amd64": 196,
}


# TODO: remove AMD64 marker after next incompatible MySQL server version is released in our snap
# (details: https://github.com/canonical/mysql-operator/pull/472#discussion_r1659300069)
@amd64_only
def test_build_and_deploy(juju: Juju) -> None:
    """Simple test to ensure that the MySQL and application charms get deployed."""
    juju.deploy(
        charm=MYSQL_APP_NAME,
        app=MYSQL_APP_NAME,
        base="ubuntu@22.04",
        config={"profile": "testing"},
        num_units=3,
        channel="8.0/stable",
        revision=BASELINE_REVISIONS["amd64"],
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
def test_rollback(juju: Juju, continuous_writes) -> None:
    """Test upgrade rollback to a healthy revision."""
    relation_data = get_relation_data(juju, MYSQL_APP_NAME, "upgrade")
    upgrade_stack = relation_data[0]["application-data"]["upgrade-stack"]
    upgrade_unit = get_unit_by_number(juju, MYSQL_APP_NAME, literal_eval(upgrade_stack)[-1])

    mysql_leader = get_app_leader(juju, MYSQL_APP_NAME)

    time.sleep(10)

    logging.info("Run pre-upgrade-check action")
    juju.run(unit=mysql_leader, action="pre-upgrade-check")

    time.sleep(20)

    # Download the specific revision we want to rollback to
    # This is necessary because after refreshing to a local charm,
    # juju refresh requires --path or --switch, and --switch cannot be combined with --revision
    logging.info("Download baseline revision charm for rollback")
    downloaded_charm = Path("./mysql_r196.charm")
    if not downloaded_charm.exists():
        subprocess.run(
            [
                "juju",
                "download",
                MYSQL_APP_NAME,
                f"--revision={BASELINE_REVISIONS['amd64']}",
                "--filepath=mysql_r196.charm",
            ],
            check=True,
        )

    # HACK: Convert databag from new format to old format for rollback compatibility
    # Revision 196 expects {"hostname", "fqdn", "ip"} but new code writes {"names": [...], "address"}
    hack_relation_data(juju, app_name=MYSQL_APP_NAME)

    # And yet, unit 1 fails with
    # 2026-04-13T15:10:27.294512Z 1 [ERROR] [MY-013171] [InnoDB] Cannot boot server version 80034 on data directory built by version 80045. Downgrade is not supported
    # mysqld: Can't open file: 'mysql.ibd' (errno: 0 - )
    # 2026-04-13T15:10:27.641133Z 1 [ERROR] [MY-010334] [Server] Failed to initialize DD Storage Engine
    # 2026-04-13T15:10:27.641412Z 0 [ERROR] [MY-010020] [Server] Data Dictionary initialization failed.

    logging.info(f"Refresh with previous charm: {downloaded_charm}")
    juju.refresh(app=MYSQL_APP_NAME, path=str(downloaded_charm.absolute()))

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


def hack_relation_data(juju: Juju, app_name: str):
    logging.info("Converting peer databags from new format to old format before rollback")
    relation_data = get_relation_data(juju, app_name, "database-peers")
    peer_relation_id = relation_data[0]["relation-id"]

    for unit_name in [f"{app_name}/0", f"{app_name}/1", f"{app_name}/2"]:
        # Read current databag from unit's own perspective
        result = juju.exec(
            f"relation-get -r {peer_relation_id} hostname-details {unit_name}", unit=unit_name
        )
        databag_content = result.stdout.strip()

        if not databag_content:
            logging.info(f"Skipping {unit_name} - no hostname-details found")
            continue

        current_data = json.loads(databag_content)

        # Check if it's in new format and convert to old format
        if "hostname" not in current_data:
            logging.info(f"Writing {unit_name} databag in old format")
            old_format = {
                "hostname": current_data["names"][0],
                "fqdn": current_data["names"][1],
                "ip": current_data["address"],
            }
            # Write back in old format
            juju.exec(
                f"relation-set -r {peer_relation_id} hostname-details='{json.dumps(old_format)}'",
                unit=unit_name,
            )
            logging.info(f"Converted {unit_name}: {old_format}")
        else:
            logging.info(f"Skipping {unit_name} - already in old format")

    # Give time for relation data to propagate
    time.sleep(5)
