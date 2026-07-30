# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""A collection of utility functions that are used in the charm."""

import logging
import os
import re
import secrets
import socket
import string

from tenacity import retry, stop_after_delay, wait_fixed

logger = logging.getLogger(__name__)


def generate_pebble_layer_env() -> dict[str, str]:
    """Generates the pebble layer environment.

    When any HTTP or HTTPS proxy is configured, `.svc.cluster.local` is
    always included in NO_PROXY so that internal Kubernetes pod-to-pod
    traffic is never routed through a corporate proxy.
    """
    external_http_proxy = os.getenv("JUJU_CHARM_HTTP_PROXY", "")
    external_https_proxy = os.getenv("JUJU_CHARM_HTTPS_PROXY", "")
    internal_proxy = os.getenv("JUJU_CHARM_NO_PROXY", "")

    internal_domain = ".svc.cluster.local"
    environment = {}

    if external_http_proxy:
        environment["HTTP_PROXY"] = external_http_proxy
    if external_https_proxy:
        environment["HTTPS_PROXY"] = external_https_proxy
    if internal_proxy:
        environment["NO_PROXY"] = internal_proxy

    if external_http_proxy or external_https_proxy:
        internal_proxy_entries = {entry.strip() for entry in internal_proxy.split(",")}
        internal_proxy_entries.add(internal_domain)
        environment["NO_PROXY"] = ",".join(internal_proxy_entries)

    return environment


def generate_random_password(length: int) -> str:
    """Randomly generate a string intended to be used as a password.

    Args:
        length: length of the randomly generated string to be returned
    Returns:
        A randomly generated string intended to be used as a password.
    """
    choices = string.ascii_letters + string.digits
    return "".join([secrets.choice(choices) for _ in range(length)])


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


@retry(reraise=True, stop=stop_after_delay(30), wait=wait_fixed(0.5))
def get_k8s_fqdn(name: str, local_unit_label: str) -> str:
    """Resolve the canonical FQDN for a Kubernetes service or pod name.

    Fully-qualified domain names always have a trailing dot
    representing the root of the DNS hierarchy, as per RFC 1034.

    Args:
        name: The Kubernetes service or pod name to resolve.
        local_unit_label: The label of the local unit (e.g., "mysql-k8s-1")

    Examples:
        >>> get_k8s_fqdn("mysql-k8s-0.mysql-k8s-endpoints", local_unit_label="mysql-k8s-0")
        'mysql-k8s-0.mysql-k8s-endpoints.jubilant-a65bb303.svc.cluster.local.'
        >>> get_k8s_fqdn("mysql-k8s-1.mysql-k8s-endpoints", local_unit_label="mysql-k8s-0")
        'mysql-k8s-1.mysql-k8s-endpoints.jubilant-a65bb303.svc.cluster.local.'
    """

    def _addrinfo(_name):
        try:
            info = socket.getaddrinfo(
                _name,
                None,
                family=socket.AF_UNSPEC,
                flags=socket.AI_CANONNAME,
                type=socket.SOCK_STREAM,
            )
            return info
        except socket.gaierror as e:
            raise RuntimeError(f"Failed to resolve canonical {_name=}") from e

    # fqdn resolve local in /etc/hosts
    name_prefix = name.split(".")[0]
    logger.debug(
        "get_k8s_fqdn: name=%r name_prefix=%r local_unit_label=%r",
        name,
        name_prefix,
        local_unit_label,
    )
    info = _addrinfo(local_unit_label)

    for entry in info:
        if canonname := entry[3]:
            if local_unit_label == name_prefix:
                logger.debug("get_k8s_fqdn: local unit path -> canonname=%r", canonname)
                return dotappend(canonname)
            else:
                # for peer units, replace the local unit pod name in the fqdn (cannoname) with the
                # peer unit pod name (name_prefix)
                # e.g.:
                # cannoname: mysql-k8s-0.mysql-k8s-endpoints.default.svc.cluster.local
                # name_prefix: mysql-k8s-1
                # fqdn = mysql-k8s-1.mysql-k8s-endpoints.default.svc.cluster.local
                fqdn = ".".join([name_prefix, *canonname.split(".")[1:]])
                logger.debug(
                    "get_k8s_fqdn: peer unit path -> canonname=%r fqdn=%r",
                    canonname,
                    fqdn,
                )
                # dotappend other units as local unit is mapped without end dot in /etc/hosts
                return dotappend(fqdn)

    # fallback to DNS
    logger.debug(
        "get_k8s_fqdn: no canonname from local lookup, falling back to DNS for name=%r", name
    )
    info = _addrinfo(name)
    for entry in info:
        if canonname := entry[3]:
            logger.debug("get_k8s_fqdn: DNS entry canonname=%r", canonname)
            return dotappend(canonname)

    raise RuntimeError(f"Could not determine canonical for {name=}")
