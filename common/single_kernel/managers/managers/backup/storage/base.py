# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from abc import ABC, abstractmethod

from botocore.client import BaseClient
from charmlibs.pathops import PathProtocol

logger = logging.getLogger(__name__)


class BaseBackupStorage(ABC):
    """Abstract Class to deal with the backup storage."""

    name: str
    certs_dir_name: str
    certs_file_name: str

    @property
    @abstractmethod
    def bucket_name(self) -> str:
        """Return the bucket name."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def bucket_path(self) -> str:
        """Return the bucket path."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def ca_chain(self) -> str | None:
        """Return the CA chain."""
        raise NotImplementedError()

    @abstractmethod
    def build_backup_args(self, ca_chain_path: str | PathProtocol | None) -> list[str]:
        """Build the backup args for upload / download."""
        raise NotImplementedError()

    @abstractmethod
    def build_backup_env(self) -> dict[str, str]:
        """Build the backup env for upload / download."""
        raise NotImplementedError()

    @abstractmethod
    def build_backup_client(self, ca_chain_path: str | PathProtocol | None) -> BaseClient:
        """Build the backup client for upload / download."""
        raise NotImplementedError()
