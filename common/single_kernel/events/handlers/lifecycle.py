# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import typing

from ops.charm import (
    ConfigChangedEvent,
    InstallEvent,
    LeaderElectedEvent,
    StartEvent,
    StorageDetachingEvent,
    UpdateStatusEvent,
)
from ops.framework import Object
from ops.model import BlockedStatus, WaitingStatus

from ...core import ServiceRole
from ...managers import LifecycleManager
from ...workload import BaseServerService
from ..helpers import Helpers

if typing.TYPE_CHECKING:
    from ...charm import Operator

logger = logging.getLogger(__name__)


class LifecycleEventHandler(Object):
    """Class to deal with the operator lifecycle events."""

    def __init__(
        self,
        charm: Operator,
        manager: LifecycleManager,
        service: BaseServerService,
        helpers: Helpers,
    ):
        """Initialize the class attributes."""
        super().__init__(charm, "lifecycle")
        self._charm = charm
        self._manager = manager
        self._service = service
        self._helpers = helpers

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)

        self.framework.observe(self.on.archive_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.data_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.logs_storage_detaching, self._on_storage_detaching)
        self.framework.observe(self.on.temp_storage_detaching, self._on_storage_detaching)

    def _create_service(self, service_role: ServiceRole) -> None:
        """Create a runtime service."""
        cluster_name = f"{self._manager.get_cluster_name()}"
        service_name = f"{self._charm.app.name}-{service_role}"

        try:
            self._charm.system.runtime.create_service(
                name=service_name,
                labels={
                    "application-name": self._charm.app.name,
                    "cluster-name": cluster_name,
                    "role": service_role,
                },
            )
        except RuntimeError as e:
            logger.error(f"Failed to create service: {e}")
            raise

    def _on_install(self, _: InstallEvent) -> None:
        """Event handler for the install event."""
        try:
            self._service.install()
        except Exception:
            self._charm.set_unit_status(BlockedStatus("Failed to install and configure MySQL"))
        else:
            self._charm.set_unit_status(WaitingStatus("Waiting to start MySQL"))

    def _on_start(self, event: StartEvent) -> None:
        """Event handler for the start event."""
        # Create the services as early as possible in the charm lifecycle so that
        # runtime issues (e.g. a missing `juju trust`) surface before the workload is initialized.
        if self._charm.unit.is_leader():
            try:
                self._create_service("primary")
                self._create_service("replicas")
            except RuntimeError:
                self._charm.set_unit_status(BlockedStatus("Run `juju trust <app-name>`"))
                event.defer()
                return

        if not self._charm.initialized:
            logger.debug("Deferring operator start: charm not initialized")
            event.defer()
            return

    def _on_leader_elected(self, event: LeaderElectedEvent) -> None:
        """Event handler for the leader-elected event."""
        pass

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Event handler for the config-changed event."""
        pass

    def _on_update_status(self, event: UpdateStatusEvent) -> None:
        """Event handler for the update-status event."""
        pass

    def _on_storage_detaching(self, event: StorageDetachingEvent) -> None:
        """Event handler for the storage-detaching event."""
        pass
