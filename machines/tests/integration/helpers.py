# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import secrets
import string

logger = logging.getLogger(__name__)


def generate_random_string(length: int) -> str:
    """Generate a random string of the provided length.

    Args:
        length: the length of the random string to generate

    Returns:
        A random string comprised of letters and digits
    """
    choices = string.ascii_letters + string.digits
    return "".join([secrets.choice(choices) for i in range(length)])
