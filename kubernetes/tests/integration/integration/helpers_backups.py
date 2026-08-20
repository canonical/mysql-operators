# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path

from jubilant import Juju, TaskError

logger = logging.getLogger(__name__)


@contextmanager
def local_tmp_folder(name: str = "tmp"):
    """Return a temporary folder path and clean it up after use."""
    if (tmp_folder := Path.cwd() / name).exists():
        shutil.rmtree(tmp_folder)
    tmp_folder.mkdir()
    yield tmp_folder
    shutil.rmtree(tmp_folder)


def list_backups(juju: Juju, unit_name: str) -> list[str]:
    """Lists backups in a safe manner (avoid raising if the action fails)."""
    try:
        logger.info("Listing existing backup ids")
        task = juju.run(unit_name, "list-backups")
    except TaskError:
        return []

    backups = task.results["backups"]
    backups = [line.split("|")[0].strip() for line in backups.split("\n")[2:]]
    return backups
