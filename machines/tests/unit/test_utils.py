#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import re

from parameterized import parameterized

from utils import _password_meets_rules, compare_dictionaries, generate_random_password


def test_generate_random_password():
    """Test generate_random_password function."""
    random_password = generate_random_password(20)
    assert len(random_password) == 20
    assert re.match(r"^[a-zA-Z0-9]{20}$", random_password)
    assert _password_meets_rules(random_password)


@parameterized.expand([
    ("valid", "Abc123", True),
    ("no_uppercase", "abc123", False),
    ("no_lowercase", "ABC123", False),
    ("no_digit", "AbcDef", False),
])
def test_password_meets_rules(name, password, expected):
    """Test _password_meets_rules helper."""
    assert _password_meets_rules(password) == expected


def test_compare_dictionaries():
    dict1 = {"a": 1, "b": 2, "c": 3, "f": 4}
    dict2 = {"a": 1, "b": 3, "d": 5, "e": 6, "f": 4}

    assert compare_dictionaries(dict1, dict2) == {"b", "c", "d", "e"}
