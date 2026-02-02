# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from jubilant_backports import Juju

from .helpers_backups import build_and_deploy_operations, pitr_operations


def test_build_and_deploy_aws(
    juju: Juju, cloud_configs_aws: tuple[dict[str, str], dict[str, str]], charm
) -> None:
    """Build and deploy for AWS."""
    build_and_deploy_operations(
        juju,
        charm,
        cloud_configs_aws[0],
        cloud_configs_aws[1],
    )


def test_pitr_aws(juju: Juju, cloud_configs_aws: tuple[dict[str, str], dict[str, str]]) -> None:
    """Pitr tests."""
    pitr_operations(juju, cloud_configs_aws[0], cloud_configs_aws[1])
