# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from abc import ABC, abstractmethod


class BaseSecretStore(ABC):
    """Abstract class to deal with a secrets store."""

    @abstractmethod
    def create_secret(self, content: dict[str, str]) -> str:
        """Create a secret."""
        raise NotImplementedError()

    @abstractmethod
    def delete_secret(self, secret_id: str) -> None:
        """Delete a secret."""
        raise NotImplementedError()

    @abstractmethod
    def get_secret_content(self, secret_id: str) -> dict[str, str]:
        """Get a secret content."""
        raise NotImplementedError()

    @abstractmethod
    def set_secret_content_by_id(self, secret_id: str, content: dict[str, str]) -> None:
        """Set a secret content by ID."""
        raise NotImplementedError()

    @abstractmethod
    def set_secret_content_by_label(self, secret_label: str, content: dict[str, str]) -> None:
        """Set a secret content by label."""
        raise NotImplementedError()
