# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import enum


class ReplicationStatus(enum.StrEnum):
    """Status for a MySQL cluster replication."""

    # fmt: off
    FAILED = "failed"                # Cluster set is in a failed state
    INITIALIZING = "initializing"    # Cluster to be added
    RECOVERING = "recovery"          # Replica cluster is being recovered
    READY = "ready"                  # Cluster set is ready
    SYNCING = "syncing"              # Credentials are being synced
    UNINITIALIZED = "uninitialized"  # Relation is not initialized
