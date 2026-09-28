# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""A collection of utility functions that are used in the charm."""

import secrets
import string


def _password_meets_rules(password: str) -> bool:
    """Check that a password meets MySQL password validation rules.

    Requires at least one lowercase letter, one uppercase letter, and one digit.
    """
    return all((
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
    ))


def generate_random_password(length: int) -> str:
    """Randomly generate a string intended to be used as a password.

    Args:
        length: length of the randomly generated string to be returned

    Returns:
        a string with random letters and digits of length specified
    """
    choices = string.ascii_letters + string.digits
    # Might seem risky but in fact the probability that a password doesn't pass these checks is low
    while True:
        password = "".join(secrets.choice(choices) for _ in range(length))
        if _password_meets_rules(password):
            return password


def compare_dictionaries(dict1: dict, dict2: dict) -> set:
    """Compare two dictionaries and return a set of keys that are different."""
    different_keys = set()

    # exiting keys with different values
    for key in dict1:
        if key in dict2 and dict1[key] != dict2[key]:
            different_keys.add(key)

    # non existent keys
    different_keys = different_keys | dict2.keys() ^ dict1.keys()

    return different_keys
