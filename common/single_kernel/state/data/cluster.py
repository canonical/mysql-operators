# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from ._base import BaseData


class ClusterData(BaseData):
    """Class to deal with the cluster data."""

    cluster_name_key = "cluster-name"
    cluster_set_name_key = "cluster-set-domain-name"
    cluster_removed_key = "removed-from-cluster-set"
    cluster_rejoin_key = "rejoin-secondaries"

    def get_cluster_name(self) -> str | None:
        """Get the MySQL cluster name."""
        name = self._data.get(self.cluster_name_key)
        if not name:
            return None

        return name

    def get_cluster_set_name(self) -> str | None:
        """Get the MySQL cluster-set name."""
        name = self._data.get(self.cluster_set_name_key)
        if not name:
            return None

        return name

    def get_cluster_removed_flag(self) -> bool | None:
        """Get the MySQL cluster removed flag."""
        flag = self._data.get(self.cluster_removed_key)
        if not flag:
            return None

        return flag == "true"

    def get_cluster_rejoin_flag(self) -> bool | None:
        """Get the MySQL cluster rejoin flag."""
        flag = self._data.get(self.cluster_rejoin_key)
        if not flag:
            return None

        return flag == "true"

    def set_cluster_name(self, name: str) -> None:
        """Set the MySQL cluster name."""
        self._data.update({self.cluster_name_key: str(name)})

    def set_cluster_set_name(self, name: str) -> None:
        """Set the MySQL cluster-set name."""
        self._data.update({self.cluster_set_name_key: str(name)})

    def set_cluster_removed_flag(self, flag: bool) -> None:
        """Set the MySQL cluster removed flag."""
        self._data.update({self.cluster_removed_key: str(flag).lower()})

    def set_cluster_rejoin_flag(self, flag: bool) -> None:
        """Set the MySQL cluster rejoin flag."""
        self._data.update({self.cluster_rejoin_key: str(flag).lower()})

    def delete_cluster_removed_flag(self) -> None:
        """Delete the MySQL cluster removed flag."""
        self._data.pop(self.cluster_removed_key, None)

    def delete_cluster_rejoin_flag(self) -> None:
        """Delete the MySQL cluster rejoin flag."""
        self._data.pop(self.cluster_rejoin_key, None)
