# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import pathlib
import platform

import yaml

logger = logging.getLogger(__name__)


def check_architecture():
    """Checks whether the charm was deployed on wrong architecture.

    If this app is being refreshed, rollback with instructions from Charmhub docs.
    If this app is being deployed for the first time, remove it and deploy it again
    using a compatible revision.
    """
    charm_path = os.environ.get("CHARM_DIR", "")
    manifest_path = pathlib.Path(charm_path, "manifest.yaml")

    if not manifest_path.exists():
        raise ValueError("Failed to check architecture: manifest.yaml not found")

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
        raise ValueError("Failed to check architecture: platform not supported")
