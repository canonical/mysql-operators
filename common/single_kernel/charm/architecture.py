# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import pathlib
import platform

import yaml

logger = logging.getLogger(__name__)


def check_architecture() -> bool:
    """Checks whether the charm was deployed on the right architecture."""
    charm_path = os.environ.get("CHARM_DIR", "")
    manifest_path = pathlib.Path(charm_path, "manifest.yaml")

    if not manifest_path.exists():
        logger.error("Failed to check architecture: manifest.yaml not found")
        return False

    manifest = yaml.safe_load(manifest_path.read_text())

    manifest_architectures = []
    hardware_architecture = platform.machine()

    for base in manifest["bases"]:
        base_architecture = base.get("architectures", [])
        manifest_architectures.extend(base_architecture)

    if not any((
        "amd64" in manifest_architectures and hardware_architecture == "x86_64",
        "arm64" in manifest_architectures and hardware_architecture == "aarch64",
        "s390x" in manifest_architectures and hardware_architecture == "s390x",
    )):
        logger.debug("Failed to check architecture: platform not supported")
        return False

    return True
