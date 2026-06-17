# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import jubilant_backports

juju = jubilant_backports.Juju()

has_secrets = not juju._is_juju_2
juju_major_version = 2 if juju._is_juju_2 else 3
