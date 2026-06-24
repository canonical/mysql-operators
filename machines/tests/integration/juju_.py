# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import importlib.metadata

import ops

# libjuju version != juju agent version, but the major version should be identical—which is good
# enough to check for secrets
_libjuju_version = importlib.metadata.version("juju")
has_secrets = ops.JujuVersion(_libjuju_version).has_secrets

juju_major_version = int(_libjuju_version.split(".")[0])
