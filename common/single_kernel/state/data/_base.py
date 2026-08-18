# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import MutableMapping


class BaseData:
    """Abstract class to deal with persisted data."""

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        self._data = data
