# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing
from functools import cached_property

from ops.framework import EventBase, Object

from ..managers import LogrotateManager
from ..services import LogrotateService

if typing.TYPE_CHECKING:
    from ..charm import Operator

logger = logging.getLogger(__name__)


class LogRotationEvent(EventBase):
    """Custom event to rotate the MySQL logs."""


class LogRotationEventHandler(Object):
    """Class to deal with the log-rotation events."""

    def __init__(
        self,
        charm: Operator,
        manager: LogrotateManager,
        service: LogrotateService,
        relation: str,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "log-rotation")
        self._charm = charm
        self._manager = manager
        self._service = service

        self._relation = relation

        self.framework.observe(self._charm.on.rotate_mysql_logs, self._rotate_logs)
        self.framework.observe(self._charm.on.update_status, self._update_config)
        self.framework.observe(self._charm.on[relation].relation_created, self._relation_created)
        self.framework.observe(self._charm.on[relation].relation_broken, self._relation_broken)

    @cached_property
    def _synchronized(self) -> bool:
        """Return whether the logs are being synchronized."""
        return bool(self._manager.get_synced_flag())

    def _relation_created(self, event: EventBase) -> None:
        """Event handler for the COS relation-created event."""
        if not self._charm.initialized:
            event.defer()
            logger.warning("Skipping logrotate config")
            return

        logger.info("Configuring logrotate before logs synchronization started")
        self._manager.set_synced_flag(True)
        self.update_config()

    def _relation_broken(self, _: EventBase) -> None:
        """Event handler for the COS relation-broken event."""
        if not self._charm.initialized:
            return

        logger.info("Configuring logrotate after logs synchronization stopped")
        self._manager.delete_synced_flag()
        self.update_config()

    def _rotate_logs(self, _: EventBase) -> None:
        """Event handler for the rotate-mysql-logs event."""
        if not self._charm.initialized:
            return

        self._manager.rotate_logs(self._charm.config.plugin_audit_enabled)

    def _update_config(self, _: EventBase) -> None:
        """Event handler for the update-status event."""
        if not self.model.get_relation(self._relation):
            return
        if self._synchronized:
            return

        self.update_config()

    def update_config(self):
        """Update the logrotate configuration."""
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
