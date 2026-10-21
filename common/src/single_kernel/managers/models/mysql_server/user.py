# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from dataclasses import dataclass
from typing import Sequence


@dataclass
class SystemUser:
    """Class to hold all the system user information together."""

    username: str
    password: str
    roles: Sequence[str] | None = None
