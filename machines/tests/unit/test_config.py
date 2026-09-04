#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import pytest
import yaml
from charms.mysql.v0.mysql import MAX_CONNECTIONS_FLOOR
from ops.testing import Harness

from charm import MySQLOperatorCharm
from config import MySQLConfig
from constants import PEER

CONFIG = str(yaml.safe_load(Path("./config.yaml").read_text()))
ACTIONS = str(yaml.safe_load(Path("./actions.yaml").read_text()))
METADATA = str(yaml.safe_load(Path("./metadata.yaml").read_text()))

logger = logging.getLogger(__name__)


@pytest.fixture
def harness():
    harness = Harness(MySQLOperatorCharm, meta=METADATA, config=CONFIG, actions=ACTIONS)
    harness.add_relation(PEER, "mysql")
    harness.begin()
    return harness


def _check_valid_values(_harness, field: str, accepted_values: list, is_long_field=False) -> None:
    """Check the correctness of the passed values for a field."""
    for value in accepted_values:
        _harness.update_config({field: value})
        assert _harness.charm.config[field] == value if not is_long_field else int(value)


def _check_invalid_values(_harness, field: str, erroneous_values: list) -> None:
    """Check the incorrectness of the passed values for a field."""
    for value in erroneous_values:
        _harness.update_config({field: value})
        with pytest.raises(ValueError):
            _ = _harness.charm.config[field]


def test_profile_limit_values(harness) -> None:
    """Check that integer fields are parsed correctly."""
    erroneous_values = [599, 10**7, -354343]
    _check_invalid_values(harness, "profile-limit-memory", erroneous_values)

    valid_values = [600, 1000, 35000]
    _check_valid_values(harness, "profile-limit-memory", valid_values)


def test_profile_values(harness) -> None:
    """Test profile values."""
    erroneous_values = ["prod", "Test", "foo", "bar"]
    _check_invalid_values(harness, "profile", erroneous_values)

    accepted_values = ["production", "testing"]
    _check_valid_values(harness, "profile", accepted_values)


def test_cluster_name_values(harness) -> None:
    """Test cluster name values."""
    erroneous_values = [64 * "a", "1-cluster", "cluster$"]
    _check_invalid_values(harness, "cluster-name", erroneous_values)

    accepted_values = ["c1", "cluster_name", "cluster.name", "Cluster-name", 63 * "c"]
    _check_valid_values(harness, "cluster-name", accepted_values)


# --- MySQLConfig (non-charm) tests ---


def test_keys_requires_restart():
    """Test keys_requires_restart returns True only for static config keys."""
    config = MySQLConfig()
    assert config.keys_requires_restart({"innodb_buffer_pool_size"}) is True
    assert config.keys_requires_restart({"innodb_buffer_pool_size", "max_connections"}) is True
    assert config.keys_requires_restart({"max_connections"}) is False
    assert config.keys_requires_restart(set()) is False


def test_filter_static_keys():
    """Test filter_static_keys removes static config keys."""
    config = MySQLConfig()
    keys = {"innodb_buffer_pool_size", "max_connections", "log_error"}
    assert config.filter_static_keys(keys) == {"max_connections"}
    assert config.filter_static_keys(set()) == set()


def test_get_custom_config():
    """Test get_custom_config parses a mysqld config section."""
    content = "[mysqld]\nmax_connections=100\ninnodb_buffer_pool_size=1G\n"
    result = MySQLConfig.get_custom_config(content)
    assert result == {"max_connections": "100", "innodb_buffer_pool_size": "1G"}


# --- Remaining CharmConfig validators ---


def test_max_connections_values(harness) -> None:
    """Test max-connections validator."""
    _check_invalid_values(harness, "max-connections", [MAX_CONNECTIONS_FLOOR - 1, 0, -10])
    _check_valid_values(harness, "max-connections", [MAX_CONNECTIONS_FLOOR, 100, 1000])


def test_binlog_retention_days_values(harness) -> None:
    """Test binlog-retention-days validator."""
    _check_invalid_values(harness, "binlog-retention-days", [0, -1])
    _check_valid_values(harness, "binlog-retention-days", [1, 7, 30])


def test_plugin_audit_strategy_values(harness) -> None:
    """Test plugin-audit-strategy validator."""
    _check_invalid_values(harness, "plugin-audit-strategy", ["sync", "ASYNC", "fast"])
    _check_valid_values(harness, "plugin-audit-strategy", ["async", "semi-async"])


def test_logs_audit_policy_values(harness) -> None:
    """Test logs-audit-policy validator."""
    _check_invalid_values(harness, "logs-audit-policy", ["none", "errors", "ALL"])
    _check_valid_values(harness, "logs-audit-policy", ["all", "logins", "queries"])


def test_logs_retention_period_values(harness) -> None:
    """Test logs-retention-period validator."""
    _check_invalid_values(harness, "logs-retention-period", ["2", "1", "abc"])
    _check_valid_values(harness, "logs-retention-period", ["auto", "3", "30"])


def test_pause_after_unit_refresh_values(harness) -> None:
    """Test pause-after-unit-refresh validator."""
    _check_invalid_values(harness, "pause-after-unit-refresh", ["some", "ALL", "1"])
    _check_valid_values(harness, "pause-after-unit-refresh", ["all", "first", "none"])


def test_cluster_set_name_values(harness) -> None:
    """Test cluster-set-name validator (shares logic with cluster-name)."""
    _check_invalid_values(harness, "cluster-set-name", [64 * "b", "1set", "set#"])
    _check_valid_values(harness, "cluster-set-name", ["s1", "set_name", "set.name", 63 * "s"])
