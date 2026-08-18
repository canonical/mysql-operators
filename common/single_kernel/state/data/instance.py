# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ._base import BaseData


class InstanceData(BaseData):
    """Class to deal with the instance data."""

    # NOTE:
    # Coming up with the consolidated list of state key was hard.
    # Keep this note until the final code cut-over is performed:
    #
    # - `instance-hostname`:
    #   Removed, given that is only used in the promote-primary action,
    #   does not take into account Juju spaces, and can be computed at runtime.
    # - `topology-change-timestamp`:
    #   Removed, given that it is used to conditionally update endpoints on the
    #   database-peers relation change. Now it is always done.
    # - `unit-container-restarts`:
    #   Removed, given that is only written, and never read,

    instance_role_key = "member-role"
    instance_state_key = "member-state"
    unit_leader_key = "leader"
    unit_status_key = "unit-status"

    def get_instance_role(self) -> str | None:
        """Get the MySQL instance role."""
        role = self._data.get(self.instance_role_key)
        if not role:
            return None

        return role

    def get_instance_state(self) -> str | None:
        """Get the MySQL instance state."""
        state = self._data.get(self.instance_state_key)
        if not state:
            return None

        return state

    def get_unit_address(self, relation: str) -> str | None:
        """Get the Juju unit address for the relation."""
        address = self._data.get(f"{relation}-address")
        if not address:
            return None

        return address

    def get_unit_leader_flag(self) -> bool | None:
        """Get the Juju unit leader flag."""
        flag = self._data.get(self.unit_leader_key)
        if not flag:
            return None

        return flag == "true"

    def get_unit_removing_flag(self) -> bool | None:
        """Get the unit removing flag."""
        status = self._data.get(self.unit_status_key)
        if not status:
            return None

        return status == "removing"

    def set_instance_role(self, role: str) -> None:
        """Set the MySQL instance role."""
        self._data.update({self.instance_role_key: str(role)})

    def set_instance_state(self, state: str) -> None:
        """Set the MySQL instance state."""
        self._data.update({self.instance_state_key: str(state)})

    def set_unit_address(self, relation: str, address: str) -> None:
        """Set the Juju unit address for the relation."""
        self._data.update({f"{relation}-address": str(address)})

    def set_unit_leader_flag(self, flag: bool) -> None:
        """Set the Juju unit leader flag."""
        self._data.update({self.unit_leader_key: str(flag).lower()})

    def set_unit_removing_flag(self) -> None:
        """Set the unit removing flag."""
        self._data.update({self.unit_status_key: "removing"})
