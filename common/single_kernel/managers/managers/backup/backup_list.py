# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import enum
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Self

logger = logging.getLogger(__name__)


class BackupStatus(enum.StrEnum):
    """Backup possible statuses."""

    IN_PROGRESS = "in progress"
    FINISHED = "finished"
    FAILED = "failed"


@dataclass
class BackupInfo:
    """Class to hold the backup info."""

    id: str
    status: BackupStatus

    @classmethod
    def from_storage(cls, backup_id: str, checksum: bool, log_file: bool) -> Self:
        """Constructs an object given other files presence."""
        if not checksum and not log_file:
            return cls(backup_id, BackupStatus.IN_PROGRESS)
        if not checksum and log_file:
            return cls(backup_id, BackupStatus.FAILED)
        if checksum and log_file:
            return cls(backup_id, BackupStatus.FINISHED)

        raise ValueError("Backup cannot have a checksum but no log-file")


class BackupListHelper:
    """Class to deal with the backup lists."""

    @staticmethod
    def collect_backups(bucket_path: str, pages: Iterable[dict]) -> list[BackupInfo]:
        """Collect backups from the storage pages."""
        metadata_ids = []
        checksum_ids = []
        log_ids = []

        for page in pages:
            for content in page.get("Contents", []):
                file_path = content["Key"].removeprefix(bucket_path)
                file_path = Path(file_path)

                match file_path.suffix:
                    case ".metadata":
                        try:
                            time.strptime(file_path.stem, "%Y-%m-%dT%H:%M:%SZ")
                        except ValueError:
                            continue
                        metadata_ids.append(file_path.stem)
                    case ".md5":
                        checksum_ids.append(file_path.stem)
                    case ".backup.log":
                        log_ids.append(file_path.stem)

        backups_info = []
        for id in metadata_ids:
            info = BackupInfo.from_storage(id, checksum=id in checksum_ids, log_file=id in log_ids)
            backups_info.append(info)

        return sorted(backups_info, key=lambda backup: backup.id)

    @staticmethod
    def format_backups(backups: list[BackupInfo]) -> str:
        """Format backups into a table output."""
        header = f"{'backup-id':<21} | {'backup-type':<12} | {'backup-status':<12}"
        border = f"-" * len(header)
        output = [header, border]

        for backup in backups:
            output.append(f"{backup.id:<21} | {'physical':<12} | {backup.status:<12}")

        return "\n".join(output)
