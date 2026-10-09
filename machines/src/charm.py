# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import platform

from ops.charm import CharmBase
from ops.main import main
from ops.model import BlockedStatus
from single_kernel.charm import VMCharm, check_architecture


class WrongArchitectureCharm(CharmBase):
    """Class that signals a wrong architecture got deployed."""

    def __init__(self, *args):
        """Initialize the class attributes."""
        super().__init__(*args)

        hardware_arch = platform.machine()
        self.unit.status = BlockedStatus(
            f"Charm incompatible with {hardware_arch} architecture. "
            f"If this app is being refreshed, rollback"
        )
        raise RuntimeError(
            f"Incompatible architecture: this charm revision does not support {hardware_arch}. "
            f"If this app is being refreshed, rollback with instructions from Charmhub docs. "
            f"If this app is being deployed for the first time, remove it and deploy it again "
            f"using a compatible revision."
        )


if __name__ == "__main__":
    if check_architecture():
        main(VMCharm)
    else:
        main(WrongArchitectureCharm)
