# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from functools import cached_property

from ops.charm import ConfigChangedEvent, RelationBrokenEvent, RelationCreatedEvent
from ops.framework import EventBase, EventSource, Object

from ...managers import LogrotateManager
from ...services import LogrotateService
from ..helpers import EventHelpers

if typing.TYPE_CHECKING:
    from ...charm import BaseCharm

logger = logging.getLogger(__name__)


class LogRotationEvent(EventBase):
    """Custom event to rotate the MySQL logs."""


class LogRotationEventHandler(Object):
    """Class to deal with the log-rotation events."""

    log_rotation = EventSource(LogRotationEvent)

    def __init__(
        self,
        charm: BaseCharm,
        helpers: EventHelpers,
        manager: LogrotateManager,
        service: LogrotateService,
        relation: str,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "log-rotation")
        self._charm = charm
        self._helpers = helpers
        self._manager = manager
        self._service = service

        self._relation = relation

        self.framework.observe(self._charm.on.log_rotation, self._on_rotate_logs)
        self.framework.observe(self._charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self._charm.on[relation].relation_created, self._on_relation_created)
        self.framework.observe(self._charm.on[relation].relation_broken, self._on_relation_broken)

    @cached_property
    def _synchronized(self) -> bool:
        """Return whether the logs are being synchronized."""
        return bool(self._manager.get_synced_flag())

    def _update_config(self):
        """Update the logrotate configuration."""
        logger.info("Configuring logrotate")

        log_types = self._manager.text_logs
        if self._charm.config.plugin_audit_enabled:
            log_types.append("audit")

        retention_days = self._charm.config.logs_retention_period
        if retention_days == "auto":
            retention_days = 1 if self._synchronized else 3

        self._service.setup(
            retention_days=int(retention_days),
            compress=self._synchronized,
            log_types=[log.lower() for log in log_types],
        )

    def _on_relation_created(self, event: RelationCreatedEvent) -> None:
        """Event handler for the COS relation-created event."""
        if not self._helpers.initialized:
            logger.debug("Deferring logging configuration: charm not initialized")
            event.defer()
            return

        self._manager.set_synced_flag(True)
        self._update_config()

    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Event handler for the config-changed event."""
        if not self._helpers.initialized:
            logger.debug("Skipping logging configuration: charm not initialized")
            return

        self._update_config()

    def _on_relation_broken(self, _: RelationBrokenEvent) -> None:
        """Event handler for the COS relation-broken event."""
        if not self._helpers.initialized:
            return

        self._manager.delete_synced_flag()
        self._update_config()

    def _on_rotate_logs(self, _: LogRotationEvent) -> None:
        """Event handler for the rotate-mysql-logs event."""
        if not self._helpers.initialized:
            return
        if self._charm.refreshing:
            return

        self._manager.rotate_logs(self._charm.config.plugin_audit_enabled)
