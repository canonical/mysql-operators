# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


class PasswordConfigHelper:
    """Class to deal with the MySQL server password plugin config."""

    static_keys = {}

    def __init__(self):
        """Initialize the class attributes."""
        pass

    def get_config(self) -> dict:
        """Return the MySQL server password plugin config."""
        return {
            "loose-validate_password.check_user_name": "ON",
            "loose-validate_password.length": 12,
            "loose-validate_password.mixed_case_count": 1,
            "loose-validate_password.number_count": 1,
            "loose-validate_password.policy": "MEDIUM",
            "loose-validate_password.special_char_count": 0,
        }
