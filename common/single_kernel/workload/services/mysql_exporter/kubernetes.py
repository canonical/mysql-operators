# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

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

    def install(self) -> None:
        """Install the service binaries."""
        pass

    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        layer = Layer({  # type: ignore
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
                        "EXPORTER_USER": username,
                        "EXPORTER_PASS": password,
                    },
                },
            },
        })

        self._container.add_layer(label=self.name, layer=layer, combine=True)

    def start(self) -> None:
        """Start the service."""
        logger.info(f"Starting service {self.name}")
        self._container.start(self.name)

    def stop(self) -> None:
        """Stop the service."""
        logger.info(f"Stopping service {self.name}")
        self._container.stop(self.name)
