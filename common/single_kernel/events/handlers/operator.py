# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import (
    ActionEvent,
    RelationChangedEvent,
    RelationJoinedEvent,
)
from ops.framework import Object

from ...core import RELATION_PEERS
from ...managers import OperatorManager
from ...workload import BaseServerService
from ..helpers import Helpers

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class OperatorEventHandler(Object):
    """Class to deal with the operator events."""

    def __init__(
        self,
        charm: Operator,
        manager: OperatorManager,
        service: BaseServerService,
        helpers: Helpers,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "operator")
        self._charm = charm
        self._manager = manager
        self._service = service
        self._helpers = helpers

        self.framework.observe(self.on.get_cluster_status_action, self._on_get_cluster_status)
        self.framework.observe(self.on.get_password_action, self._on_get_password)
        self.framework.observe(self.on.set_password_action, self._on_set_password)
        self.framework.observe(self.on.promote_to_primary_action, self._on_promote_to_primary)
        self.framework.observe(self.on.recreate_cluster_action, self._on_recreate_cluster)

        self.framework.observe(
            self.on[RELATION_PEERS].relation_joined,
            self._on_relation_joined,
        )
        self.framework.observe(
            self.on[RELATION_PEERS].relation_changed,
            self._on_relation_changed,
        )

    def _on_get_cluster_status(self, event: ActionEvent) -> None:
        """Event handler for the get-cluster-status action."""
        pass

    def _on_get_password(self, event: ActionEvent) -> None:
        """Event handler for the get-password action."""
        pass

    def _on_set_password(self, event: ActionEvent) -> None:
        """Event handler for the set-password action."""
        pass

    def _on_promote_to_primary(self, event: ActionEvent) -> None:
        """Event handler for the promote-to-primary action."""
        pass

    def _on_recreate_cluster(self, event: ActionEvent) -> None:
        """Event handler for the recreate-cluster action."""
        pass

    def _on_relation_joined(self, event: RelationJoinedEvent) -> None:
        """Event handler for the relation-joined event."""
        pass

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event handler for the relation-changed event."""
        pass
