# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from ...systems import VMSystem
from .base import BaseExporterService

try:
    import charmlibs.snap as snap
    import charmlibs.systemd as systemd
except ImportError:
    pass

logger = logging.getLogger(__name__)


class VMExporterService(BaseExporterService):
    """Class to deal with the MySQL exporter service lifecycle."""

    snap_name = "charmed-mysql"

    def __init__(self, system: VMSystem):
        """Initialize the class attributes."""
        self._system = system

    @property
    def running(self) -> bool:
        """Return whether the service is running."""
        return systemd.service_running(f"snap.{self.snap_name}.{self.name}")

    def install(self, revision: str | None = None) -> None:
        """Install the service binaries."""
        pass

    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        try:
            snap.list_one(self.snap_name)
        except snap.NotInstalledError:
            raise RuntimeError(f"Snap {self.snap_name} not installed")

        snap.set(
            snap=self.snap_name,
            config={"exporter.user": username, "exporter.password": password},
        )

    def start(self) -> None:
        """Start the service."""
        try:
            snap.list_one(self.snap_name)
        except snap.NotInstalledError:
            raise RuntimeError(f"Snap {self.snap_name} not installed")

        try:
            logger.info(f"Starting service {self.snap_name}.{self.name}")
            snap.start(snap=self.snap_name, services=[self.name], enable=True)
        except snap.APIError as e:
            logger.error(f"Failed to start service {self.snap_name}.{self.name}: {e}")
            raise
        else:
            self._wait_for_connection()

    def stop(self) -> None:
        """Stop the service."""
        try:
            snap.list_one(self.snap_name)
        except snap.NotInstalledError:
            raise RuntimeError(f"Snap {self.snap_name} not installed")

        try:
            logger.info(f"Stopping service {self.snap_name}.{self.name}")
            snap.stop(snap=self.snap_name, services=[self.name], disable=True)
        except snap.APIError as e:
            logger.error(f"Failed to stop service {self.snap_name}.{self.name}: {e}")
            raise
