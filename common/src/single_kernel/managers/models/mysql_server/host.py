# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class MachineHost:
    """Class to hold all the host information together."""

    address: str
    names: Sequence[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Deserializes the JSON into a dataclass object."""
        return cls(**data)

    def into_dict(self) -> dict[str, Any]:
        """Serializes the dataclass into JSON format."""
        return self.__dict__
