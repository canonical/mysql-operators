# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import re

from pydantic.fields import Field
from pydantic.functional_validators import field_validator
from pydantic.main import BaseModel

from ..core.literals import RefreshPause
from ..managers.managers.config import MIN_CONNS, AuditPolicy, AuditStrategy, Profile


class CharmConfig(BaseModel):
    """Clas to encapsulate the charm configuration."""

    cluster_name: str | None = Field(default=None)
    cluster_set_name: str | None = Field(default=None)
    max_connections: int | None = Field(default=None)
    profile: Profile
    profile_limit_memory: int | None = Field(default=None)
    binlog_retention_days: int
    logs_retention_period: str | int
    logs_audit_policy: AuditPolicy
    plugin_audit_enabled: bool
    plugin_audit_strategy: AuditStrategy
    pause_after_unit_refresh: RefreshPause
    tls_client_private_key: str | None = Field(default=None)
    tls_peer_private_key: str | None = Field(default=None)

    @field_validator("cluster_name", "cluster_set_name")
    @classmethod
    def cluster_name_validator(cls, value: str) -> str | None:
        """Check cluster name.

        Limited to 63 character, must start with a letter and
        contain only alphanumeric characters, `-`, `_` or `.`
        """
        if len(value) > 63:
            raise ValueError("cluster / cluster-set name must be at most 63 chars long")
        if not value[0].isalpha():
            raise ValueError("cluster / cluster-set name must start with a letter")
        if not re.match(r"^[a-zA-Z0-9-_.]*$", value):
            raise ValueError("cluster / cluster-set name must contain only alphanumeric chars")

        return value

    @field_validator("max_connections")
    @classmethod
    def max_connections_validator(cls, value: int) -> int | None:
        """Check max connections."""
        if value < MIN_CONNS:
            raise ValueError(f"max-connections must be equal or greater than {MIN_CONNS}")

        return value

    @field_validator("profile_limit_memory")
    @classmethod
    def profile_limit_memory_validator(cls, value: int) -> int | None:
        """Check profile limit memory."""
        if value < 600:
            raise ValueError("profile-limit-memory must have at least 600 MBs")
        if value > 9999999:
            raise ValueError("profile-limit-memory must have at most 9999999 MBs")

        return value

    @field_validator("binlog_retention_days")
    @classmethod
    def binlog_retention_days_validator(cls, value: int) -> int:
        """Check binlog retention days."""
        if value < 1:
            raise ValueError("binlog-retention-days must be greater than 0")

        return value

    @field_validator("logs_retention_period")
    @classmethod
    def logs_retention_period_validator(cls, value: str | int) -> str | int:
        """Check logs retention period."""
        if isinstance(value, str) and value != "auto":
            raise ValueError("logs-retention-period must be integer greater than 0 or `auto`")
        if isinstance(value, int) and not (0 < value < 999):
            raise ValueError("logs-retention-period must be integer greater than 0 or `auto`")

        return value
