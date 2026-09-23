# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from charm_refresh import CharmSpecificMachines, Machines

from ...managers import Clients
from .base import BaseRefreshHandler

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class VMRefreshHandler(BaseRefreshHandler, CharmSpecificMachines):
    """Class to deal with the operator refresh."""

    charm_name = "mysql"
    workload_name = "MySQL"

    def __init__(self, charm: BaseCharm, clients: Clients):
        """Initialize the class attributes."""
        super().__init__(charm, clients)
        super().__post_init__()

    def refresh_snap(self, *, snap_name: str, snap_revision: str, refresh: Machines) -> None:
        """Refresh the installed snap."""
        self._charm.service_exporter.stop()
        self._charm.service_server.stop()

        logger.info(f"Installing snap revision {snap_revision}")
        self._charm.service_server.install(snap_revision)
        self._charm.service_server.start()
        self._charm.service_exporter.start()
