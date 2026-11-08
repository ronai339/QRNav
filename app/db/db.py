import sqlite3
import os

# Base directory (project root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

# Instance folder (for runtime DB files)
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

# Ensure instance folder exists
os.makedirs(INSTANCE_DIR, exist_ok=True)

# Database paths
DB_PATH = os.path.join(INSTANCE_DIR, "qrnav.db")
TEST_DB = os.path.join(BASE_DIR, "tests/test_qrnav.db")

# Folders for to-be-imported and exported files using data management scripts
SEED_FOLDER = os.path.join(BASE_DIR, "data/seed")
EXPORT_FOLDER = os.path.join(BASE_DIR, "data/export")

def get_connection(db_path=None):
    """
    Creates and returns a SQLite connection for the given database path.

    If no path is provided, the current main application database path is used.
    This makes the function easier to redirect in tests.
    This helper is used across the project so that connection creation stays consistent.

    :param db_path: str, path to the SQLite database file
    :return: sqlite.Connection, open SQLite connection
    """
    if db_path is None:
        db_path = DB_PATH
    return sqlite3.connect(db_path)