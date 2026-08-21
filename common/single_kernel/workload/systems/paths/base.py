# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod

from charmlibs.pathops import PathProtocol


class BasePaths(ABC):
    """Abstract class to deal with paths within a filesystem."""

    @property
    @abstractmethod
    def backup_plugins(self) -> PathProtocol:
        """Return the path to the backup plugins folder."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def logrotate_config(self) -> PathProtocol:
        """Return the path to the logrotate config file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_config_custom(self) -> PathProtocol:
        """Return the path to the MySQL custom config file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_config_default(self) -> PathProtocol:
        """Return the path to the MySQL default config file."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_archive(self) -> PathProtocol:
        """Return the path to the MySQL archive folder."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_data(self) -> PathProtocol:
        """Return the path to the MySQL data folder."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_logs(self) -> PathProtocol:
        """Return the path to the MySQL logs folder."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_temp(self) -> PathProtocol:
        """Return the path to the MySQL temp folder."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_plugins(self) -> PathProtocol:
        """Return the path to the MySQL plugins folder."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def mysql_socket(self) -> PathProtocol:
        """Return the path to the MySQL socket file."""
        raise NotImplementedError()

    @abstractmethod
    def binary(self, command: str) -> PathProtocol:
        """Return the path to the binary executable."""
        raise NotImplementedError()
