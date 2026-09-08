# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Generic, Type, TypeVar

from ops.charm import CharmBase
from pydantic.main import BaseModel

T = TypeVar("T", bound=BaseModel)


class TypedCharmBase(CharmBase, Generic[T]):
    """Class for extending config-typed charms."""

    config_type: Type[T]

    @property
    def config(self) -> T:
        """Return a config instance validated and parsed."""
        translated_keys = {k.replace("-", "_"): v for k, v in self.model.config.items()}
        return self.config_type(**translated_keys)
