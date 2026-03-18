# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""A collection of utility functions that are used in the charm."""

import re
import secrets
import socket
import string


def generate_random_password(length: int) -> str:
    """Randomly generate a string intended to be used as a password.

    Args:
        length: length of the randomly generated string to be returned
    Returns:
        A randomly generated string intended to be used as a password.
    """
    choices = string.ascii_letters + string.digits
    # Might seem risky but in fact the probability that a password doesn't pass these checks is low
    while True:
        password = "".join([secrets.choice(choices) for i in range(length)])
        # These checks are consistent with our rules for the password validation MySQL component
        if all((
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
        )):
            return password


def split_mem(mem_str) -> tuple:
    """Split a memory string into a number and a unit.

    Args:
        mem_str: a string representing a memory value, e.g. "1Gi"
    """
    pattern = r"^(\d+)(\w+)$"
    parts = re.match(pattern, mem_str)
    if parts:
        return parts.groups()
    return None, "No unit found"


def any_memory_to_bytes(mem_str) -> int:
    """Convert a memory string to bytes.

    Args:
        mem_str: a string representing a memory value, e.g. "1Gi"
    """
    units = {
        "KI": 1024,
        "K": 10**3,
        "MI": 1048576,
        "M": 10**6,
        "GI": 1073741824,
        "G": 10**9,
        "TI": 1099511627776,
        "T": 10**12,
    }
    try:
        num = int(mem_str)
        return num
    except ValueError:
        memory, unit = split_mem(mem_str)
        unit = unit.upper()
        if unit not in units:
            raise ValueError(f"Invalid memory definition in '{mem_str}'") from None

        num = int(memory)
        return int(num * units[unit])


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


def dotappend(string: str) -> str:
    """Append a dot to a string if it does not already end with one."""
    if not string.endswith("."):
        string += "."
    return string


def get_k8s_fqdn(name: str) -> str:
    """Resolve the canonical FQDN for a Kubernetes service or pod name."""
    try:
        info = socket.getaddrinfo(
            name,
            None,
            family=socket.AF_UNSPEC,
            flags=socket.AI_CANONNAME,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as e:
        raise RuntimeError(f"Failed to resolve canonical name for {name}") from e

    for entry in info:
        if canonname := entry[3]:
            return canonname

    raise RuntimeError(f"Could not determine canonical name for {name}")
