#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers to run the integration tests behind a Squid forward proxy.

Squid is installed on the test runner host. While it is up, it is the only route to the
internet for the units under test: a NetworkPolicy scoped to the model namespace drops
every other egress, so a charm that ignores the Juju proxy configuration cannot reach
anything. The policy is namespace scoped on purpose, to leave the controller alone.

The tests do not run as root, so every step that touches the host (the package, the Squid
configuration, its log and the microk8s service arguments) goes through passwordless sudo.
"""

import logging
import os
import re
import socket
import subprocess
import tempfile
from pathlib import Path
from string import Template

from jubilant_backports import Juju
from tenacity import Retrying, stop_after_delay, wait_fixed

MINUTE_SECS = 60

PROXY_PORT = 3128
SQUID_CONFIG_PATH = Path("/etc/squid/conf.d/99-juju-integration-test.conf")
SQUID_ACCESS_LOG_PATH = Path("/var/log/squid/access.log")

EGRESS_POLICY_NAME = "proxy-egress-only"
EGRESS_POLICY_PATH = (
    "tests/integration/integration/high_availability/manifests/proxy_egress_only.yml"
)

MICROK8S_ARGS_PATH = Path("/var/snap/microk8s/current/args")
DEFAULT_POD_CIDR = "10.1.0.0/16"
DEFAULT_SERVICE_CIDR = "10.152.183.0/24"

# Model config keys set to route the units through the proxy (reset on teardown)
PROXY_CONFIG_KEYS = (
    "juju-http-proxy",
    "juju-https-proxy",
    "juju-no-proxy",
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


def _kubectl(*args: str) -> str:
    """Run a kubectl command against the microk8s cluster."""
    environment = {**os.environ, "KUBECONFIG": os.path.expanduser("~/.kube/config")}
    result = subprocess.run(
        ["microk8s.kubectl", *args], capture_output=True, check=False, env=environment, text=True
    )
    if result.returncode:
        logging.error("Command kubectl %s failed: %s", args, result.stderr)
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)

    return result.stdout.strip()


def _get_microk8s_arg(service: str, argument: str, default: str) -> str:
    """Read a command line argument of a microk8s service, falling back to a default."""
    arguments = _sudo("cat", str(MICROK8S_ARGS_PATH / service), check=False)
    if match := re.search(rf"--{argument}=(\S+)", arguments):
        return match.group(1)

    logging.warning("No --%s found for %s, assuming %s", argument, service, default)
    return default


def check_passwordless_sudo() -> bool:
    """Whether the tests can raise privileges without a password prompt."""
    return (
        subprocess.run(["sudo", "--non-interactive", "true"], capture_output=True).returncode == 0
    )


def get_node_address() -> str:
    """Return the internal address of the Kubernetes node, i.e. the test runner host."""
    output = _kubectl(
        "get",
        "nodes",
        "-o",
        'jsonpath={.items[0].status.addresses[?(@.type=="InternalIP")].address}',
    )
    address = output.split()[0]
    logging.info("Kubernetes node address is %s", address)

    return address


def get_cluster_cidrs() -> tuple[str, str]:
    """Return the pod network CIDR and the service network CIDR of the cluster."""
    pod_cidr = _get_microk8s_arg("kube-proxy", "cluster-cidr", DEFAULT_POD_CIDR)
    service_cidr = _get_microk8s_arg(
        "kube-apiserver", "service-cluster-ip-range", DEFAULT_SERVICE_CIDR
    )
    logging.info("Cluster pod CIDR is %s, service CIDR is %s", pod_cidr, service_cidr)

    return pod_cidr, service_cidr


def install_squid(allowed_sources: list[str]) -> None:
    """Install Squid on the test runner host and allow the given sources through it."""
    logging.info("Installing squid on the test runner")
    _sudo("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "update", check=False)
    _sudo("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "--yes", "squid")

    logging.info("Allowing %s through squid", allowed_sources)
    _sudo_write(
        SQUID_CONFIG_PATH,
        f"acl juju_units src {' '.join(allowed_sources)}\nhttp_access allow juju_units\n",
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


def block_direct_egress(namespace: str, node_address: str) -> None:
    """Drop pod egress in the model namespace, so the proxy is the only route out.

    Traffic to the node keeps the proxy and the Kubernetes API reachable, and traffic
    inside the cluster keeps the units, the controller and the cluster DNS reachable.
    """
    pod_cidr, service_cidr = get_cluster_cidrs()
    template = Template(Path(EGRESS_POLICY_PATH).read_text()).substitute(
        namespace=namespace,
        node_address=node_address,
        pod_cidr=pod_cidr,
        service_cidr=service_cidr,
    )

    logging.info("Dropping direct egress from namespace %s", namespace)
    with tempfile.NamedTemporaryFile(dir=Path.home(), suffix=".yml") as manifest:
        manifest.write(template.encode())
        manifest.flush()
        _kubectl("apply", "-f", manifest.name)


def unblock_direct_egress(namespace: str) -> None:
    """Remove the policy installed by :func:`block_direct_egress`."""
    _kubectl(
        "delete",
        "networkpolicy",
        EGRESS_POLICY_NAME,
        f"--namespace={namespace}",
        "--ignore-not-found",
    )


def set_model_proxy(juju: Juju, proxy_url: str, no_proxy: list[str]) -> None:
    """Configure the model so that units reach the internet through the proxy."""
    no_proxy_value = ",".join(no_proxy)
    logging.info("Setting the model proxy to %s (no proxy: %s)", proxy_url, no_proxy_value)
    juju.cli(
        "model-config",
        f"juju-http-proxy={proxy_url}",
        f"juju-https-proxy={proxy_url}",
        f"juju-no-proxy={no_proxy_value}",
    )


def unset_model_proxy(juju: Juju) -> None:
    """Reset the model proxy configuration."""
    juju.cli("model-config", f"--reset={','.join(PROXY_CONFIG_KEYS)}")
