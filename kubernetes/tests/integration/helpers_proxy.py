#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers to run the integration tests behind a Squid forward proxy.

Squid runs on the test runner host. While it is up, it is the only route to the internet
for the units under test: a NetworkPolicy scoped to the model namespace drops every other
egress, so a charm that ignores the Juju proxy configuration cannot reach anything. The
policy is namespace scoped on purpose, to leave the controller alone.

The Squid package is installed by the spread task, so that a local run against an already
prepared host does not have to install it again. The tests do not run as root, so every
step that touches the host (the Squid configuration, its log and the microk8s service
arguments) goes through passwordless sudo.
"""

import logging
import re
import socket
import subprocess
from pathlib import Path

from jubilant_backports import Juju
from lightkube.core.client import Client
from lightkube.core.exceptions import ApiError
from lightkube.models.meta_v1 import LabelSelector, ObjectMeta
from lightkube.models.networking_v1 import (
    IPBlock,
    NetworkPolicyEgressRule,
    NetworkPolicyPeer,
    NetworkPolicyPort,
    NetworkPolicySpec,
)
from lightkube.resources.core_v1 import Node
from lightkube.resources.networking_v1 import NetworkPolicy
from tenacity import Retrying, stop_after_delay, wait_fixed

MINUTE_SECS = 60

PROXY_PORT = 3128
SQUID_BINARY_PATH = Path("/usr/sbin/squid")
SQUID_CONFIG_PATH = Path("/etc/squid/conf.d/99-juju-integration-test.conf")
SQUID_ACCESS_LOG_PATH = Path("/var/log/squid/access.log")

EGRESS_POLICY_NAME = "proxy-egress-only"
FIELD_MANAGER = "mysql-integration-tests"

MICROK8S_ARGS_PATH = Path("/var/snap/microk8s/current/args")
DEFAULT_POD_CIDR = "10.1.0.0/16"
DEFAULT_SERVICE_CIDR = "10.152.183.0/24"

# Model config keys set to route the units through the proxy (reset on teardown)
PROXY_CONFIG_KEYS = (
    "juju-http-proxy",
    "juju-https-proxy",
    "juju-no-proxy",
)


def _sudo(*command: str, check: bool = True) -> str:
    """Run a command on the test runner host as root, without a password prompt."""
    result = subprocess.run(
        ["sudo", "--non-interactive", *command], capture_output=True, check=check, text=True
    )

    return result.stdout.strip()


def _sudo_write(path: Path, content: str) -> None:
    """Write a file on the test runner host as root."""
    subprocess.run(
        ["sudo", "--non-interactive", "tee", str(path)],
        capture_output=True,
        check=True,
        input=content,
        text=True,
    )


def _get_microk8s_arg(service: str, argument: str, default: str) -> str:
    """Read a command line argument of a microk8s service, falling back to a default."""
    arguments = _sudo("cat", str(MICROK8S_ARGS_PATH / service), check=False)
    if match := re.search(rf"--{argument}=(\S+)", arguments):
        return match.group(1)

    logging.warning(f"No {argument} found for {service}, assuming {default}")
    return default


def _egress_policy(
    namespace: str, node_address: str, pod_cidr: str, service_cidr: str
) -> NetworkPolicy:
    """Build the policy that leaves the proxy as the only route out of the namespace."""
    return NetworkPolicy(
        metadata=ObjectMeta(name=EGRESS_POLICY_NAME, namespace=namespace),
        spec=NetworkPolicySpec(
            # Every pod of the model, including the ones added by a later scale up
            podSelector=LabelSelector(),
            policyTypes=["Egress"],
            egress=[
                # The squid proxy and the Kubernetes API both live on the node
                NetworkPolicyEgressRule(
                    to=[NetworkPolicyPeer(ipBlock=IPBlock(cidr=f"{node_address}/32"))]
                ),
                # Other pods (the units and the Juju controller) and the cluster services
                NetworkPolicyEgressRule(
                    to=[
                        NetworkPolicyPeer(ipBlock=IPBlock(cidr=pod_cidr)),
                        NetworkPolicyPeer(ipBlock=IPBlock(cidr=service_cidr)),
                    ]
                ),
                # The cluster DNS
                NetworkPolicyEgressRule(
                    ports=[
                        NetworkPolicyPort(port=53, protocol="UDP"),
                        NetworkPolicyPort(port=53, protocol="TCP"),
                    ]
                ),
            ],
        ),
    )


def check_passwordless_sudo() -> bool:
    """Whether the tests can raise privileges without a password prompt."""
    return (
        subprocess.run(["sudo", "--non-interactive", "true"], capture_output=True).returncode == 0
    )


def get_node_address() -> str:
    """Return the internal address of the Kubernetes node, i.e. the test runner host."""
    client = Client()
    for node in client.list(res=Node):
        for address in (node.status and node.status.addresses) or []:
            if address.type == "InternalIP":
                logging.info(f"Kubernetes node address is {address.address}")

                return address.address

    raise Exception("No Kubernetes node with an internal address found")


def get_cluster_cidrs() -> tuple[str, str]:
    """Return the pod network CIDR and the service network CIDR of the cluster."""
    pod_cidr = _get_microk8s_arg("kube-proxy", "cluster-cidr", DEFAULT_POD_CIDR)
    service_cidr = _get_microk8s_arg(
        "kube-apiserver", "service-cluster-ip-range", DEFAULT_SERVICE_CIDR
    )
    logging.info(f"Cluster pod CIDR is {pod_cidr}, service CIDR is {service_cidr}")

    return pod_cidr, service_cidr


def install_squid(allowed_sources: list[str]) -> None:
    """Set up Squid on the test runner host and allow the given sources through it.

    The package is expected to come from the spread task, and is only installed here as a
    fallback for a run on a host that the task did not prepare.
    """
    if SQUID_BINARY_PATH.exists():
        logging.info("Squid is already installed on the test runner")
    else:
        logging.info("Installing squid on the test runner")
        _sudo("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "update", check=False)
        _sudo("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "--yes", "squid")

    logging.info(f"Allowing {allowed_sources} through squid")
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


def block_direct_egress(
    namespace: str, node_address: str, pod_cidr: str, service_cidr: str
) -> None:
    """Drop pod egress in the model namespace, so the proxy is the only route out.

    Traffic to the node keeps the proxy and the Kubernetes API reachable, and traffic
    inside the cluster keeps the units, the controller and the cluster DNS reachable.
    """
    logging.info(f"Dropping direct egress from namespace {namespace}")
    client = Client()
    client.apply(
        _egress_policy(namespace, node_address, pod_cidr, service_cidr),
        field_manager=FIELD_MANAGER,
    )


def unblock_direct_egress(namespace: str) -> None:
    """Remove the policy installed by :func:`block_direct_egress`."""
    client = Client()
    try:
        client.delete(res=NetworkPolicy, name=EGRESS_POLICY_NAME, namespace=namespace)
    except ApiError as error:
        if error.status.code != 404:
            raise

        logging.info(f"No {EGRESS_POLICY_NAME} policy to remove in namespace {namespace}")


def set_model_proxy(juju: Juju, proxy_url: str, no_proxy: list[str]) -> None:
    """Configure the model so that units reach the internet through the proxy."""
    no_proxy_value = ",".join(no_proxy)
    logging.info(f"Setting the model proxy to {proxy_url} (no proxy: {no_proxy_value})")
    juju.model_config({
        "juju-http-proxy": proxy_url,
        "juju-https-proxy": proxy_url,
        "juju-no-proxy": no_proxy_value,
    })


def unset_model_proxy(juju: Juju) -> None:
    """Reset the model proxy configuration."""
    juju.model_config(reset=PROXY_CONFIG_KEYS)
