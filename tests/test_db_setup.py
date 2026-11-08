import pytest
from app.db.db import TEST_DB, get_connection
from werkzeug.security import generate_password_hash

@pytest.fixture(scope="module")
def setup_test_db():
    """
    Create and populate a temporary SQLite database for tests.

    The fixture recreates a minimal schema, inserts dummy graph data,
    dummy users, and test operator-node assignments.

    :yield: None
    """
    # Create and connect to the test DB
    with get_connection(TEST_DB) as conn:
        c = conn.cursor()

        # Create minimal schema
        c.executescript("""
            DROP TABLE IF EXISTS nodes;
            DROP TABLE IF EXISTS edges;
            DROP TABLE IF EXISTS rooms;
            DROP TABLE IF EXISTS users;
            DROP TABLE IF EXISTS operator_nodes;
    
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                name TEXT,
                type TEXT,
                floor INTEGER,
                wing TEXT,
                label TEXT
            );
            CREATE TABLE edges (
                from_node INTEGER,
                to_node INTEGER,
                instruction_hun TEXT,
                instruction_en TEXT,
                cost INTEGER,
                open INTEGER
            );
            CREATE TABLE rooms (
                room_number TEXT PRIMARY KEY,
                node_id INTEGER,
                name TEXT,
                label TEXT,
                direction_hint_hun TEXT,
                direction_hint_en TEXT,
                state TEXT
            );
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','operator'))
            );
            CREATE TABLE operator_nodes (
                operator_id INTEGER,
                node_id INTEGER,
                PRIMARY KEY (operator_id, node_id),
                FOREIGN KEY (operator_id) REFERENCES users(id),
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            );
        """)

        # Insert dummy node data
        c.executemany("INSERT INTO nodes (id, name, type, floor, wing, label) VALUES (?, ?, ?, ?, ?, ?)", [
            (1, "Hall A", "corridor", 0, "A", None),
            (2, "Stairs A", "staircase", 1, "A", None),
            (3, "Hall B", "corridor", 1, "B", None),
            (4, "Elevator 1", "elevator", 1, "B", None),
        ])

        # Insert dummy edge data
        c.executemany("INSERT INTO edges (from_node, to_node, instruction_hun, instruction_en, cost, open) VALUES (?, ?, ?, ?, ?, ?)", [
            (1, 2, "Menj fel a lépcsőn", "Go up stairs", 2, 1),
            (2, 3, None, None, 3, 1),
            (3, 4, "Menj lifttel az első emeletre", "Take the elevator to the first floor", 1, 1),
        ])

        # Insert dummy rooms
        c.executemany("INSERT INTO rooms (room_number, node_id, name, label, direction_hint_hun, direction_hint_en, state) VALUES (?, ?, ?, ?, ?, ?, ?)", [
            ("100", 1, "Office A", "lab", "észak", "north", "free"),
            ("200", 3, "Office B", "lab", "balra", "left", "free"),
        ])

        # Insert dummy users
        c.executemany("""
        INSERT INTO users (id, username, password_hash, role)
        VALUES (?, ?, ?, ?)
        """, [
            (1, "admin", generate_password_hash("adminpass"), "admin"),
            (2, "operator1", generate_password_hash("operatorpass"), "operator"),
        ])

        # Insert dummy operator-node assignment
        c.executemany("""
        INSERT INTO operator_nodes (operator_id, node_id)
        VALUES (?, ?)
        """, [
            (2, 1),  # operator1 can edit node 1 only
        ])
        conn.commit()

        # Yield to the test session
        yield
