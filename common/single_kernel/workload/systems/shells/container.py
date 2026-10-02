# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from contextlib import contextmanager
from threading import Thread
from typing import IO, Iterator

from ops.model import Container
from ops.pebble import ExecError

from .base import BaseShell

Pipe = IO[str] | None

logger = logging.getLogger(__name__)


class ContainerShell(BaseShell):
    """Class to deal with a container shell."""

    def __init__(self, container: Container, user: str, group: str):
        """Initialize the class attributes."""
        self._container = container
        self._user = user
        self._group = group

    def _stream_logs(self, pipe: Pipe) -> None:
        """Stream the pipe logs."""
        if not pipe:
            return

        for line in pipe:
            logger.debug(line.strip())

    @contextmanager
    def execute_async(
        self,
        command: list[str],
        environ: dict[str, str] | None = None,
        stdin: Pipe = None,
    ) -> Iterator[Pipe]:
        """Executes the given command in an async manner.

        In case of failure, it must raise an exception that is common across systems.
        Given that K8s uses pebble and VM uses subprocess, RuntimeError has been chosen.
        """
        if not environ:
            environ = {}

        process = self._container.exec(
            command,
            user=self._user,
            group=self._group,
            environment=environ,
            stdin=stdin,
        )

        thread = Thread(target=self._stream_logs, args=[process.stderr], daemon=True)
        thread.start()

        try:
            yield process.stdout
        finally:
            try:
                process.wait()
            except ExecError as e:
                raise RuntimeError(f"Failed to execute command: {e.exit_code}")
            finally:
                thread.join()

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
        if not environ:
            environ = {}

        try:
            process = self._container.exec(
                command,
                user=self._user,
                group=self._group,
                environment=environ,
                stdin=stdin,
            )
            stdout, stderr = process.wait_output()
        except ExecError as exc:
            logger.error(f"Standard output: {exc.stdout}")
            logger.error(f"Standard error: {exc.stderr}")
            raise RuntimeError("Failed to execute command")

        if stderr:
            logger.debug(f"Execution succeeded with errors: {stderr}")

        return stdout.strip()
