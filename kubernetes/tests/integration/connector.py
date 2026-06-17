#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import mysql.connector


def create_db_connections(
    num_connections: int, host: str, username: str, password: str, database: str
) -> list[mysql.connector.MySQLConnection]:
    """Create a list of database connections.

    Args:
        num_connections: Number of connections to create.
        host: Hostname of the database.
        username: Username to connect to the database.
        password: Password to connect to the database.
        database: Database to connect to.
    """
    connections = []
    for _ in range(num_connections):
        conn = mysql.connector.connect(
            host=host,
            user=username,
            password=password,
            database=database,
            use_pure=True,
        )
        if conn.is_connected():
            connections.append(conn)
    return connections
