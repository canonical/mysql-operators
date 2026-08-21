# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from .base import BaseSystem
from .paths import SnapPaths
from .runtimes import MachineRuntime
from .shells import MachineShell


class VMSystem(BaseSystem):
    """Class to deal with a system."""

    user = "snap_daemon"
    group = "root"

    def __init__(self, paths: SnapPaths, runtime: MachineRuntime):
        """Initialize the class attributes."""
        self._paths = paths
        self._runtime = runtime

    @property
    def paths(self) -> SnapPaths:
        """Return the filesystem object."""
        return self._paths

    @property
    def runtime(self) -> MachineRuntime:
        """Return the runtime object."""
        return self._runtime

    @property
    def shell(self) -> MachineShell:
        """Return the shell object."""
        return MachineShell(self.user, self.group)
