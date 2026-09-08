# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import StatusBase

from ..core import Substrate
from .base import TypedCharmBase
from .config import CharmConfig


class Operator(TypedCharmBase[CharmConfig]):
    """Class to encapsulate all operator logic."""

    def __init__(self, substrate: Substrate, *args, **kwargs):
        """Initialize the class attributes."""
        super().__init__(*args, **kwargs)
        self._substrate = substrate

        self._manager_operator = None
        self._service_exporter = None
        self._service_server = None

    @property
    def initialized(self) -> bool:
        """Return whether the operator is initialized."""
        return all((
            self._manager_operator.cluster_initialized,
            self._service_exporter.running,
            self._service_server.running,
        ))

    def set_unit_status(self, status: StatusBase) -> None:
        """Set the unit status."""
        self.unit.status = status
