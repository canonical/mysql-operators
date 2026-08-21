# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging

from ops.model import Container
from ops.pebble import Layer

from ...systems import K8sSystem
from .base import BaseExporterService

logger = logging.getLogger(__name__)


class K8sExporterService(BaseExporterService):
    """Class to deal with the MySQL exporter service lifecycle."""

    def __init__(self, system: K8sSystem, container: Container):
        """Initialize the class attributes."""
        self._system = system
        self._container = container

    @property
    def running(self) -> bool:
        """Return whether the service is running."""
        services = self._container.get_services(self.name)
        if not services:
            return False

        return services[self.name].is_running()

    def _create_layer(self) -> Layer:
        """Creates the Pebble layer for the service.

        This must be called whenever the Pebble daemon starts with a clean state,
        not only during the initial setup. Pebble does not persist layers across restarts,
        so the layer must be re-pushed before any start / stop calls.
        """
        exporter_file = self._system.paths.home / self._system.user / "exporter.env"
        exporter_env = exporter_file.read_text()
        exporter_env = json.loads(exporter_env)

        return Layer({  # type: ignore
            "summary": "MySQL exporter layer",
            "description": "Layer for the MySQL exporter service",
            "services": {
                self.name: {
                    "summary": "MySQL exporter",
                    "override": "replace",
                    "command": "/start-mysqld-exporter.sh",
                    "startup": "enabled",
                    "user": self._system.user,
                    "group": self._system.group,
                    "environment": {
                        "EXPORTER_USER": exporter_env["username"],
                        "EXPORTER_PASS": exporter_env["password"],
                    },
                },
            },
        })

    def _set_exporter_user(self, username: str, password: str) -> None:
        """Set the service username / password pair."""
        logger.debug("Setting exporter username and password")

        exporter_file = self._system.paths.home / self._system.user / "exporter.env"
        exporter_file.write_text(
            data=json.dumps({
                "username": username,
                "password": password,
            }),
            mode=0o600,
            user=self._system.user,
            group=self._system.group,
        )

    def install(self, revision: str | None = None) -> None:
        """Install the service binaries."""
        pass

    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        self._set_exporter_user(username, password)

    def start(self) -> None:
        """Start the service."""
        logger.info(f"Starting service {self.name}")
        layer = self._create_layer()

        self._container.add_layer(label=self.name, layer=layer, combine=True)
        self._container.start(self.name)

    def stop(self) -> None:
        """Stop the service."""
        logger.info(f"Stopping service {self.name}")
        layer = self._create_layer()

        self._container.add_layer(label=self.name, layer=layer, combine=True)
        self._container.stop(self.name)
