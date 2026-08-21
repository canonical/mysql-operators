# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from charmlibs.snap import SnapCache, SnapError

from ...systems import VMSystem
from .base import BaseExporterService

logger = logging.getLogger(__name__)


class VMExporterService(BaseExporterService):
    """Class to deal with the MySQL exporter service lifecycle."""

    snap_name = "charmed-mysql"

    def __init__(self, system: VMSystem):
        """Initialize the class attributes."""
        self._system = system
        self._cache = SnapCache()

    def install(self) -> None:
        """Install the service binaries."""
        pass

    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        snap = self._cache[self.snap_name]
        if not snap.present:
            raise RuntimeError(f"Snap {self.snap_name} not installed")

        snap.set({
            "exporter.user": username,
            "exporter.password": password,
        })

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
