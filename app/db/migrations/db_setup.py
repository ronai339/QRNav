from app.db.db import DB_PATH, get_connection

def create_db():
    """
    Recreate the main QRNav database schema.

    The function drops the core tables and then creates the working
    schema for nodes, rooms, users, and operator-node assignments.
    It is intended for initial setup, reset, or test database preparation.

    :return: None
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.executescript("""
            DROP TABLE IF EXISTS nodes;
            DROP TABLE IF EXISTS edges;
            DROP TABLE IF EXISTS rooms;
            DROP TABLE IF EXISTS users;
            DROP TABLE IF EXISTS operator_nodes;
            DROP TABLE IF EXISTS graph_changes;
    
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT CHECK(type IN ('corridor', 'staircase', 'elevator', 'exit', 'other')),
                floor INTEGER,
                wing TEXT,
                label TEXT
            );
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_node INTEGER,
                to_node INTEGER,
                cost REAL,
                instruction_hun TEXT,
                instruction_en TEXT,
                open BOOLEAN DEFAULT 1,
                FOREIGN KEY (from_node) REFERENCES nodes(id),
                FOREIGN KEY (to_node) REFERENCES nodes(id)
            );
            CREATE TABLE IF NOT EXISTS rooms (
                room_number TEXT PRIMARY KEY,
                node_id INTEGER,
                name TEXT,
                label TEXT,
                direction_hint_hun TEXT,
                direction_hint_en TEXT,
                state TEXT NOT NULL DEFAULT 'undefined' CHECK (state IN (
                    'free',
                    'closed',
                    'in_use',
                    'maintenance',
                    'undefined'
                )),
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','operator'))
            );
            CREATE TABLE IF NOT EXISTS operator_nodes (
                operator_id INTEGER,
                node_id INTEGER,
                PRIMARY KEY (operator_id, node_id),
                FOREIGN KEY (operator_id) REFERENCES users(id),
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            );
            CREATE TABLE IF NOT EXISTS graph_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user TEXT,
                action_type TEXT,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                FOREIGN KEY (user) REFERENCES users(username)
            );
            INSERT INTO users (username, password_hash, role)
            VALUES ('admin','scrypt:32768:8:1$rStFtr4YVnbx0SfQ$c8e7dda4b05748eff01b049eb1ec248868df9e99cc037293e3774b82558ab8da86705064ef366d640250ff05cb48167c7a01290b32e1de5914108d9f06bbd2d7','admin');
        """)

        conn.commit()
        print("Database created:", DB_PATH)

if __name__ == "__main__":
    create_db()