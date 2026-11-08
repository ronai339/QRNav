import csv
import os
from app.db.db import DB_PATH, EXPORT_FOLDER, get_connection

def export_table(table_name, file_name):
    """
    Export a complete database table into a CSV file.

    The function writes the column headers and all rows to the export folder.

    :param table_name: str, database table to export
    :param file_name: str, output CSV file name
    :return: None
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()

        # Query everything
        c.execute(f"SELECT * FROM {table_name}")
        rows = c.fetchall()

        # Get column names
        col_names = [description[0] for description in c.description]

        # Write to CSV
        os.makedirs(EXPORT_FOLDER, exist_ok=True)
        with open(os.path.join(EXPORT_FOLDER, file_name), mode="w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(col_names)
            writer.writerows(rows)

        print(f"✅ Exported {table_name} to {file_name}")

def export_all():
    """
    Export all main QRNav tables to separate CSV files.

    This helper exports nodes, edges, and rooms in one run.

    :return: None
    """
    export_table("nodes", "nodes.csv")
    export_table("edges", "edges.csv")
    export_table("rooms", "rooms.csv")

if __name__ == "__main__":
    export_all()