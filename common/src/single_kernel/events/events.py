# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.charm import CharmEvents
from ops.framework import EventSource

from .handlers.address import AddressChangeEvent
from .handlers.log_rotation import LogRotationEvent
from .handlers.self_healing import SelfHealingEvent


class CustomEvents(CharmEvents):
    """Class to hold all the charm custom events."""

    address_changed = EventSource(AddressChangeEvent)
    log_rotation = EventSource(LogRotationEvent)
    self_healing = EventSource(SelfHealingEvent)
