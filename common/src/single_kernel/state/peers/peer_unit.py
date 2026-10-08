# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from typing import MutableMapping


class PeerStateUnit:
    """Class to deal with the peer unit state."""

    # NOTE:
    # Coming up with the consolidated list of state key was hard.
    # Keep this note until the final code cut-over is performed:
    #
    # - `instance-hostname`:
    #   Removed, given that is only used in the promote-primary action,
    #   does not take into account Juju spaces, and can be computed at runtime.
    # - `topology-change-timestamp`:
    #   Removed, given that it is used to conditionally update endpoints on the
    #   database-peers relation change, by populating this field upon promote-to-primary.
    #   Now it always occurs, as member-state / member-role fields are updated after promotion.
    # - `unit-container-restarts`:
    #   Removed, given that is only written, and never read.

    instance_role_key = "member-role"
    instance_state_key = "member-state"
    unit_leader_key = "leader"
    unit_status_key = "unit-status"

    service_address_hostname_key = "hostname-details"
    service_address_pid_key = "ip-address-manager-pid"
    service_healing_pid_key = "self-healing-manager-pid"
    service_logrotate_pid_key = "log-rotate-manager-pid"
    service_logrotate_sync_key = "logs-synced"

    def __init__(self, data: MutableMapping[str, str]):
        """Initialize the class attributes."""
        self._data = data

    def get_address_hostname(self) -> dict | None:
        """Get the address resolution hostname details."""
        details = self._data.get(self.service_address_hostname_key)
        if not details:
            return None

        return json.loads(details)

    def get_address_service_pid(self) -> int | None:
        """Get the address resolution process ID."""
        manager_pid = self._data.get(self.service_address_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def get_healing_service_pid(self) -> int | None:
        """Get the self-healing process ID."""
        manager_pid = self._data.get(self.service_healing_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def get_instance_role(self) -> str:
        """Get the MySQL instance role."""
        role = self._data.get(self.instance_role_key)
        if not role:
            return "UNKNOWN"

        return role

    def get_instance_state(self) -> str:
        """Get the MySQL instance state."""
        state = self._data.get(self.instance_state_key)
        if not state:
            return "UNKNOWN"

        return state

    def get_logrotate_service_pid(self) -> int | None:
        """Get the log-rotation process ID."""
        manager_pid = self._data.get(self.service_logrotate_pid_key)
        if not manager_pid:
            return None

        return int(manager_pid)

    def get_logrotate_sync_flag(self) -> bool | None:
        """Get the log-rotation synchronization flag."""
        flag = self._data.get(self.service_logrotate_sync_key)
        if not flag:
            return None

        return flag == "true"

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

    def set_address_hostname(self, details: dict) -> None:
        """Set the address resolution hostname details."""
        self._data.update({self.service_address_hostname_key: json.dumps(details)})

    def set_address_service_pid(self, manager_pid: int) -> None:
        """Set the address resolution process ID."""
        self._data.update({self.service_address_pid_key: str(manager_pid)})

    def set_healing_service_pid(self, manager_pid: int) -> None:
        """Set the self-healing process ID."""
        self._data.update({self.service_healing_pid_key: str(manager_pid)})

    def set_instance_role(self, role: str | None) -> None:
        """Set the MySQL instance role."""
        if not role:
            role = "UNKNOWN"

        self._data.update({self.instance_role_key: str(role)})

    def set_instance_state(self, state: str | None) -> None:
        """Set the MySQL instance state."""
        if not state:
            state = "UNKNOWN"

        self._data.update({self.instance_state_key: state})

    def set_logrotate_service_pid(self, manager_pid: int) -> None:
        """Set the log-rotation process ID."""
        self._data.update({self.service_logrotate_pid_key: str(manager_pid)})

    def set_logrotate_sync_flag(self, flag: bool) -> None:
        """Set the log-rotation synchronization flag."""
        self._data.update({self.service_logrotate_sync_key: str(flag).lower()})

    def set_unit_address(self, relation: str, address: str) -> None:
        """Set the Juju unit address for the relation."""
        self._data.update({f"{relation}-address": str(address)})

    def set_unit_leader_flag(self, flag: bool) -> None:
        """Set the Juju unit leader flag."""
        self._data.update({self.unit_leader_key: str(flag).lower()})

    def set_unit_removing_flag(self) -> None:
        """Set the unit removing flag."""
        self._data.update({self.unit_status_key: "removing"})

    def delete_address_service_pid(self) -> None:
        """Delete the address resolution process ID."""
        self._data.pop(self.service_address_pid_key, None)

    def delete_healing_service_pid(self) -> None:
        """Delete the self-healing process ID."""
        self._data.pop(self.service_healing_pid_key, None)

    def delete_logrotate_service_pid(self) -> None:
        """Delete the log-rotation process ID."""
        self._data.pop(self.service_logrotate_pid_key, None)

    def delete_logrotate_sync_flag(self) -> None:
        """Delete the log-rotation synchronization flag."""
        self._data.pop(self.service_logrotate_sync_key, None)
