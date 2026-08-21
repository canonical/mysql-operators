# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod
from typing import Mapping, Sequence


class BaseRuntime(ABC):
    """Abstract class to deal with a runtime."""

    @abstractmethod
    def get_cores(self) -> int:
        """Return the runtime core count.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses OS, RuntimeError has been chosen.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_memory(self) -> int:
        """Return the runtime memory bytes.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses OS, RuntimeError has been chosen.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_hostname(self, address: str) -> str:
        """Return the FQDN of the provided address."""
        raise NotImplementedError()

    @abstractmethod
    def create_service(self, name: str, labels: Mapping[str, str]) -> None:
        """Creates a network service.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        raise NotImplementedError()

    @abstractmethod
    def remove_hosts(self) -> None:
        """Remove all runtime hosts.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        raise NotImplementedError()

    @abstractmethod
    def update_hosts(self, address: str, names: Sequence[str]) -> None:
        """Update the runtime hosts.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        raise NotImplementedError()

    @abstractmethod
    def update_labels(self, address: str, labels: Mapping[str, str]) -> None:
        """Update the runtime labels.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses lightkube and VM uses Hosts, RuntimeError has been chosen.
        """
        raise NotImplementedError()
