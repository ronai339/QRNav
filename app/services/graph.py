import networkx as nx
from app.db.db import get_connection


# GRAPH:

# Graph construction
def load_graph(db_path):
    """
    Loads the navigable graph from the SQLite database.

    Nodes are read from the 'nodes' table and edges from the 'edges' table.
    Only open edges are added to the graph, and edge cost is stored
    as the NetworkX weight attribute.

    :param db_path: str, path to the SQLite database
    :return: networkx.Digraph, directed graph used for routing
    """
    with get_connection(db_path) as conn:
        c = conn.cursor()
        g = nx.DiGraph()

        # Load nodes into graph
        c.execute("SELECT id FROM nodes")
        for (node_id,) in c.fetchall():
            g.add_node(node_id)

        # Load edges into graph
        c.execute("SELECT from_node, to_node, cost, open FROM edges")
        for from_node, to_node, cost, is_open in c.fetchall():
            if is_open:
                g.add_edge(from_node, to_node, weight=cost)
    return g

# Get the node containing the given room
def get_node_for_room(room_number, db_path):
    """
    Resolve a room number to the node that contains it.

    :param room_number: room number to search for
    :param db_path: str, path to the SQLite database
    :return: int, node ID if the room exists, otherwise None
    """
    with get_connection(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT node_id FROM rooms WHERE room_number = ?", (room_number,))
        result = c.fetchone()
    return result[0] if result else None


# PATHFINDING:

# Finding the shortest path, listing the nodes touched
def find_path_by_nodes(from_node, to_node, db_path):
    """
    Finds the shortest path between two nodes.

    The function uses the current graph state and weights stored in the database.
    It returns the node sequence together with an error message when no path can be found.

    :param from_node: int, start node ID
    :param to_node: int, destination node ID
    :param db_path: str, path to the SQLite database
    :return: tuple[list[int]] | None, str | None, path and error message
    """
    g = load_graph(db_path)
    try:
        path = nx.shortest_path(g, from_node, to_node, weight="weight")
        return path, None
    except nx.NetworkXNoPath:
        return None, "No path found between nodes."
    except nx.NodeNotFound:
        return None, "Invalid node."

# Computing path cost
def compute_path_cost(from_node, to_node, db_path):
    """
    Calculates the total weighted cost of the shortest path between two nodes.

    :param from_node: int, start node ID
    :param to_node: int, destination ID
    :param db_path: str, path to the SQLite database
    :return: float | int, total path cost
    :raise: ValueError, if no path exists between the two nodes
    """
    g = load_graph(db_path)
    try:
        return nx.shortest_path_length(g, from_node, to_node, weight="weight")
    except KeyError:
        raise ValueError(f"No path between {from_node} and {to_node}.")

# Resolving user input
def resolve_room(query, is_start=False, start_node_id=None, db_path=None, lang="en"):
    """
    Resolves user input to a concrete room record.

    The function accepts room numbers, room names, and labels.
    For destination lookup by label, it can choose the closest matching
    room to the current start node when multiple rooms share the same label.

    :param query: str, raw user input
    :param is_start: bool, whether the lookup is for the start room
    :param start_node_id: int | None, required when resolving destination via label
    :param db_path: str | None, path to the SQLite database
    :param lang: str, language code for error messages and room data
    :return: dict, room data containing room number, node ID, name, label, direction hints and state
    :raise: ValueError, if the room cannot be resolved or the input is ambiguous
    """
    with get_connection(db_path) as conn:
        c = conn.cursor()
        query = query.strip()

        # Try room_number (exact match)
        if query.isdigit():
            c.execute("SELECT * FROM rooms WHERE room_number = ?", (int(query),))
            row = c.fetchone()
            if row:
                return _row_to_dict(row, lang)

        # Try exact name match (case-insensitive)
        c.execute("SELECT * FROM rooms WHERE LOWER(name) = LOWER(?)", (query,))
        row = c.fetchone()
        if row:
            return _row_to_dict(row, lang)

        # If resolving start room, stop here
        if is_start:
            if lang == "en":
                raise ValueError("Start room not found or ambiguous.")
            else:
                raise ValueError("Kezdő helyiség nem található vagy nem egyértelmű.")

        # Try label match (case-insensitive)
        c.execute("SELECT * FROM rooms WHERE LOWER(label) = LOWER(?)", (query,))
        rows = c.fetchall()
        if not rows:
            if lang == "en":
                raise ValueError("Destination room not found.")
            else:
                raise ValueError("Cél helyiség nem található.")
        if len(rows) == 1:
            return _row_to_dict(rows[0],lang=lang)

        # Multiple matches -> pick closest
        if start_node_id is None:
            if lang == "en":
                raise ValueError("start_node_id required for label-based resolution.")
            else:
                raise ValueError("start_node_id megadása szükséges a címke alapú kereséshez.")

        best_room = None
        best_cost = float("inf")
        g = load_graph(db_path)

        for row in rows:
            room = _row_to_dict(row, lang=lang)
            try:
                path = nx.dijkstra_path(g,start_node_id,room["node_id"],weight="weight")
                cost = nx.path_weight(g,path,weight="weight")
                if cost is not None and cost < best_cost:
                    best_cost = cost
                    best_room = room
            except nx.NetworkXNoPath:
                continue
        if best_room is None:
            if lang == "en": raise ValueError("No reachable room found for that label.")
            else: raise ValueError("Nincs elérhető helyiség a megadott címkével.")
    return best_room

# Transform row to dictionary
def _row_to_dict(row, lang):
    """
    Converts a room database row into a dictionary.

    Selects the appropriate language-specific direction hint.

    :param row: tuple, row returned from the rooms database query
    :param lang: str, "en" for English or "hun" for Hungarian
    :return: dict, normalized room data
    """
    direction_hint = row[4] if lang == "hun" else row[5]
    return {
        "room_number": row[0],
        "node_id": row[1],
        "name": row[2],
        "label": row[3],
        "direction_hint": direction_hint,
        "state": row[6],
    }


# INSTRUCTIONS:

# List main instructions from edges
def get_edge_instruction(from_node, to_node, c, lang):
    """
    Fetch the stored instruction text for a specific directed edge.

    If no instruction is stored for the selected language, the function
    returns None so the caller can fall back to a generic instruction.

    :param from_node: int, source node ID
    :param to_node: int, destination node ID
    :param c: active database cursor
    :param lang: language code ("en" or "hun")
    :return: str | None, instruction text if available, otherwise None
    """
    column = "instruction_en" if lang == "en" else "instruction_hun"
    c.execute(f"""
        SELECT {column}
        FROM edges
        WHERE from_node = ? AND to_node = ?
    """, (from_node, to_node))

    result = c.fetchone()
    return result[0] if result and result[0] else None

# Generate instructions
def generate_instructions(path, start_room, destination_room, db_path, lang="en"):
    """
    Generates human-readable navigation instructions for a node path.

    The output begins with a start message, includes edge-by-edge route
    instructions, and ends with an arrival message at the destination room.

    :param path: list, sequence of node IDs forming the route
    :param start_room: dict, starting room data
    :param destination_room: dict, destination room data
    :param db_path: str, path to SQLite database
    :param lang: str, language code ("en" or "hun")
    :return: list[str], ordered list of navigation instructions
    """
    with get_connection(db_path) as conn:
        c = conn.cursor()
        instructions = []

        # First instruction
        if lang == "en":
            instructions.append(f"Starting from {start_room['name']} (Room {start_room['room_number']}):")
        else:
            instructions.append(f"{start_room['name']} nevű ({start_room['room_number']} számú) helyiségtől indulva:")

        # Direction hint
        if start_room['direction_hint']:
            instructions.append(start_room['direction_hint'])

        # Step-by-step path instructions
        for i in range(len(path) - 1):
            from_node = path[i]
            to_node = path[i + 1]
            instruction = get_edge_instruction(from_node, to_node, c, lang)

            if instruction:
                instructions.append(instruction)
            else:
                if lang == "en": instructions.append(f"Go from node {from_node} to node {to_node}.")
                else: instructions.append(f"Menj {from_node} csúcstól {to_node} csúcshoz.")

        # Final instruction
        if lang == "en":
            instructions.append(f"You’ve arrived at the corridor with {destination_room['name']}"
                                f"(Room {destination_room['room_number']})")
        else:
            instructions.append(f"Megérkezett a {destination_room['name']} helyiség folyosójához "
                                f"(helyiség száma: {destination_room['room_number']})")
    return instructions



