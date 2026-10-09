# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from mysql_shell.models import LogType

TextLogs = [
    LogType.ERROR,
    LogType.GENERAL,
    LogType.SLOW,
]
