# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import MutableMapping


class ReplicationUnitState:
    """Class to deal with the replication unit state."""

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        self._data = data
