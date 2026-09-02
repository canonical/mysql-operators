# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import enum

from ...workload.systems.paths import BasePaths

BYTES_1MiB = 1048576
BYTES_1GiB = 1073741824

MIN_CONNS = 10
MIN_MEMORY = 200 * BYTES_1MiB


class MemoryProfile(enum.StrEnum):
    """Cluster memory profile."""

    PROD = "production"
    TEST = "testing"


class ClusterConfigHelper:
    """Class to deal with the MySQL server cluster config."""

    static_keys = {
        "innodb_buffer_pool_size",
        "innodb_buffer_pool_chunk_size",
        "loose-group_replication_message_cache_size",
    }

    def __init__(self, paths: BasePaths):
        """Initialize the class attributes."""
        self._paths = paths

    def _calculate_buffer_pool(self, memory: int) -> tuple[int, int | None, int | None]:
        """Calculate the buffer pool options.

        Based on https://github.com/percona/percona-xtradb-cluster-operator/blob/main/pkg/pxc/app/config/autotune.go#L31-L54
        """
        chunk_size_minimum = BYTES_1MiB
        chunk_size_default = BYTES_1MiB * 128
        message_cache_default = BYTES_1GiB

        pool_size = int(memory * 0.75) - message_cache_default
        pool_chunk_size = None
        message_cache_size = None

        if pool_size < 0 or memory - pool_size < BYTES_1GiB:
            message_cache_size = BYTES_1MiB * 128
            pool_size = int(memory * 0.5)

        # Round pool_size to be a multiple of chunk_size_default
        if pool_size % chunk_size_default != 0:
            pool_size += chunk_size_default - (pool_size % chunk_size_default)

        if pool_size > BYTES_1GiB:
            chunk_size = int(pool_size / 8)

            # Round chunk_size to a multiple of chunk_size_min
            if chunk_size % chunk_size_minimum != 0:
                chunk_size += chunk_size_minimum - (chunk_size % chunk_size_minimum)

            pool_size = chunk_size * 8
            pool_chunk_size = chunk_size

        return pool_size, pool_chunk_size, message_cache_size

    def _calculate_max_connections(self, memory: int) -> int:
        """Calculate the maximum number of connections given the available memory.

        Based on https://github.com/percona/percona-xtradb-cluster-operator/blob/main/pkg/pxc/app/config/autotune.go#L61-L70
        """
        return memory // (12 * BYTES_1MiB)

    def _get_production_config(self, memory: int, max_connections: int | None) -> dict:
        """Return the cluster configuration for the production profile."""
        if max_connections:
            memory = max(memory - (max_connections * 12 * BYTES_1MiB), MIN_MEMORY)

        (
            pool_size,
            pool_chunk_size,
            message_cache_size,
        ) = self._calculate_buffer_pool(memory)

        memory -= pool_size + (message_cache_size or 0)

        if not pool_chunk_size:
            pool_chunk_size = 128 * BYTES_1MiB
        if not message_cache_size:
            message_cache_size = 1 * BYTES_1GiB
        if not max_connections:
            max_connections = max(self._calculate_max_connections(memory), MIN_CONNS)

        if memory < 2 * BYTES_1GiB:
            performance_schema_instrument = "'memory/%=OFF'"
        else:
            performance_schema_instrument = "'memory/%=ON'"

        return {
            "innodb_buffer_pool_size": pool_size,
            "innodb_buffer_pool_chunk_size": pool_chunk_size,
            "innodb_log_group_home_dir": self._paths.mysql_logs,
            "innodb_temp_tablespaces_dir": self._paths.mysql_temp,
            "innodb_undo_directory": self._paths.mysql_logs,
            "loose-group_replication_message_cache_size": message_cache_size,
            "loose-group_replication_paxos_single_leader": "ON",
            "max_connections": max_connections,
            "performance-schema-instrument": performance_schema_instrument,
        }

    def _get_testing_config(self) -> dict:
        """Return the cluster configuration for the testing profile."""
        return {
            "innodb_buffer_pool_size": 20 * BYTES_1MiB,
            "innodb_buffer_pool_chunk_size": 1 * BYTES_1MiB,
            "innodb_log_group_home_dir": self._paths.mysql_logs,
            "innodb_temp_tablespaces_dir": self._paths.mysql_temp,
            "innodb_undo_directory": self._paths.mysql_logs,
            "loose-group_replication_message_cache_size": 128 * BYTES_1MiB,
            "loose-group_replication_paxos_single_leader": "ON",
            "max_connections": 100,
            "performance-schema-instrument": "'memory/%=OFF'",
        }

    def get_config(self, profile: MemoryProfile, memory: int, max_connections: int | None) -> dict:
        """Return the InnoDB cluster config."""
        match profile:
            case MemoryProfile.PROD:
                return self._get_production_config(memory, max_connections)
            case MemoryProfile.TEST:
                return self._get_testing_config()
            case _:
                raise ValueError(f"Unknown config profile: {profile}")
