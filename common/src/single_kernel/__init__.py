# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import warnings

from pydantic.warnings import UnsupportedFieldAttributeWarning

# Data Platform library package embeds Field(exclude=True, default=None) in
# Annotated type aliases (e.g. UserSecretStr, TlsSecretStr).
# Pydantic 2.13+warns about both attributes in that context.
warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)
