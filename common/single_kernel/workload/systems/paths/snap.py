# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from functools import cached_property

from charmlibs.pathops import PathProtocol

from .base import BasePaths


class SnapPaths(BasePaths):
    """Class to deal with paths within the snap filesystem."""

    def __init__(self, root: PathProtocol, snap_name: str):
        """Initialize the class attributes."""
        self._root = root
        self._snap = snap_name

    @cached_property
    def _common(self) -> PathProtocol:
        """Return the path to the common snap folder."""
        return self._root / "var" / "snap" / self._snap / "common"

    @cached_property
    def _current(self) -> PathProtocol:
        """Return the path to the common snap folder."""
        return self._root / "var" / "snap" / self._snap / "current"

    @cached_property
    def _plugins(self) -> PathProtocol:
        """Return the path to the plugin folders."""
        return self._root / "snap" / self._snap / "current" / "usr" / "lib"

    @cached_property
    def backup_plugins(self) -> PathProtocol:
        """Return the path to the backup plugins folder."""
        return self._plugins / "xtrabackup" / "plugin"

    @cached_property
    def logrotate_config(self) -> PathProtocol:
        """Return the path to the logrotate config file."""
        return self._root / "etc" / "logrotate.d" / "flush_mysql_logs"

    @cached_property
    def mysql_config_custom(self) -> PathProtocol:
        """Return the path to the MySQL custom config file."""
        return self._current / "etc" / "mysql" / "mysql.conf.d" / "z-custom-mysqld.cnf"

    @cached_property
    def mysql_config_default(self) -> PathProtocol:
        """Return the path to the MySQL default config file."""
        return self._current / "etc" / "mysql" / "mysql.cnf"

    @cached_property
    def mysql_archive(self) -> PathProtocol:
        """Return the path to the MySQL archive folder."""
        return self._common / "var" / "lib" / "mysql" / "archive"

    @cached_property
    def mysql_data(self) -> PathProtocol:
        """Return the path to the MySQL data folder."""
        return self._common / "var" / "lib" / "mysql" / "data"

    @cached_property
    def mysql_logs(self) -> PathProtocol:
        """Return the path to the MySQL logs folder."""
        return self._common / "var" / "lib" / "mysql" / "logs"

    @cached_property
    def mysql_temp(self) -> PathProtocol:
        """Return the path to the MySQL temp folder."""
        return self._common / "var" / "lib" / "mysql" / "temp"

    @cached_property
    def mysql_plugins(self) -> PathProtocol:
        """Return the path to the MySQL plugins folder."""
        return self._plugins / "mysql" / "plugin"

    @cached_property
    def mysql_socket(self) -> PathProtocol:
        """Return the path to the MySQL socket file."""
        return self._common / "var" / "run" / "mysqld" / "mysqld.sock"

    def binary(self, command: str) -> PathProtocol:
        """Return the path to the binary executable."""
        return self._root / "snap" / "bin" / f"{self._snap}.{command}"
