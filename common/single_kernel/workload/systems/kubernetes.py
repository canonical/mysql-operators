# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Container

from .base import BaseSystem
from .paths import RockPaths
from .runtimes import ContainerRuntime
from .shells import ContainerShell


class K8sSystem(BaseSystem):
    """Class to deal with a system."""

    user = "mysql"
    group = "mysql"

    def __init__(self, paths: RockPaths, runtime: ContainerRuntime, container: Container):
        """Initialize the class attributes."""
        self._paths = paths
        self._runtime = runtime
        self._container = container

    @property
    def paths(self) -> RockPaths:
        """Return the filesystem object."""
        return self._paths

    @property
    def runtime(self) -> ContainerRuntime:
        """Return the runtime object."""
        return self._runtime

    @property
    def shell(self) -> ContainerShell:
        """Return the shell object."""
        return ContainerShell(self._container, self.user, self.group)
