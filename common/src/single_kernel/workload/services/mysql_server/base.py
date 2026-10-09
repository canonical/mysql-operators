# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import socket
from abc import ABC, abstractmethod

import tenacity


class BaseServerService(ABC):
    """Class to deal with the MySQL server service lifecycle."""

    name = "mysqld"
    port = 3306

    @property
    @abstractmethod
    def running(self) -> bool:
        """Return whether the service is running."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def initialized(self) -> bool:
        """Return whether the service has been initialized."""
        raise NotImplementedError()

    @abstractmethod
    def install(self, revision: str | None = None) -> None:
        """Install the service binaries."""
        raise NotImplementedError()

    @abstractmethod
    def setup(self, username: str, password: str) -> None:
        """Set up the service."""
        raise NotImplementedError()

    @abstractmethod
    def start(self) -> None:
        """Start the service."""
        raise NotImplementedError()

    @abstractmethod
    def stop(self) -> None:
        """Stop the service."""
        raise NotImplementedError()

    def _wait_for_connection(self) -> None:
        """Wait for service connection."""
        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_delay(120),
            wait=tenacity.wait_fixed(2),
            reraise=True,
        ):
            with attempt:
                conn = socket.create_connection(("127.0.0.1", self.port), timeout=1)
                conn.close()
