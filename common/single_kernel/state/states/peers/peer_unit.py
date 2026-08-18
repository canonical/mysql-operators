# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import MutableMapping

from ...data import AddressData, InstanceData, LogrotateData, SelfHealingData


class PeerStateUnit(AddressData, InstanceData, LogrotateData, SelfHealingData):
    """Class to deal with the peer unit state."""

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        super().__init__(data)
