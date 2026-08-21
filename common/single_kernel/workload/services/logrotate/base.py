# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod
from typing import Sequence


class BaseLogrotateService(ABC):
    """Class to deal with the logrotate service lifecycle."""

    @abstractmethod
    def install(self) -> None:
        """Install the service binaries."""
        raise NotImplementedError()

    @abstractmethod
    def setup(self, retention_days: int, compress: bool, log_types: Sequence[str]) -> None:
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
