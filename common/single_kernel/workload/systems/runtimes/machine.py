# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import socket
from typing import Sequence

from python_hosts.exception import UnableToWriteHosts
from python_hosts.hosts import Hosts, HostsEntry

from .base import BaseRuntime

logger = logging.getLogger(__name__)


class MachineRuntime(BaseRuntime):
    """Class to deal with a machine runtime."""

    host_comment = "Managed by Charmed MySQL"
    host_type = "ipv4"

    def get_cores(self) -> int:
        """Return the runtime core count.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses OS, RuntimeError has been chosen.
        """
        logger.debug("Calculating runtime cores")

        num_cores = 0
        with open("/proc/cpuinfo") as cpu_info:
            for line in cpu_info:
                if line.startswith("processor"):
                    num_cores += 1

        return num_cores

    def get_memory(self) -> int:
        """Return the runtime memory bytes.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses OS, RuntimeError has been chosen.
        """
        logger.debug("Calculating runtime memory")

        with open("/proc/meminfo") as memory_info:
            for line in memory_info:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) * 1024

        raise RuntimeError("Failed to calculate runtime memory")

    def get_hostname(self, address: str) -> str:
        """Return the FQDN of the provided address."""
        logger.debug(f"Resolving FQDN for {address}")

        return socket.getfqdn()

    def update_hosts(self, addresses: Sequence[str], names: Sequence[str]) -> None:
        """Update the runtime hosts.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        logger.debug("Updating hostnames in /etc/hosts")

        # Remove MAAS injected entry
        hosts = Hosts()
        hosts.remove_all_matching(address="127.0.1.1", name=socket.getfqdn())
        hosts.remove_all_matching(comment=self.host_comment)

        entries = []
        for address, name in zip(addresses, names):
            entries.append(
                HostsEntry(
                    address=address,
                    names=[name],
                    comment=self.host_comment,
                    entry_type=self.host_type,
                )
            )

        try:
            hosts.add(entries)
            hosts.write()
        except UnableToWriteHosts as e:
            raise RuntimeError(f"Failed to update hostnames: {e}")

    def update_labels(self, labels: Sequence[dict], names: Sequence[str]) -> None:
        """Update the runtime labels.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        pass
