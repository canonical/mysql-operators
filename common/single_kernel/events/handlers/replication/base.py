# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from abc import ABC

from ops.charm import ActionEvent
from ops.framework import Object

from ....managers import BaseReplicationManager
from ...helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ....charm import BaseCharm

logger = logging.getLogger(__name__)


class BaseReplicationEventHandler(Object, ABC):
    """Class to deal with the replication events."""

    def __init__(
        self,
        charm: BaseCharm,
        manager: BaseReplicationManager,
        helpers: EventHelpers,
        relation: str,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, relation)
        self._charm = charm
        self._manager = manager
        self._helpers = helpers

        self.framework.observe(
            self._charm.on.create_replication_action,
            self._on_create_replication,
        )
        self.framework.observe(
            self._charm.on.rejoin_cluster_action,
            self._on_rejoin_cluster,
        )

    def _on_create_replication(self, event: ActionEvent) -> None:
        """Event handler for the create-replication action."""
        pass

    def _on_rejoin_cluster(self, event: ActionEvent) -> None:
        """Event handler for the rejoin-cluster action."""
        pass
