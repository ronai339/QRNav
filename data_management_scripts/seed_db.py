import csv
import os
from app.db.db import DB_PATH, SEED_FOLDER, get_connection

def import_csv():
    """
    Seed the main database from CSV files in the seed folder.

    Existing nodes, edges, and rooms are removed first,
    then the seed CSV files are imported into the database.

    :return: None
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()

        # Clear existing data
        c.execute("DELETE FROM edges")
        c.execute("DELETE FROM rooms")
        c.execute("DELETE FROM nodes")

        # Load nodes.csv
        with open(os.path.join(SEED_FOLDER, "nodes.csv"), newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            nodes = [(int(row["id"]), row["name"], row["type"], int(row["floor"]), row["wing"], row["label"] or None)
                 for row in reader]
            c.executemany("INSERT INTO nodes (id, name, type, floor, wing, label) VALUES (?, ?, ?, ?, ?, ?) ", nodes)

        # Load edges.csv
        with open(os.path.join(SEED_FOLDER, "edges.csv"), newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            edges = [(int(row["id"]), int(row["from_node"]), int(row["to_node"]), float(row["cost"]),
                      row["instruction_hun"] or None, row["instruction_en"] or None, int(row["open"]))
                     for row in reader]
            c.executemany("INSERT INTO edges (id, from_node, to_node, cost, instruction_hun, instruction_en, open) VALUES (?, ?, ?, ?, ?, ?, ?) ",edges)

        # Load rooms.csv
        with open(os.path.join(SEED_FOLDER, "rooms.csv"), newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rooms = [(row["room_number"], int(row["node_id"]), row["name"],
                      row["label"] or None, row["direction_hint_hun"] or None, row["direction_hint_en"] or None)
                     for row in reader]
            c.executemany("INSERT INTO rooms (room_number, node_id, name, label, direction_hint_hun, direction_hint_en) VALUES (?, ?, ?, ?, ?, ?)",rooms)

        conn.commit()
        print("✅ CSV data imported successfully!")

if __name__ == "__main__":
    import_csv()