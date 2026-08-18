# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import MutableMapping

from ...data import ClusterData, TLSData


class PeerStateApp(ClusterData, TLSData):
    """Class to deal with the peer application state."""

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        super().__init__(data)
