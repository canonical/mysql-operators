# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod

from .paths import BasePaths
from .runtimes import BaseRuntime
from .shells import BaseShell


class BaseSystem(ABC):
    """Abstract class to deal with a system."""

    user: str
    group: str

    @property
    @abstractmethod
    def paths(self) -> BasePaths:
        """Return the filesystem object."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def runtime(self) -> BaseRuntime:
        """Return the runtime object."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def shell(self) -> BaseShell:
        """Return the shell object."""
        raise NotImplementedError()
