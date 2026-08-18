# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Relation, Unit

from .secrets import BaseSecretStore


class ReplicationState:
    """Class to deal with the async replication state."""

    # NOTE:
    # Coming up with the consolidated list of state key was hard.
    # Keep this note until the final code cut-over is performed:
    #
    # - `async-ready`:
    #   Moved into the replication databag, given that it is
    #   only used within async-replication functionality.
    # - `cluster-name`:
    #   Duplicated with the Operator state on purpose,
    #   given that the consumer does not have access to
    #   the remote peer data-bag.
    # - `is-replica`:
    #   Removed, given that it is only used in the offering side,
    #   and no action is taken with it (other than logging).
    # - `switchover`:
    #   Removed, given that is never read, only written.
    # - `user-data-found`:
    #   Removed, given that it is only used in the consumer side,
    #   and no action is taken with it (other than logging).

    cluster_key = "cluster-name"
    endpoint_key = "endpoint"
    name_key = "replication-name"
    label_key = "node-label"
    ready_key = "async-ready"
    replica_key = "replica-state"
    secret_key = "secret-id"
    version_key = "mysql-version"

    def __init__(self, store: BaseSecretStore, relation: Relation, component: Unit | Application):
        """Initialize the class attributes."""
        self._store = store
        self._relation = relation
        self._relation_data = self._relation.data[component] if self._relation else {}

    @property
    def store(self) -> BaseSecretStore:
        """Return the secrets store."""
        return self._store

    def get_cluster_name(self) -> str | None:
        """Return the offering / consuming cluster name."""
        name = self._relation_data.get(self.cluster_key)
        if not name:
            return None

        return name

    def get_endpoint(self) -> str | None:
        """Return the offering cluster endpoint address."""
        endpoint = self._relation_data.get(self.endpoint_key)
        if not endpoint:
            return None

        return endpoint

    def get_instance_label(self) -> str | None:
        """Return the consuming cluster primary node label."""
        label = self._relation_data.get(self.label_key)
        if not label:
            return None

        return label

    def get_ready_flag(self) -> bool | None:
        """Return the offering cluster ready flag."""
        flag = self._relation_data.get(self.ready_key)
        if not flag:
            return None

        return flag == "true"

    def get_replica_flag(self) -> bool | None:
        """Return the consuming cluster replica initialized flag."""
        flag = self._relation_data.get(self.replica_key)
        if not flag:
            return None

        return flag == "true"

    def get_secret_id(self) -> str | None:
        """Return the offering cluster secret ID holding the connection data."""
        secret_id = self._relation_data.get(self.secret_key)
        if not secret_id:
            return None

        return secret_id

    def get_version(self) -> str | None:
        """Return the offering cluster MySQL version."""
        version = self._relation_data.get(self.version_key)
        if not version:
            return None

        return version

    def set_cluster_name(self, name: str) -> None:
        """Set the offering / consuming cluster name."""
        self._relation_data.update({self.cluster_key: str(name)})

    def set_endpoint(self, endpoint: str) -> None:
        """Set the offering cluster endpoint address."""
        self._relation_data.update({self.endpoint_key: str(endpoint)})

    def set_instance_label(self, label: str) -> None:
        """Set the consuming cluster primary instance label."""
        self._relation_data.update({self.label_key: str(label)})

    def set_replication_name(self, label: str) -> None:
        """Set the offering replication name."""
        self._relation_data.update({self.name_key: str(label)})

    def set_ready_flag(self, flag: bool) -> None:
        """Set the offering cluster ready flag."""
        self._relation_data.update({self.ready_key: str(flag).lower()})

    def set_replica_flag(self, flag: bool) -> None:
        """Set the consuming cluster replica initialized flag."""
        self._relation_data.update({self.replica_key: str(flag).lower()})

    def set_secret_id(self, secret_id: str) -> None:
        """Set the offering cluster secret ID."""
        self._relation_data.update({self.secret_key: str(secret_id)})

    def set_version(self, version: str) -> None:
        """Set the offering cluster endpoint address."""
        self._relation_data.update({self.version_key: str(version)})

    def delete_ready_flag(self) -> None:
        """Delete the offering cluster ready flag."""
        self._relation_data.update({self.ready_key: ""})
