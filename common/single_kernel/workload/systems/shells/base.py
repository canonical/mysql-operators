# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import IO

Pipe = IO[str] | None


class BaseShell(ABC):
    """Abstract class to deal with a shell."""

    @abstractmethod
    def execute_async(
        self,
        command: list[str],
        environ: dict[str, str] | None = None,
        stdin: Pipe = None,
    ) -> AbstractContextManager[Pipe]:
        """Executes the given command in an async manner.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses pebble and VM uses subprocess, RuntimeError has been chosen.
        """
        raise NotImplementedError()

    @abstractmethod
    def execute_sync(
        self,
        command: list[str],
        environ: dict[str, str] | None = None,
        stdin: str | None = None,
    ) -> str:
        """Executes the given command in a sync manner.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses pebble and VM uses subprocess, RuntimeError has been chosen.
        """
        raise NotImplementedError()
