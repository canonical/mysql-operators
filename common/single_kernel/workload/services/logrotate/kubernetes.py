# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Sequence

import jinja2

from ...systems import K8sSystem
from .base import BaseLogrotateService

logger = logging.getLogger(__name__)


class K8sLogrotateService(BaseLogrotateService):
    """Class to deal with the logrotate service lifecycle."""

    def __init__(self, system: K8sSystem):
        """Initialize the class attributes."""
        self._system = system

    def install(self) -> None:
        """Install the service binaries."""
        pass

    def setup(self, retention_days: int, compress: bool, log_types: Sequence[str]) -> None:
        """Set up the service."""
        logger.debug("Creating the logrotate config file")

        # Logrotate is executed once per minute, so retention-days x hours x minutes
        # give us the number of log files to preserve
        retention_files = retention_days * 24 * 60

        with open("templates/logrotate.j2") as file:
            template = jinja2.Template(file.read())

        rendered = template.render(
            archive_dir=self._system.paths.mysql_archive,
            logs_dir=self._system.paths.mysql_logs,
            logs_retention_days=retention_days,
            logs_retention_files=retention_files,
            logs_compression_enabled=compress,
            log_types=log_types,
            system_user=self._system.user,
            system_group=self._system.group,
        )

        logger.debug("Writing the logrotate config file")
        self._system.paths.logrotate_config.write_text(
            data=rendered,
            mode=0o640,
            user=self._system.user,
            group=self._system.group,
        )

    def start(self) -> None:
        """Start the service."""
        pass

    def stop(self) -> None:
        """Stop the service."""
        pass
