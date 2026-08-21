# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod


class BaseExporterService(ABC):
    """Class to deal with the MySQL exporter service lifecycle."""

    name = "mysqld-exporter"

    @abstractmethod
    @property
    def running(self) -> bool:
        """Return whether the service is running."""
        raise NotImplementedError()

    @abstractmethod
    def install(self) -> None:
        """Install the service binaries."""
        raise NotImplementedError()

    @abstractmethod
    def setup(self, username: str, password: str) -> None:
        """Return the service configuration."""
        raise NotImplementedError()

    @abstractmethod
    def start(self) -> None:
        """Start the service."""
        raise NotImplementedError()

    @abstractmethod
    def stop(self) -> None:
        """Stop the service."""
        raise NotImplementedError()
