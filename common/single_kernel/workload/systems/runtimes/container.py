# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import re
import socket
from functools import cached_property
from typing import Sequence

from lightkube.core.client import Client
from lightkube.core.exceptions import ApiError
from lightkube.resources.core_v1 import Node, Pod

from .base import BaseRuntime

logger = logging.getLogger(__name__)


class ContainerRuntime(BaseRuntime):
    """Class to deal with a container runtime."""

    memory_pattern = r"^(\d+)(\w+)$"
    memory_bytes = {
        "KI": 1024,
        "K": 10**3,
        "MI": 1048576,
        "M": 10**6,
        "GI": 1073741824,
        "G": 10**9,
        "TI": 1099511627776,
        "T": 10**12,
    }

    def __init__(self, namespace: str, pod_name: str, container_name: str):
        """Initialize the class attributes."""
        self._pod_name = pod_name
        self._container_name = container_name
        self._client = Client(namespace=namespace)

    @cached_property
    def _node_name(self) -> str:
        """Return the node name."""
        pod = self._client.get(Pod, name=self._pod_name)
        if pod.spec and pod.spec.nodeName:
            return pod.spec.nodeName

        raise RuntimeError(f"Failed to get node name for pod {self._pod_name}")

    def _parse_procs(self, procs: str) -> int:
        """Parses the reported CPUs value to units (i.e. 1000m)."""
        proc_parts = procs.split("m")
        proc_units = int(proc_parts[0])
        return proc_units // 1000

    def _parse_memory(self, memory: str) -> int:
        """Parses the reported memory value to bytes (i.e. 1Gi)."""
        parts = re.match(self.memory_pattern, memory)
        if not parts:
            raise RuntimeError(f"Failed to parse memory '{memory}'")

        memory_units = parts.groups()[1].upper()
        memory_bytes = self.memory_bytes[memory_units]
        return int(memory) * memory_bytes

    def _get_container_limits(self) -> dict:
        """Return the container limits."""
        pod = self._client.get(Pod, name=self._pod_name)
        if not pod.spec:
            return {}

        for container in pod.spec.containers:
            if container.name == self._container_name and container.resources:
                return container.resources.limits or {}

        return {}

    def _get_container_cores(self) -> int | None:
        """Return the container core count."""
        limits = self._get_container_limits()

        procs = limits.get("cpu")
        if not procs:
            return None

        try:
            return int(procs)
        except ValueError:
            return int(self._parse_procs(procs))

    def _get_container_memory(self) -> int | None:
        """Return the container memory."""
        limits = self._get_container_limits()

        memory = limits.get("memory")
        if not memory:
            return None

        try:
            return int(memory)
        except ValueError:
            return int(self._parse_memory(memory))

    def _get_node_cores(self) -> int | None:
        """Return the container node available CPU cores."""
        node = self._client.get(Node, name=self._node_name)
        if not node.status:
            return None

        status = node.status.allocatable or {}
        procs = status.get("cpu")
        if not procs:
            return None

        try:
            return int(procs)
        except ValueError:
            return int(self._parse_procs(procs))

    def _get_node_memory(self) -> int | None:
        """Return the container node available memory bytes."""
        node = self._client.get(Node, name=self._node_name)
        if not node.status:
            return None

        status = node.status.allocatable or {}
        memory = status.get("memory")
        if not memory:
            return None

        try:
            return int(memory)
        except ValueError:
            return int(self._parse_memory(memory))

    def get_cores(self) -> int:
        """Return the runtime core count.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses OS, RuntimeError has been chosen.
        """
        logger.debug("Calculating runtime cores")

        try:
            container_cores = self._get_container_cores()
            allocable_cores = self._get_node_cores()
        except ApiError as e:
            raise RuntimeError(f"Failed to fetch core information: {e}")

        return min(count for count in (container_cores, allocable_cores) if count)

    def get_memory(self) -> int:
        """Return the runtime memory bytes.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses OS, RuntimeError has been chosen.
        """
        logger.debug("Calculating runtime memory")

        try:
            container_memory = self._get_container_memory()
            allocable_memory = self._get_node_memory()
        except ApiError as e:
            raise RuntimeError(f"Failed to fetch memory information: {e}")

        return min(mem for mem in (container_memory, allocable_memory) if mem)

    def get_hostname(self, address: str) -> str:
        """Return the FQDN of the provided address."""
        logger.debug(f"Resolving FQDN for {address}")

        try:
            info = socket.getaddrinfo(
                host=address,
                port=None,
                family=socket.AF_UNSPEC,
                flags=socket.AI_CANONNAME,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as e:
            raise RuntimeError(f"Failed to resolve FQDN for {address}: {e}")

        for entry in info:
            hostname = entry[3]
            if hostname and hostname.endswith("."):
                return f"{hostname}"
            if hostname and not hostname.endswith("."):
                return f"{hostname}."

        raise RuntimeError(f"Failed to determine FQDN for {address}")

    def update_hosts(self, addresses: Sequence[str], names: Sequence[str]) -> None:
        """Update the runtime hosts.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        pass

    def update_labels(self, labels: Sequence[dict], names: Sequence[str]) -> None:
        """Update the runtime labels.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        logger.debug("Updating pod labels")

        for label, name in zip(labels, names):
            if not name:
                name = self._pod_name

            try:
                pod = self._client.get(Pod, name=name)
                if pod.metadata and pod.metadata.labels:
                    pod.metadata.labels.update(label)

                self._client.patch(Pod, name=name, obj=pod)
            except ApiError as e:
                message = str(e)
                if e.status.code == 403:
                    message = f"`juju trust` needed"
                if e.status.code == 404:
                    message = f"pod {name} not found"
                if e.status.code == 409:
                    message = f"pod {name} changed"
                raise RuntimeError(f"Failed to update pod labels: {message}")
