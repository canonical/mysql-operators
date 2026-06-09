# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Service custom events."""

from ops.charm import CharmEvents
from ops.framework import EventSource

from services.observers.log_rotate_observer import RotateMySQLLogsEvent


class CharmServicesEvents(CharmEvents):
    """A CharmEvent extension with all the services events."""

    rotate_mysql_logs = EventSource(RotateMySQLLogsEvent)
