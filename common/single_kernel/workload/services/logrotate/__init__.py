# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from .base import BaseLogrotateService
from .kubernetes import K8sLogrotateService
from .machines import VMLogrotateService
