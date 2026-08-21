# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from functools import cached_property

from charmlibs.pathops import PathProtocol

from .base import BasePaths


class RockPaths(BasePaths):
    """Class to deal with paths within the rock filesystem."""

    def __init__(self, root: PathProtocol):
        """Initialize the class attributes."""
        self._root = root

    @cached_property
    def backup_plugins(self) -> PathProtocol:
        """Return the path to the backup plugins folder."""
        return self._root / "usr" / "lib64" / "xtrabackup" / "plugin"

    @cached_property
    def logrotate_config(self) -> PathProtocol:
        """Return the path to the logrotate config file."""
        return self._root / "etc" / "logrotate.d" / "flush_mysql_logs"

    @cached_property
    def mysql_config_custom(self) -> PathProtocol:
        """Return the path to the MySQL custom config file."""
        return self._root / "etc" / "mysql" / "mysql.conf.d" / "z-custom.cnf"

    @cached_property
    def mysql_config_default(self) -> PathProtocol:
        """Return the path to the MySQL default config file."""
        return self._root / "etc" / "mysql" / "my.conf"

    @cached_property
    def mysql_archive(self) -> PathProtocol:
        """Return the path to the MySQL archive folder."""
        return self._root / "var" / "lib" / "mysql" / "archive"

    @cached_property
    def mysql_data(self) -> PathProtocol:
        """Return the path to the MySQL data folder."""
        return self._root / "var" / "lib" / "mysql" / "data"

    @cached_property
    def mysql_logs(self) -> PathProtocol:
        """Return the path to the MySQL logs folder."""
        return self._root / "var" / "lib" / "mysql" / "logs"

    @cached_property
    def mysql_temp(self) -> PathProtocol:
        """Return the path to the MySQL temp folder."""
        return self._root / "var" / "lib" / "mysql" / "temp"

    @cached_property
    def mysql_plugins(self) -> PathProtocol:
        """Return the path to the MySQL plugins folder."""
        return self._root / "usr" / "lib" / "mysql" / "plugin"

    @cached_property
    def mysql_socket(self) -> PathProtocol:
        """Return the path to the MySQL socket file."""
        return self._root / "var" / "run" / "mysqld" / "mysqld.sock"

    def binary(self, command: str) -> PathProtocol:
        """Return the path to the binary executable."""
        return self._root / "usr" / "bin" / command
