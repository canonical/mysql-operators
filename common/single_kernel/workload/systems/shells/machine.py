# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import subprocess
from contextlib import contextmanager
from threading import Thread
from typing import IO, Iterator

from .base import BaseShell

Pipe = IO[str] | None

logger = logging.getLogger(__name__)


class MachineShell(BaseShell):
    """Class to deal with a machine shell."""

    def __init__(self, user: str, group: str):
        """Initialize the class attributes."""
        self._user = user
        self._group = group

    def _resolve_user(self, command: list[str]) -> str:
        """Resolve the user given a command.

        Xtrabackup commands must be run as root because they use setpriv to drop privileges.
        See https://snapcraft.io/docs/explanation/snap-development/system-usernames/#dropping-privileges
        """
        if any((
            command[0].endswith("charmed-mysql.xbcloud"),
            command[0].endswith("charmed-mysql.xbstream"),
            command[0].endswith("charmed-mysql.xtrabackup"),
        )):
            return "root"
        else:
            return self._user

    def _resolve_group(self, command: list[str]) -> str:
        """Resolve the group given a command.

        Xtrabackup commands must be run as root because they use setpriv to drop privileges.
        See https://snapcraft.io/docs/explanation/snap-development/system-usernames/#dropping-privileges
        """
        if any((
            command[0].endswith("charmed-mysql.xbcloud"),
            command[0].endswith("charmed-mysql.xbstream"),
            command[0].endswith("charmed-mysql.xtrabackup"),
        )):
            return "root"
        else:
            return self._group

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

        user = self._resolve_user(command)
        group = self._resolve_group(command)

        process = subprocess.Popen(
            command,
            user=user,
            group=group,
            env={**os.environ, **environ},
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        thread = Thread(target=self._stream_logs, args=[process.stderr], daemon=True)
        thread.start()

        try:
            yield process.stdout
        finally:
            code = process.wait()
            thread.join()

        if code != 0:
            raise RuntimeError(f"Failed to execute command: {code}")

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

        user = self._resolve_user(command)
        group = self._resolve_group(command)

        try:
            process = subprocess.run(
                command,
                user=user,
                group=group,
                env={**os.environ, **environ},
                input=stdin,
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(f"Standard output: {exc.stdout}")
            logger.error(f"Standard error: {exc.stderr}")
            raise RuntimeError("Failed to execute command")

        if process.stderr:
            logger.debug(f"Execution succeeded with errors: {process.stderr}")

        return process.stdout.strip()
