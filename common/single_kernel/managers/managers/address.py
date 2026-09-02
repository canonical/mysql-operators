# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Mapping, Sequence

from mysql_shell import ExecutionError

from ...state import AddressResolutionState
from ...workload import BaseSystem
from ..clients import MySQLClusterClient, MySQLInstanceClient

logger = logging.getLogger(__name__)


class AddressResolutionManager:
    """Class to deal with the address-resolution operations."""

    def __init__(
        self,
        state: AddressResolutionState,
        system: BaseSystem,
        cluster_client: MySQLClusterClient,
        instance_client: MySQLInstanceClient,
    ):
        """Initialize the class attributes."""
        self._state = state
        self._system = system

        self._cluster_client = cluster_client
        self._instance_client = instance_client

    def update_hosts(self, addresses: Sequence[str], names: Mapping[str, list]) -> None:
        """Update hosts."""
        logger.debug("Updating address hosts")

        self._system.runtime.remove_hosts()
        for address in addresses:
            self._system.runtime.update_hosts(address, names[address])

        try:
            self._instance_client.flush_host_cache()
        except ExecutionError as e:
            logger.warning(f"Failed to flush MySQL host cache: {e}")
