# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import MutableMapping

from ...data import ReplicationData


class ReplicationAppState(ReplicationData):
    """Class to deal with the replication application state."""

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        super().__init__(data)
