# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import platform
import tomllib

import tenacity
from charmlibs.pathops import LocalPath
from charmlibs.snap import SnapCache, SnapError, SnapState
from mysql_shell import BaseExecutor

from ...systems import VMSystem
from .base import BaseServerService

logger = logging.getLogger(__name__)


class VMServerService(BaseServerService):
    """Class to deal with the MySQL server service lifecycle."""

    snap_name = "charmed-mysql"

    def __init__(self, system: VMSystem, executor: BaseExecutor):
        """Initialize the class attributes."""
        self._system = system
        self._cache = SnapCache()
        self._executor = executor

    def _init_directories(self) -> None:
        """Initializes the service directories."""
        logger.debug("Initializing server directories")

        self._system.shell.execute_sync([
            f"/usr/bin/sudo",
            f"/snap/bin/{self.snap_name}.mysqld-initialize",
            f"--datadir={self._system.paths.mysql_data}",
            f"--innodb-log-group-home-dir={self._system.paths.mysql_logs}",
            f"--innodb-undo-directory={self._system.paths.mysql_logs}",
            f"--innodb-temp-tablespaces-dir={self._system.paths.mysql_temp}",
        ])

    def _reset_directories(self) -> None:
        """Reset the service directories."""
        logger.debug("Resetting server directories")
        owner = f"{self._system.user}:{self._system.group}"

        for path in (
            str(self._system.paths.mysql_data),
            str(self._system.paths.mysql_logs),
            str(self._system.paths.mysql_temp),
        ):
            self._system.shell.execute_sync(["find", path, "-maxdepth 1", "-delete"])
            self._system.shell.execute_sync(["chown", owner, path])

    def _set_operator_user(self, username: str, password: str) -> None:
        """Set the service main username / password pair."""
        logger.debug("Set operator username and password")

        custom_sql_file = self._system.paths._common / "create-operator-user.sql"
        custom_sql_file.write_text(
            data="\n".join((
                f"CREATE USER '{username}'@'%' IDENTIFIED BY '{password}';",
                f"GRANT ALL ON *.* TO '{username}'@'%' WITH GRANT OPTION;",
            )),
            mode=0o600,
            user=self._system.user,
            group=self._system.group,
        )

        custom_cnf_file = self._system.paths.mysql_config_custom
        custom_cnf_file.write_text(
            data="\n".join((
                f"[mysqld]",
                f"init_file = {custom_sql_file}",
            )),
            mode=0o600,
            user=self._system.user,
            group=self._system.group,
        )

        try:
            self.start()
            self.stop()
        except SnapError as e:
            logger.error(f"Failed to restart service {self.snap_name}.{self.name}: {e}")
            raise
        finally:
            custom_sql_file.unlink()
            custom_cnf_file.unlink()

    def _wait_for_connection(self) -> None:
        """Wait for service connection."""
        if not self._system.paths.mysql_socket.exists():
            raise RuntimeError("MySQL server socket missing")

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_delay(120),
            wait=tenacity.wait_fixed(2),
            reraise=True,
        ):
            with attempt:
                self._executor.check_connection()

    def install(self) -> None:
        """Install the service binaries."""
        snap = self._cache[self.snap_name]

        version_file = LocalPath("refresh_versions.toml")
        version_data = tomllib.loads(version_file.read_text())
        version_rev = version_data["snap"]["revisions"][platform.machine()]

        try:
            logger.debug("Installing service snap")
            snap.ensure(state=SnapState.Present, revision=version_rev)
            snap.hold()

            for binary in [
                "mysql",
                "mysqlbinlog",
                "mysqlrouter",
                "mysqlsh",
                "xbcloud",
                "xbstream",
                "xtrabackup",
            ]:
                snap.alias(binary)
        except SnapError as e:
            logger.exception(f"Failed to install snap {self.snap_name}: {e}")
            raise

    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        self._reset_directories()
        self._init_directories()
        self._set_operator_user(username, password)

    def start(self) -> None:
        """Start the service."""
        snap = self._cache[self.snap_name]
        if not snap.present:
            raise RuntimeError(f"Snap {self.snap_name} not installed")

        try:
            logger.info(f"Starting service {self.snap_name}.{self.name}")
            snap.start(services=[self.name], enable=True)
        except SnapError as e:
            logger.error(f"Failed to start service {self.snap_name}.{self.name}: {e}")
            raise
        else:
            self._wait_for_connection()

    def stop(self) -> None:
        """Stop the service."""
        snap = self._cache[self.snap_name]
        if not snap.present:
            raise RuntimeError(f"Snap {self.snap_name} not installed")

        try:
            logger.info(f"Stopping service {self.snap_name}.{self.name}")
            snap.stop(services=[self.name], disable=True)
        except SnapError as e:
            logger.error(f"Failed to stop service {self.snap_name}.{self.name}: {e}")
            raise
