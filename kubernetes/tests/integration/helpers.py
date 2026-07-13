# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import itertools
import secrets
import string

from mysql.connector.errors import (
    DatabaseError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
)
from tenacity import retry, stop_after_attempt, wait_fixed

from .connector import MySQLConnector


def generate_random_string(length: int) -> str:
    """Generate a random string of the provided length.

    Args:
        length: the length of the random string to generate

    Returns:
        A random string comprised of letters and digits
    """
    choices = string.ascii_letters + string.digits
    return "".join([secrets.choice(choices) for i in range(length)])


def execute_queries_on_unit(
    unit_address: str,
    username: str,
    password: str,
    queries: list[str],
    commit: bool = False,
) -> list:
    """Execute given MySQL queries on a unit.

    Args:
        unit_address: The public IP address of the unit to execute the queries on
        username: The MySQL username
        password: The MySQL password
        queries: A list of queries to execute
        commit: A keyword arg indicating whether there are any writes queries

    Returns:
        A list of rows that were potentially queried
    """
    config = {
        "user": username,
        "password": password,
        "host": unit_address,
        "raise_on_warnings": False,
    }

    with MySQLConnector(config, commit) as cursor:
        for query in queries:
            cursor.execute(query)
        output = list(itertools.chain(*cursor.fetchall()))

    return output


@retry(stop=stop_after_attempt(8), wait=wait_fixed(15), reraise=True)
def is_connection_possible(credentials: dict, **extra_opts) -> bool:
    """Test a connection to a MySQL server.

    Args:
        credentials: A dictionary with the credentials to test
        extra_opts: extra options for mysql connection
    """
    config = {
        "user": credentials["username"],
        "password": credentials["password"],
        "host": credentials["host"],
        "raise_on_warnings": False,
        "connection_timeout": 10,
        **extra_opts,
    }

    try:
        with MySQLConnector(config) as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
    except (DatabaseError, InterfaceError, OperationalError, ProgrammingError):
        # Errors raised when the connection is not possible
        return False
