# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os

import tenacity
from mysql_shell import BaseExecutor
from ops.model import Container
from ops.pebble import ChangeError, Layer

from ...systems import K8sSystem
from .base import BaseServerService

logger = logging.getLogger(__name__)


class K8sServerService(BaseServerService):
    """Class to deal with the MySQL server service lifecycle."""

    def __init__(self, system: K8sSystem, container: Container, executor: BaseExecutor):
        """Initialize the class attributes."""
        self._system = system
        self._container = container
        self._executor = executor

    def _generate_layer_env(self) -> dict[str, str]:
        """Generates the pebble layer environment.

        When any HTTP or HTTPS proxy is configured, `.svc.cluster.local` is
        always included in NO_PROXY so that internal Kubernetes pod-to-pod
        traffic is never routed through a corporate proxy.
        """
        external_http_proxy = os.getenv("JUJU_CHARM_HTTP_PROXY", "")
        external_https_proxy = os.getenv("JUJU_CHARM_HTTPS_PROXY", "")
        internal_proxy = os.getenv("JUJU_CHARM_NO_PROXY", "")

        internal_domain = ".svc.cluster.local"
        environment = {}

        if external_http_proxy:
            environment["HTTP_PROXY"] = external_http_proxy
        if external_https_proxy:
            environment["HTTPS_PROXY"] = external_https_proxy
        if internal_proxy:
            environment["NO_PROXY"] = internal_proxy

        if external_http_proxy or external_https_proxy:
            internal_proxy_entries = {entry.strip() for entry in internal_proxy.split(",")}
            internal_proxy_entries.add(internal_domain)
            environment["NO_PROXY"] = ",".join(internal_proxy_entries)

        return environment

    def _init_directories(self) -> None:
        """Initializes the service directories."""
        logger.debug("Initializing server directories")

        self._system.shell.execute_sync([
            f"/usr/sbin/mysqld",
            f"--initialize",
            f"--user={self._system.user}",
            f"--datadir={self._system.paths.mysql_data}",
            f"--innodb-log-group-home-dir={self._system.paths.mysql_logs}",
            f"--innodb-undo-directory={self._system.paths.mysql_logs}",
            f"--innodb-temp-tablespaces-dir={self._system.paths.mysql_temp}",
        ])

    def _reset_directories(self) -> None:
        """Reset the service directories."""
        logger.debug("Resetting server directories")

        for path in (
            str(self._system.paths.mysql_data),
            str(self._system.paths.mysql_logs),
            str(self._system.paths.mysql_temp),
        ):
            self._system.shell.execute_sync(["find", path, "-maxdepth 1", "-delete"])

    def _set_operator_user(self, username: str, password: str) -> None:
        """Set the service main username / password pair."""
        logger.debug("Set operator username and password")

        custom_home_path = self._system.paths._root / "home" / self._system.user
        custom_sql_file = custom_home_path / "create-operator-user.sql"
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
            self._wait_for_connection()
            self.stop()
        except ChangeError as e:
            logger.error(f"Failed to restart service {self.name}: {e}")
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
        pass

    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        self._reset_directories()
        self._init_directories()
        self._set_operator_user(username, password)

        daemon_command = " ".join([
            f"/usr/sbin/mysqld",
            f"--basedir=/usr",
            f"--datadir={self._system.paths.mysql_data}",
            f"--plugin-dir={self._system.paths.mysql_plugins}",
            f"--log-error={self._system.paths.mysql_logs / 'error.log'}",
        ])
        logging_command = " ".join([
            f"/usr/bin/tail",
            f"--follow={self._system.paths.mysql_logs / 'error.log'}",
        ])

        layer = Layer({  # type: ignore
            "summary": "MySQL server layer",
            "description": "Layer for the MySQL server service",
            "services": {
                self.name: {
                    "summary": "MySQL daemon",
                    "override": "replace",
                    "command": daemon_command,
                    "startup": "enabled",
                    "user": self._system.user,
                    "group": self._system.group,
                    "after": ["logs"],
                    "requires": ["logs"],
                    "kill-delay": "24h",
                    "environment": {
                        "MYSQLD_PARENT_PID": 1,
                        **self._generate_layer_env(),
                    },
                },
                "logs": {
                    "summary": "MySQL daemon tail logs",
                    "override": "replace",
                    "command": logging_command,
                    "startup": "enabled",
                },
            },
        })

        self._container.add_layer(label=self.name, layer=layer, combine=True)

    def start(self) -> None:
        """Start the service."""
        logger.info(f"Starting service {self.name}")
        self._container.start(self.name)
        self._wait_for_connection()

    def stop(self) -> None:
        """Stop the service."""
        logger.info(f"Stopping service {self.name}")
        self._container.stop(self.name)
