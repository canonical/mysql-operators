# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Literal

EndpointRole = Literal["primary", "replicas", "offline"]
RefreshPause = Literal["all", "first", "none"]
Substrate = Literal["K8S", "VM"]
