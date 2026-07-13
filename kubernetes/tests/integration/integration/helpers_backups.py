# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import shutil
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def local_tmp_folder(name: str = "tmp"):
    """Return a temporary folder path and clean it up after use."""
    if (tmp_folder := Path.cwd() / name).exists():
        shutil.rmtree(tmp_folder)
    tmp_folder.mkdir()
    yield tmp_folder
    shutil.rmtree(tmp_folder)
