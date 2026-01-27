# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import importlib.metadata

# libjuju version != juju agent version, but the major version should be identical—which is good
# enough to check for secrets
_libjuju_version = importlib.metadata.version("juju")
has_secrets = int(_libjuju_version.split(".")[0]) >= 3
juju_major_version = int(_libjuju_version.split(".")[0])
