#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers to run the integration tests behind a Squid forward proxy.

Squid is installed on the test runner host. While it is up, it is the only route to the
internet for the units under test: direct egress out of the LXD bridge is dropped, so a
charm that ignores the Juju proxy configuration cannot reach anything.

The tests do not run as root, so every step that touches the host (the package, the Squid
configuration, its log and the firewall) goes through passwordless sudo.
"""

import ipaddress
import json
import logging
import socket
import subprocess
from pathlib import Path

from jubilant_backports import Juju
from tenacity import Retrying, stop_after_delay, wait_fixed

MINUTE_SECS = 60

PROXY_PORT = 3128
SQUID_CONFIG_PATH = Path("/etc/squid/conf.d/99-juju-integration-test.conf")
SQUID_ACCESS_LOG_PATH = Path("/var/log/squid/access.log")

# Own iptables chain, so the rules can be removed without disturbing the LXD rules
EGRESS_CHAIN = "JUJU-PROXY-TEST"

# Model config keys set to route the units through the proxy (reset on teardown)
PROXY_CONFIG_KEYS = (
    "juju-http-proxy",
    "juju-https-proxy",
    "juju-no-proxy",
    "snap-http-proxy",
    "snap-https-proxy",
    "apt-http-proxy",
    "apt-https-proxy",
)


def _run(*command: str, check: bool = True) -> str:
    """Run a command on the test runner host and return its output."""
    result = subprocess.run(command, capture_output=True, check=False, text=True)
    if check and result.returncode:
        logging.error("Command %s failed: %s", command, result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode, command, result.stdout, result.stderr
        )

    return result.stdout.strip()


def _sudo(*command: str, check: bool = True) -> str:
    """Run a command on the test runner host as root, without a password prompt."""
    return _run("sudo", "--non-interactive", *command, check=check)


def _sudo_write(path: Path, content: str) -> None:
    """Write a file on the test runner host as root."""
    subprocess.run(
        ["sudo", "--non-interactive", "tee", str(path)],
        capture_output=True,
        check=True,
        input=content,
        text=True,
    )


def check_passwordless_sudo() -> bool:
    """Whether the tests can raise privileges without a password prompt."""
    return (
        subprocess.run(["sudo", "--non-interactive", "true"], capture_output=True).returncode == 0
    )


def get_lxd_bridge() -> tuple[str, str, str]:
    """Return the name, host address and network CIDR of the LXD bridge."""
    networks = json.loads(_run("lxc", "network", "list", "--format=json"))
    for network in networks:
        address = network.get("config", {}).get("ipv4.address", "none")
        if network["type"] == "bridge" and network["managed"] and address != "none":
            interface = ipaddress.ip_interface(address)
            return network["name"], str(interface.ip), str(interface.network)

    raise Exception("No managed LXD bridge with an IPv4 address found")


def get_controller_addresses() -> list[str]:
    """Return the API addresses of the controllers known to the client."""
    controllers = json.loads(_run("juju", "show-controller", "--format=json"))
    addresses = set()
    for controller in controllers.values():
        for endpoint in controller["details"]["api-endpoints"]:
            addresses.add(endpoint.rsplit(":", 1)[0].strip("[]"))

    return sorted(addresses)


def install_squid(allowed_cidr: str) -> None:
    """Install Squid on the test runner host and allow the given network through it."""
    logging.info("Installing squid on the test runner")
    _sudo("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "update", check=False)
    _sudo("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "--yes", "squid")

    logging.info("Allowing %s through squid", allowed_cidr)
    _sudo_write(
        SQUID_CONFIG_PATH, f"acl juju_units src {allowed_cidr}\nhttp_access allow juju_units\n"
    )
    _sudo("systemctl", "restart", "squid")

    for attempt in Retrying(
        reraise=True, stop=stop_after_delay(2 * MINUTE_SECS), wait=wait_fixed(2)
    ):
        with attempt, socket.create_connection(("127.0.0.1", PROXY_PORT), timeout=5):
            logging.info("Squid is listening on port %d", PROXY_PORT)


def remove_squid() -> None:
    """Stop Squid and drop the test configuration."""
    _sudo("rm", "--force", str(SQUID_CONFIG_PATH), check=False)
    _sudo("systemctl", "stop", "squid", check=False)


def get_squid_access_log() -> str:
    """Return the contents of the Squid access log, which is only readable by root."""
    return _sudo("cat", str(SQUID_ACCESS_LOG_PATH), check=False)


def check_proxy_relayed_traffic_to(*hosts: str) -> bool:
    """Whether Squid relayed traffic to any of the given hosts."""
    access_log = get_squid_access_log()

    return any(host in access_log for host in hosts)


def block_direct_egress(bridge: str, exempt_sources: list[str]) -> None:
    """Drop traffic leaving the LXD bridge, so the proxy is the only route out.

    Traffic inside the bridge (unit to unit, unit to controller) is kept, and so is
    traffic from the exempt sources: the controller fetches charms from Charmhub itself,
    outside of the model proxy configuration. Traffic to the host, which includes the
    proxy and the bridge resolver, is not forwarded and therefore unaffected.
    """
    unblock_direct_egress(bridge)

    _sudo("iptables", "--new-chain", EGRESS_CHAIN)
    _sudo("iptables", "--append", EGRESS_CHAIN, "--out-interface", bridge, "--jump", "RETURN")
    for source in exempt_sources:
        _sudo("iptables", "--append", EGRESS_CHAIN, "--source", source, "--jump", "RETURN")
    _sudo("iptables", "--append", EGRESS_CHAIN, "--jump", "DROP")

    logging.info("Dropping direct egress from bridge %s", bridge)
    _sudo("iptables", "--insert", "FORWARD", "1", "--in-interface", bridge, "--jump", EGRESS_CHAIN)


def unblock_direct_egress(bridge: str) -> None:
    """Remove the rules installed by :func:`block_direct_egress`."""
    delete_jump = [
        "sudo",
        "--non-interactive",
        "iptables",
        "--delete",
        "FORWARD",
        "--in-interface",
        bridge,
        "--jump",
        EGRESS_CHAIN,
    ]
    while subprocess.run(delete_jump, capture_output=True).returncode == 0:
        logging.info("Removed a %s jump from the FORWARD chain", EGRESS_CHAIN)

    _sudo("iptables", "--flush", EGRESS_CHAIN, check=False)
    _sudo("iptables", "--delete-chain", EGRESS_CHAIN, check=False)


def set_model_proxy(juju: Juju, proxy_url: str, no_proxy: list[str]) -> None:
    """Configure the model so that units reach the internet through the proxy."""
    no_proxy_value = ",".join(no_proxy)
    logging.info("Setting the model proxy to %s (no proxy: %s)", proxy_url, no_proxy_value)
    juju.cli(
        "model-config",
        f"juju-http-proxy={proxy_url}",
        f"juju-https-proxy={proxy_url}",
        f"juju-no-proxy={no_proxy_value}",
        f"snap-http-proxy={proxy_url}",
        f"snap-https-proxy={proxy_url}",
        f"apt-http-proxy={proxy_url}",
        f"apt-https-proxy={proxy_url}",
    )


def unset_model_proxy(juju: Juju) -> None:
    """Reset the model proxy configuration."""
    juju.cli("model-config", f"--reset={','.join(PROXY_CONFIG_KEYS)}")
