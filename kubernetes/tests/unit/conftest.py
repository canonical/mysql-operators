# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_refresh():
    """Fixture to shunt refresh logic and events."""
    refresh_mock = Mock()
    refresh_mock.in_progress = False
    refresh_mock.app_status_higher_priority = None
    refresh_mock.app_status_lower_priority.return_value = None
    refresh_mock.unit_status_higher_priority = None
    refresh_mock.unit_status_lower_priority.return_value = None
    refresh_mock.workload_allowed_to_start = True

    with (
        patch("charm_refresh.Kubernetes", Mock(return_value=refresh_mock)),
        patch("charm.KubernetesMySQLRefresh", Mock(return_value=None)),
    ):
        yield


@pytest.fixture
def with_juju_secrets(monkeypatch):
    monkeypatch.setattr("ops.JujuVersion.has_secrets", True)
