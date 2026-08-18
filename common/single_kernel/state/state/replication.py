# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Relation, Unit

from ..secrets import BaseSecretStore


class ReplicationState:
    """Class to deal with the async replication state."""

    # NOTE:
    # Coming up with the consolidated list of state key was hard.
    # Keep this note until the final code cut-over is performed:
    #
    # - `async-ready` (now called `replication-ready`):
    #   Moved into the replication databag, given that it is
    #   only used within async-replication functionality.
    # - `cluster-name`:
    #   Duplicated with the Operator state on purpose,
    #   given that the consumer does not have access to
    #   the remote peer data-bag.
    # - `is-replica`:
    #   Removed, given that it is only used in the offering side,
    #   and no action is taken with it (other than logging).
    # - `user-data-found`:
    #   Removed, given that it is only used in the consumer side,
    #   and no action is taken with it (other than logging).

    cluster_name_key = "cluster-name"
    cluster_version_key = "cluster-version"
    instance_address_key = "instance-address"
    instance_label_key = "instance-label"
    replication_name_key = "replication-name"
    replication_ready_key = "replication-ready"
    replica_key = "replica-state"
    secret_key = "secret-id"
    switchover_key = "switchover"

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
        name = self._relation_data.get(self.cluster_name_key)
        if not name:
            return None

        return name

    def get_cluster_version(self) -> str | None:
        """Return the offering cluster MySQL version."""
        version = self._relation_data.get(self.cluster_version_key)
        if not version:
            return None

        return version

    def get_instance_address(self) -> str | None:
        """Return the offering cluster primary instance address."""
        endpoint = self._relation_data.get(self.instance_address_key)
        if not endpoint:
            return None

        return endpoint

    def get_instance_label(self) -> str | None:
        """Return the consuming cluster primary instance label."""
        label = self._relation_data.get(self.instance_label_key)
        if not label:
            return None

        return label

    def get_replication_ready_flag(self) -> bool | None:
        """Return the offering cluster replication ready flag."""
        flag = self._relation_data.get(self.replication_ready_key)
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

    def get_switchover_count(self) -> int:
        """Return the offering / consuming cluster switchover count."""
        count = self._relation_data.get(self.switchover_key)
        if not count:
            return 0

        return int(count)

    def set_cluster_name(self, name: str) -> None:
        """Set the offering / consuming cluster name."""
        self._relation_data.update({self.cluster_name_key: str(name)})

    def set_cluster_version(self, version: str) -> None:
        """Set the offering cluster version."""
        self._relation_data.update({self.cluster_version_key: str(version)})

    def set_instance_address(self, address: str) -> None:
        """Set the offering cluster primary instance address."""
        self._relation_data.update({self.instance_address_key: str(address)})

    def set_instance_label(self, label: str) -> None:
        """Set the consuming cluster primary instance label."""
        self._relation_data.update({self.instance_label_key: str(label)})

    def set_replication_name(self, label: str) -> None:
        """Set the offering cluster replication name."""
        self._relation_data.update({self.replication_name_key: str(label)})

    def set_replication_ready_flag(self, flag: bool) -> None:
        """Set the offering cluster replication ready flag."""
        self._relation_data.update({self.replication_ready_key: str(flag).lower()})

    def set_replica_flag(self, flag: bool) -> None:
        """Set the consuming cluster replica initialized flag."""
        self._relation_data.update({self.replica_key: str(flag).lower()})

    def set_secret_id(self, secret_id: str) -> None:
        """Set the offering cluster secret ID."""
        self._relation_data.update({self.secret_key: str(secret_id)})

    def set_switchover_count(self, count: int) -> None:
        """Set the offering / consuming cluster switchover count."""
        self._relation_data.update({self.switchover_key: str(count)})

    def delete_replication_ready_flag(self) -> None:
        """Delete the offering cluster ready flag."""
        self._relation_data.update({self.replication_ready_key: ""})
