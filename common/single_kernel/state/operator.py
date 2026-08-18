# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import Application, Relation, Unit

from .secrets import BaseSecretStore


class OperatorState:
    """Class to deal with the operator state."""

    cluster_name_key = "cluster-name"
    cluster_set_name_key = "cluster-set-domain-name"
    cluster_removed_key = "removed-from-cluster-set"
    cluster_rejoin_key = "rejoin-secondaries"
    instance_host_key = "instance-hostname"
    instance_role_key = "member-role"
    instance_state_key = "member-state"
    unit_leader_key = "leader"
    unit_status_key = "unit-status"
    topology_timestamp_key = "topology-change-timestamp"

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
        """Return the MySQL cluster name."""
        name = self._relation_data.get(self.cluster_name_key)
        if not name:
            return None

        return name

    def get_cluster_set_name(self) -> str | None:
        """Return the MySQL cluster-set name."""
        name = self._relation_data.get(self.cluster_set_name_key)
        if not name:
            return None

        return name

    def get_cluster_removed_flag(self) -> bool | None:
        """Return the MySQL cluster removed flag."""
        flag = self._relation_data.get(self.cluster_removed_key)
        if not flag:
            return None

        return flag == "true"

    def get_cluster_rejoin_flag(self) -> bool | None:
        """Return the MySQL cluster rejoin flag."""
        flag = self._relation_data.get(self.cluster_rejoin_key)
        if not flag:
            return None

        return flag == "true"

    def get_instance_host(self) -> str | None:
        """Return the MySQL instance host."""
        host = self._relation_data.get(self.instance_host_key)
        if not host:
            return None

        return host

    def get_instance_role(self) -> str | None:
        """Return the MySQL instance role."""
        role = self._relation_data.get(self.instance_role_key)
        if not role:
            return None

        return role

    def get_instance_state(self) -> str | None:
        """Return the MySQL instance state."""
        state = self._relation_data.get(self.instance_state_key)
        if not state:
            return None

        return state

    def get_unit_leader_flag(self) -> bool | None:
        """Return the Juju unit leader flag."""
        flag = self._relation_data.get(self.unit_leader_key)
        if not flag:
            return None

        return flag == "true"

    def get_unit_status(self) -> str | None:
        """Return the Juju unit status."""
        status = self._relation_data.get(self.unit_status_key)
        if not status:
            return None

        return status

    def get_topology_timestamp(self) -> int | None:
        """Return the MySQL cluster topology change timestamp."""
        timestamp = self._relation_data.get(self.topology_timestamp_key)
        if not timestamp:
            return None

        return int(timestamp)

    def set_cluster_name(self, name: str) -> None:
        """Set the MySQL cluster name."""
        self._relation_data.update({self.cluster_name_key: str(name)})

    def set_cluster_set_name(self, name: str) -> None:
        """Set the MySQL cluster-set name."""
        self._relation_data.update({self.cluster_set_name_key: str(name)})

    def set_cluster_removed_flag(self, flag: bool) -> None:
        """Set the MySQL cluster removed flag."""
        self._relation_data.update({self.cluster_removed_key: str(flag).lower()})

    def set_cluster_rejoin_flag(self, flag: bool) -> None:
        """Set the MySQL cluster rejoin flag."""
        self._relation_data.update({self.cluster_rejoin_key: str(flag).lower()})

    def set_instance_host(self, host: str) -> None:
        """Set the MySQL instance host."""
        self._relation_data.update({self.instance_host_key: str(host)})

    def set_instance_role(self, role: str) -> None:
        """Set the MySQL instance role."""
        self._relation_data.update({self.instance_role_key: str(role)})

    def set_instance_state(self, state: str) -> None:
        """Set the MySQL instance state."""
        self._relation_data.update({self.instance_state_key: str(state)})

    def set_unit_leader_flag(self, flag: bool) -> None:
        """Set the Juju unit leader flag."""
        self._relation_data.update({self.unit_leader_key: str(flag).lower()})

    def set_unit_status(self, status: str) -> None:
        """Set the Juju unit status."""
        self._relation_data.update({self.unit_status_key: str(status)})

    def set_topology_timestamp(self, timestamp: int) -> None:
        """Set the MySQL cluster topology change timestamp."""
        self._relation_data.update({self.topology_timestamp_key: str(timestamp)})

    def delete_cluster_removed_flag(self) -> None:
        """Delete the MySQL cluster removed flag."""
        self._relation_data.update({self.cluster_removed_key: ""})

    def delete_cluster_rejoin_flag(self) -> None:
        """Delete the MySQL cluster rejoin flag."""
        self._relation_data.update({self.cluster_rejoin_key: ""})
