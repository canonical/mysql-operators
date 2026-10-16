# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import enum


class ReplicationStatus(enum.StrEnum):
    """Status for a MySQL cluster replication."""

    # fmt: off
    INITIALIZING  = "initializing"   # Replica cluster is being added to the cluster-set
    RECOVERING    = "recovery"       # Replica cluster is recovering (data copy / units joining)
    READY         = "ready"          # Cluster-set is fully operational
    SYNCING       = "syncing"        # Credentials are being synced to the replica cluster
    UNINITIALIZED = "uninitialized"  # Relation not yet set up
