# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Service custom events."""

from ops.charm import CharmEvents
from ops.framework import EventSource

from services.observers.ip_address_observer import IPAddressChangeEvent
from services.observers.log_rotate_observer import RotateMySQLLogsEvent


class CharmServicesEvents(CharmEvents):
    """A CharmEvent extension with all the services events."""

    ip_address_change = EventSource(IPAddressChangeEvent)
    rotate_mysql_logs = EventSource(RotateMySQLLogsEvent)
