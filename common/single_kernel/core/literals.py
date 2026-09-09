# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Literal

RefreshPause = Literal["all", "first", "none"]
ServiceRole = Literal["primary", "replicas", "offline"]
Substrate = Literal["K8S", "VM"]
