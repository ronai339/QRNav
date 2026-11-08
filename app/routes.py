import csv
from flask import make_response, Flask, session, render_template, request, redirect, url_for, abort
from werkzeug.security import check_password_hash, generate_password_hash
from io import StringIO, TextIOWrapper
from app.services.graph import generate_instructions, resolve_room, find_path_by_nodes, get_node_for_room
from app.auth.auth import get_current_language, get_current_user
from app.auth.permissions import can_edit_node, can_edit_edge, role_required, login_required
from app.utils.logger import log_change
from app.utils.translations import TRANSLATIONS
from app.utils.validation import validate_node_id, validate_positive_int
from app.db.db import DB_PATH, get_connection

app = Flask(__name__)

# Secret-key
app.secret_key = "_b<,+OH-H.+{1tCc"


# LANGUAGE SETTINGS:

# Set default language to English
@app.before_request
def set_default_language():
    """
    Ensure that a language preference exists for the current session.

    If the user has not chosen a language yet, English is stored as
    the default so that templates can render safely.

    :return: None
    """
    if "lang" not in session: session["lang"] = "en"

# Switch language
@app.route("/switch_language")
def switch_language():
    """
    Toggle the active session language between English and Hungarian.

    After switching, the user is redirected back to the previous page
    when possible, otherwise to the home page.

    :return: Flask response, redirect to the previous page or home page
    """
    current = session.get("lang", "en")
    if current == "en": session["lang"] = "hun"
    else: session["lang"] = "en"
    return redirect(request.referrer or url_for("home"))

# Inject translations
@app.context_processor
def inject_translations():
    """
    Inject the active translations dictionary into all templates.

    This allows Jinja templates to access translated labels through 't'.
    the selected language is read from the current session.

    :return: dict, template context containing the active translation mapping
    """
    lang = session.get("lang", "en")
    return dict(t=TRANSLATIONS[lang])


# LOGIN/OUT AND HOMEPAGES:

# Navigation homepage
@app.route("/", methods=["GET"])
def home():
    """
    Render the public navigation page and compute a route when requested.

    The function reads the starting and destination rooms from query parameters,
    resolves them into graph nodes, computes the path, and then generates
    step-by-step instructions for display.

    :return: Flask response, rendered homepage
    """
    from_query = request.args.get("from_room")
    to_query = request.args.get("to_room")
    instructions = []
    lang = get_current_language()
    error = None
    start_room = None
    destination_room = None

    if from_query and to_query:
        try:
            with get_connection(DB_PATH) as conn:

                # Resolve start room
                start_room = resolve_room(from_query, is_start=True, db_path=DB_PATH, lang=lang)
                start_node_id = start_room["node_id"]

                # Resolve destination room
                destination_room = resolve_room(to_query, is_start=False, start_node_id=start_node_id, db_path=DB_PATH, lang=lang)
                end_node_id = destination_room["node_id"]

            # Compute path
            path, error = find_path_by_nodes(start_node_id,end_node_id,DB_PATH)
            if path:
                instructions = generate_instructions(path,start_room,destination_room,DB_PATH,lang)

        except ValueError as e:
            error = str(e)
    return render_template("index.html",instructions=instructions,error=error,start_room=start_room,destination_room=destination_room)

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Authenticate a user and start a session.

    On successful login, the user's ID and role are stored in the
    session and the user is redirected to the admin/operator area.
    Invalid credentials return the login page with an error message.

    :return: Flask response, rendered login page or redirect
    """
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with get_connection(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, password_hash, role
                FROM users
                WHERE username = ?
            """, (username,))
            user = c.fetchone()

        if user and check_password_hash(user[1], password):
            session["admin_operator"] = True
            session["user_id"] = user[0]
            session["role"] = user[2]
            next_page = request.args.get("next")
            return redirect(next_page or "/admin_operator")
        else:
            error = "Invalid username or password"
    return render_template("login.html", error=error)

# Logout
@app.route("/logout")
def logout():
    """
    Clear the current session and return to the public home page.

    :return: Flask response, redirect to the home page
    """
    session.clear()
    return redirect(url_for("home"))

# Admin and operator homepage
@app.route("/admin_operator")
@login_required
def admin_operator_home():
    """
    Render the main dashboard for logged-in administrators and operators.

    The page shows the available management views according to the current user's role.

    :return: Flask response, rendered admin/operator dashboard
    """
    with get_connection(DB_PATH) as conn:
        user = get_current_user()
        return render_template("admin_operator/admin_operator_home.html", user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))


# EDGES:

# View list of edges
@app.route("/admin_operator/edges")
@login_required
def view_edges():
    """
    Render the edge management page.

    Admin users can see all edges, while operators only see the edges with both
    connected nodes assigned to them through the operator-node mapping table.

    :return: Flask response, rendered edge overview page
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        if user["role"] == "operator":
            accessible_nodes = set(row[0] for row in c.execute("""
                SELECT id
                FROM nodes 
                WHERE id IN (
                    SELECT node_id FROM operator_nodes
                    WHERE operator_id = ?)
            """, (user["id"],)))
        else:
            accessible_nodes = set(row[0] for row in c.execute("SELECT id FROM nodes"))

        c.execute("""
                SELECT e.id, e.from_node, e.to_node, e.cost, e.instruction_hun, e.instruction_en, e.open,
                       nf.name, nt.name
                FROM edges e
                JOIN nodes nf ON e.from_node = nf.id
                JOIN nodes nt ON e.to_node = nt.id
                ORDER BY e.id
            """)
        edges = c.fetchall()
        return render_template("admin_operator/view_edges.html", edges=edges, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"), accessible_nodes=accessible_nodes)

# Add a pair of new edges
@app.route("/admin_operator/edges/add", methods=["GET", "POST"])
@login_required
def add_edge_pair():
    """
    Add a new directed edge pair to the graph.

    The route accepts form input for both directions, checks edit permissions,
    validates the submitted node IDs, stores the new edges, and records the
    action in the change log.

    :return: Flask response, add-edge form or redirect after successful creation
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        if request.method == "POST":
            from_node = int(validate_node_id(request.form["from_node"]))
            to_node = int(validate_node_id(request.form["to_node"]))

            instruction_hun1 = request.form.get("instruction_hun1") or None
            instruction_en1 = request.form.get("instruction_en1") or None
            cost1 = float(request.form.get("cost1") or 1.0)
            open1 = 1 if request.form.get("open1") == "on" else 0

            instruction_hun2 = request.form.get("instruction_hun2") or None
            instruction_en2 = request.form.get("instruction_en2") or None
            cost2 = float(request.form.get("cost2") or 1.0)
            open2 = 1 if request.form.get("open2") == "on" else 0

            # Check permission
            if not can_edit_edge(user, from_node, to_node, conn):
                abort(403)

            c.execute("SELECT MAX(id) FROM edges")
            max_id = c.fetchone()[0] or 0
            next_id = max_id + 1

            c.execute("""
                INSERT INTO edges (id, from_node, to_node, cost, instruction_hun, instruction_en, open)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (next_id, from_node, to_node, cost1, instruction_hun1, instruction_en1, open1))
            c.execute("""
                INSERT INTO edges (id, from_node, to_node, cost, instruction_hun, instruction_en, open)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (next_id + 1, to_node, from_node, cost2, instruction_hun2, instruction_en2, open2))
            conn.commit()

            log_change(user["username"], "add", "edge", next_id,
                       f"Él hozzáadva {from_node} csúcstól {to_node} csúcsig. / Edge from {from_node} to {to_node} added.")
            log_change(user["username"], "add", "edge", next_id + 1,
                       f"Él hozzáadva {to_node} csúcstól {from_node} csúcsig. / Edge from {to_node} to {from_node} added.")

            return redirect("/admin_operator/edges")

        # List all nodes
        if user["role"] == "operator":
            c.execute("""
                SELECT id, name 
                FROM nodes 
                WHERE id IN (
                    SELECT node_id FROM operator_nodes
                    WHERE operator_id = ?)
                ORDER BY id
            """, (user["id"],))
        else:
            c.execute("SELECT id, name FROM nodes ORDER BY id")
        nodes = c.fetchall()

        return render_template("admin_operator/add_edge.html", nodes=nodes, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

# Edit an existing edge
@app.route("/admin_operator/edges/edit/<int:edge_id>", methods=["GET", "POST"])
@login_required
def edit_edge(edge_id):
    """
    Edit an existing edge after checking that the current user
    has permission to modify both connected nodes.

    The form updates the edge endpoints, cost, direction hints,
    and open/closed status.

    :param edge_id: int, identifier of the edge to edit
    :return: Flask response, rendered edit form or redirect back to the edge list
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        edge_id = validate_positive_int(edge_id)

        if request.method == "POST":
            from_node = int(validate_node_id(request.form["from_node"]))
            to_node = int(validate_node_id(request.form["to_node"]))
            cost = float(request.form.get("cost") or 1.0)
            instruction_hun = request.form.get("instruction_hun") or None
            instruction_en = request.form.get("instruction_en") or None
            open_status = 1 if request.form.get("open") == "on" else 0

            # Check permission
            if not can_edit_edge(user, from_node, to_node, conn):
                abort(403)

            c.execute("""
                UPDATE edges
                SET from_node = ?, to_node = ?, cost = ?, instruction_hun = ?, instruction_en = ?, open = ?
                WHERE id = ?
            """, (from_node, to_node, cost, instruction_hun, instruction_en, open_status, edge_id))
            conn.commit()
            log_change(user["username"], "edit", "edge", edge_id,
                       f"{edge_id} azonosítójú él módosítva. / Edge with id {edge_id} changed.")
            return redirect("/admin_operator/edges")

        c.execute("SELECT id, from_node, to_node, cost, instruction_hun, instruction_en, open FROM edges WHERE id = ?", (edge_id,))
        edge = c.fetchone()

        if user["role"] == "operator":
            c.execute("""
                SELECT id, name 
                FROM nodes 
                WHERE id IN (
                    SELECT node_id FROM operator_nodes
                    WHERE operator_id = ?)
                ORDER BY id
            """, (user["id"],))
        else:
            c.execute("SELECT id, name FROM nodes ORDER BY id")
        nodes = c.fetchall()

        return render_template("admin_operator/edit_edge.html", edge=edge, nodes=nodes, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

# Delete an existing edge
@app.route("/admin_operator/edges/delete/<int:edge_id>")
@login_required
def delete_edge(edge_id):
    """
    Delete an edge from the graph after verifying edit permission.

    The function first loads the edge, checks whether the current user is allowed
    to edit the connected nodes, and then removes the edge from the database.

    :param edge_id: int, identifier of the edge to delete
    :return: Flask response, redirect to the edge list
    """
    user = get_current_user()
    edge_id = validate_positive_int(edge_id)

    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT from_node, to_node FROM edges WHERE id = ?", (edge_id,))
        row = c.fetchone()

        # Check permission
        if row is None:
            abort(404)
        from_node, to_node = row
        if not can_edit_edge(user, from_node, to_node, conn):
            abort(403)

        c.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
        conn.commit()
        log_change(user["username"], "delete", "edge", edge_id,
                   f"{edge_id} azonosítójú él törölve. / Edge with id {edge_id} deleted.")
        return redirect("/admin_operator/edges")

# Export all edges to an edges.csv file
@app.route("/admin_operator/export/edges")
@login_required
def export_edges():
    """
    Export all edges as a CSV file download.

    The exported file contains the complete edge table, including
    endpoints, cost, instructions, and the open/closed state.

    :return: Flask response, CSV file download
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, from_node, to_node, cost, instruction_hun, instruction_en, open FROM edges")
        user = get_current_user()
        rows = c.fetchall()

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "from_node", "to_node", "cost", "instruction_hun", "instruction_en", "open"])
        writer.writerows(rows)

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=edges.csv"
        response.headers["Content-type"] = "text/csv"

        log_change(user["username"], "export", "edge", None,
                   f"Élek exportálva CSV fájlként. / Edges exported as CSV file.")

        return response

# Import edges from a file
@app.route("/admin_operator/import/edges", methods=["POST"])
@login_required
def import_edges():
    """
    Import edge data from an uploaded CSV file.

    The function reads the file row by row, validates the input,
    and inserts or updates edges in the database.

    :return: Flask response, redirect to the edge list or an error response
    """
    file = request.files["file"]

    if not file:
        return "No file uploaded", 400

    # Decode file content
    csvfile = TextIOWrapper(file, encoding='utf-8')
    reader = csv.DictReader(csvfile)

    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        for row in reader:
            if not row.get("id") or not row.get("from_node") or not row.get("to_node"):
                continue  # Skip invalid row
            edge_id = int(row["id"])
            from_node = int(row["from_node"])
            to_node = int(row["to_node"])
            cost = float(row["cost"]) if row.get("cost") else 0
            instruction_hun = row["instruction_hun"].strip() if row.get("instruction_hun") else None
            instruction_en = row["instruction_en"].strip() if row.get("instruction_en") else None
            edge_open = 1 if str(row["open"]).strip() in ["1", "true", "True"] else 0
            c.execute("""
                        INSERT INTO edges (id, from_node, to_node, cost, instruction_hun, instruction_en, open)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            id = excluded.id,
                            from_node = excluded.from_node,
                            to_node = excluded.to_node,
                            cost = excluded.cost,
                            instruction_hun = excluded.instruction_hun,
                            instruction_en = excluded.instruction_en,
                            open = excluded.open
                    """, (edge_id, from_node, to_node, cost, instruction_hun, instruction_en, edge_open))
        conn.commit()

        log_change(user["username"], "import", "edge", None,
                   f"Élek importálva CSV fájlból. / Edges imported from CSV file.")
        return redirect("/admin_operator/edges")

# Open/Close an edge using toggle
@app.route("/admin_operator/edges/toggle/<int:edge_id>", methods=["POST"])
@login_required
def toggle_edge_open(edge_id):
    """
    Toggle the open/closed state of an edge.

    This route is used by the admin/operator interface to quickly
    enable or disable a connection in the navigation graph.

    :param edge_id: int, identifier of the edge to toggle
    :return: Flask response, redirect to the edge list
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT open FROM edges WHERE id = ?", (edge_id,))
        user = get_current_user()
        current_status = c.fetchone()

        if current_status is not None:
            if current_status[0] == 1:
                new_status = 0
                log_open ="closed"
            else:
                new_status = 1
                log_open = "open"
            c.execute("UPDATE edges SET open = ? WHERE id = ?", (new_status, edge_id))
            conn.commit()
            log_change(user["username"], "edit", "edge", edge_id, f"Él / Edge: {log_open}")

        return redirect("/admin_operator/edges")


# NODES:

# View list of nodes
@app.route("/admin_operator/nodes")
@login_required
def view_nodes():
    """
    Render the node overview page.

    Admin users can see all nodes, while operators only see the
    nodes assigned to them through the operator-node mapping table.

    :return: Flask response, rendered node list page
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        if user["role"] == "operator":
            accessible_nodes = set(row[0] for row in c.execute("""
                SELECT id
                FROM nodes 
                WHERE id IN (
                    SELECT node_id FROM operator_nodes
                    WHERE operator_id = ?)
            """, (user["id"],)))
        elif user["role"] == "admin":
            accessible_nodes = set(row[0] for row in c.execute("SELECT id FROM nodes"))

        c.execute("""
            SELECT id, name, type, floor, wing, label 
            FROM nodes 
            ORDER BY id
        """)
        nodes = c.fetchall()
        return render_template("admin_operator/view_nodes.html", nodes=nodes, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"), accessible_nodes=accessible_nodes)

# Add a new node
@app.route("/admin_operator/nodes/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_node():
    """
    Create a new node in the graph.

    The form stores the node name, type, floor, wing,
    optional labels, and language-specific instructions.

    :return: Flask response, rendered add-node form or redirect back to the node list
    """
    user = get_current_user()

    if request.method == "POST":
        name = request.form["name"]
        type_ = request.form["type"]
        floor = int(request.form["floor"])
        wing = request.form["wing"]
        label = request.form.get("label") or None

        # Check permission
        if user["role"] != "admin":
            abort(403)

        with get_connection(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO nodes (name, type, floor, wing, label)
                VALUES (?, ?, ?, ?, ?)
            """, (name, type_, floor, wing, label))
            conn.commit()
            log_change(user["username"], "add", "node", name,
                       f"{name} nevű csúcs hozzáadva. / Node with name {name} added.")
            return redirect("/admin_operator/nodes")

    return render_template("admin_operator/add_node.html", user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))


# Edit an existing node
@app.route("/admin_operator/nodes/edit/<int:node_id>", methods=["GET", "POST"])
@login_required
def edit_node(node_id):
    """
    Edit an existing node after checking edit permission.

    Admin users may edit every node,
    while operators may only edit nodes assigned to them.

    :param node_id: int, identifier of the node to edit
    :return: Flask response, rendered edit form or redirect back to the node list
    """

    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        node_id = validate_positive_int(node_id)

        # Check permission
        if not can_edit_node(user, node_id, conn):
            abort(403)

        if request.method == "POST":
            name = request.form["name"]
            type_ = request.form["type"]
            floor = int(request.form["floor"])
            wing = request.form["wing"]
            label = request.form.get("label") or None

            c.execute("""
                UPDATE nodes
                SET name = ?, type = ?, floor = ?, wing = ?, label = ?
                WHERE id = ?
            """, (name, type_, floor, wing, label, node_id))
            conn.commit()
            log_change(user["username"], "edit", "node", node_id,
                       f"{node_id} azonosítójú csúcs módosítva. / Node with id {node_id} changed.")
            return redirect("/admin_operator/nodes")

        if user["role"] == "operator":
            c.execute("""
                    SELECT id, name, type, floor, wing, label
                    FROM nodes
                    WHERE id = ?
                      AND id IN (
                          SELECT node_id
                          FROM operator_nodes
                          WHERE operator_id = ?
                      )
                """, (node_id, user["id"]))
        else:
            c.execute("""
                    SELECT id, name, type, floor, wing, label 
                    FROM nodes 
                    WHERE id = ?
                """, (node_id,))
        node = c.fetchone()

        if node is None:
            abort(403)

        return render_template("admin_operator/edit_node.html", node=node, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

# Delete an existing node and the connecting edges
@app.route("/admin_operator/nodes/delete/<int:node_id>")
@login_required
def delete_node(node_id):
    """
    Delete a node and its connected edges after validating that it is safe to remove.

    The function blocks deletion when the node is still referenced by a room.

    :param node_id: int, identifier of the node to delete
    :return: Flask response, redirect to the node list or an error response
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        node_id = validate_positive_int(node_id)

        # Check permission
        user = get_current_user()
        if node_id is None:
            return "Node not found", 404
        if not can_edit_node(user, node_id, conn):
            abort(403)

        # Check if any rooms are using this node
        c.execute("SELECT COUNT(*) FROM rooms WHERE node_id = ?", (node_id,))
        room_count = c.fetchone()[0]
        if room_count > 0:
            return f"❌ Cannot delete node {node_id}: {room_count} room(s) still use this node. Go back and reassign or delete those first."

        # Delete edges where this node is from/to
        c.execute("DELETE FROM edges WHERE from_node = ? OR to_node = ?", (node_id, node_id))


        # Delete the node itself
        c.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        conn.commit()

        log_change(user["username"], "delete", "edge", node_id,
                   f"{node_id} azonosítójú csúcshoz kapcsolódó élek törölve. / Edges connected to node with id {node_id} deleted.")
        log_change(user["username"], "delete", "node", node_id,
                   f"{node_id} azonosítójú csúcs törölve. / Node with id {node_id} deleted.")
        return redirect("/admin_operator/nodes")

# Export all nodes to a nodes.csv file
@app.route("/admin_operator/export/nodes")
@login_required
def export_nodes():
    """
    Export all nodes as a CSV file download.

    The exported file contains the full node table with all stored metadata.

    :return: Flask response, CSV file download
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        c.execute("SELECT id, name, type, floor, wing, label FROM nodes")
        rows = c.fetchall()

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "type", "floor", "wing", "label"])
        writer.writerows(rows)

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=nodes.csv"
        response.headers["Content-type"] = "text/csv"

        log_change(user["username"], "export", "node", None,
                   f"Csúcsok exportálva CSV fájlként. / Nodes exported as CSV file.")

        return response

# Import nodes from a file
@app.route("/admin_operator/import/nodes", methods=["POST"])
@login_required
def import_nodes():
    """
    Import all node data from an uploaded CSV file.

    Existing rows are updated when the imported CSV contains a matching node
    identifier.

    :return: Flask response, redirect to the node list or an error response
    """
    file = request.files["file"]

    if not file:
        return "No file uploaded", 400

    csvfile = TextIOWrapper(file, encoding='utf-8')
    reader = csv.DictReader(csvfile)

    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        for row in reader:
            if not row.get("id") or not row.get("type"):
                continue  # Skip invalid row
            node_id = int(row["id"])
            name = row["name"].strip() if row.get("name") else None
            node_type = row["type"].strip()
            floor = int(row["floor"]) if row.get("floor") else None
            wing = row["wing"].strip() if row.get("wing") else None
            label = row["label"].strip() if row.get("label") else None

            c.execute("""
                INSERT INTO nodes (id, name, type, floor, wing, label)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    id = excluded.id,
                    name = excluded.name,
                    type = excluded.type,
                    floor = excluded.floor,
                    wing = excluded.wing,
                    label = excluded.label
            """, (node_id, name, node_type, floor, wing, label))
        conn.commit()
        log_change(user["username"], "import", "node", None,
                   f"Csúcsok importálva CSV fájlból. / Nodes imported from CSV file.")

        return redirect("/admin_operator/nodes")


# ROOMS:

# View list of rooms
@app.route("/admin_operator/rooms")
@login_required
def view_rooms():
    """
    Render the room overview page.

    The page joins rooms with their assigned nodes and
    shows only the rooms that the current user is allowed to inspect.

    :return: Flask response, rendered room list page
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        if user["role"] == "operator":
            accessible_nodes = set(row[0] for row in c.execute("""
                    SELECT id
                    FROM nodes 
                    WHERE id IN (
                        SELECT node_id FROM operator_nodes
                        WHERE operator_id = ?)
                """, (user["id"],)))
        else:
            accessible_nodes = set(row[0] for row in c.execute("SELECT id FROM nodes"))

        c.execute("""
                SELECT r.room_number, r.node_id, r.name, r.label, r.direction_hint_hun, r.direction_hint_en, r.state, n.name
                FROM rooms r
                LEFT JOIN nodes n ON r.node_id = n.id
                ORDER BY r.room_number
            """)
        rooms = c.fetchall()
        return render_template("admin_operator/view_rooms.html", rooms=rooms, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"), accessible_nodes=accessible_nodes)

# Add a new room
@app.route("/admin_operator/rooms/add", methods=["GET", "POST"])
@login_required
def add_room():
    """
    Create a new room and assign it to a node.

    The function validates the room number and node identifier, then stores
    the room together with optional direction hints and status information.

    :return: Flask response, rendered add-room form or redirect back to the room list
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        if request.method == "POST":
            room_number = validate_positive_int(request.form["room_number"])
            node_id = int(validate_node_id(request.form["node_id"]))
            name = request.form["name"]
            label = request.form.get("label", None)
            direction_hint_hun = request.form.get("direction_hint_hun", None)
            direction_hint_en = request.form.get("direction_hint_en", None)
            state = request.form["state"]

            # Check permission
            if not can_edit_node(user, node_id, conn):
                abort(403)

            c.execute("""
                INSERT INTO rooms (room_number, node_id, name, label, direction_hint_hun, direction_hint_en, state)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (room_number, node_id, name, label, direction_hint_hun, direction_hint_en, state))
            conn.commit()

            log_change(user["username"], "add", "room", room_number,
                       f"{room_number} számú helyiség hozzáadva. / Room with room number {room_number} added.")
            return redirect("/admin_operator/rooms")

        if user["role"] == "operator":
            c.execute("""
                SELECT id, name 
                FROM nodes 
                WHERE id IN (
                    SELECT node_id FROM operator_nodes
                    WHERE operator_id = ?)
                ORDER BY id
            """, (user["id"],))
        else:
            c.execute("SELECT id, name FROM nodes ORDER BY id")
        nodes = c.fetchall()

        return render_template("admin_operator/add_room.html", nodes=nodes, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

# Edit an existing room
@app.route("/admin_operator/rooms/edit/<room_number>", methods=["GET", "POST"])
@login_required
def edit_room(room_number):
    """
    Edit an existing room after validating the room number and permission.

    The room can be updated only if the current user is allowed to
    edit the underlying node assigned to the room.

    :param room_number: str or int, room number to edit
    :return: Flask response, rendered edit form or redirect back to the room list
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        room_number = validate_positive_int(room_number)

        if request.method == "POST":
            name = request.form["name"]
            label = request.form.get("label", None)
            direction_hint_hun = request.form.get("direction_hint_hun", None)
            direction_hint_en = request.form.get("direction_hint_en", None)
            state = request.form["state"]

            # Check permission
            node_id = get_node_for_room(room_number, DB_PATH)
            if node_id is None:
                return "Node not found", 404
            if not can_edit_node(user, node_id, conn):
                abort(403)

            c.execute("""
                UPDATE rooms
                SET name = ?, label = ?, direction_hint_hun = ?, direction_hint_en = ?, state = ?
                WHERE room_number = ?
            """, (name, label, direction_hint_hun, direction_hint_en, state, room_number))
            conn.commit()
            log_change(user["username"], "edit", "room", room_number,
                       f"{room_number} számú helyiség módosítva. / Room with number {room_number} changed.")
            return redirect("/admin_operator/rooms")

        if user["role"] == "operator":
            c.execute("""
                SELECT room_number, name, label, direction_hint_hun, direction_hint_en, state 
                FROM rooms 
                WHERE node_id IN (
                    SELECT node_id FROM operator_nodes
                    WHERE operator_id = ?)
                ORDER BY node_id
            """, (user["id"],))
        else:
            c.execute("SELECT room_number, name, label, direction_hint_hun, direction_hint_en, state FROM rooms WHERE room_number = ?", (room_number,))
        room = c.fetchone()

        return render_template("admin_operator/edit_room.html", room=room, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

# Delete an existing room
@app.route("/admin_operator/rooms/delete/<room_number>")
@login_required
def delete_room(room_number):
    """
    Delete a room after verifying that the current user is allowed to edit its node.

    :param room_number: str or int, room number to delete
    :return: Flask response, redirect to the room list or an error response
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        room_number = validate_positive_int(room_number)
        node_id = get_node_for_room(room_number, DB_PATH)

        # Check permission
        user = get_current_user()
        if node_id is None:
            return "Node not found", 404
        if not can_edit_node(user, node_id, conn):
            abort(403)

        c.execute("DELETE FROM rooms WHERE room_number = ?", (room_number,))
        conn.commit()
        log_change(user["username"], "delete", "room", room_number,
                   f"{room_number} számú helyiség törölve. / Room with room number {room_number} deleted.")
        return redirect("/admin_operator/rooms")

# Export all rooms to a rooms.csv file
@app.route("/admin_operator/export/rooms")
@login_required
def export_rooms():
    """
    Export all rooms as a CSV file download.

    The exported file includes room metadata,
    node assignments, direction hints, and room state.

    :return: Flask response, CSV file download
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        c.execute("SELECT room_number, node_id, name, label, direction_hint_hun, direction_hint_en, state FROM rooms")
        rows = c.fetchall()

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["room_number", "node_id", "name", "label", "direction_hint_hun", "direction_hint_en", "state"])
        writer.writerows(rows)

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=rooms.csv"
        response.headers["Content-type"] = "text/csv"

        log_change(user["username"], "export", "room", None,
                   f"Helyiségek exportálva CSV fájlként. / Rooms exported as CSV file.")

        return response

# Import rooms from a file
@app.route("/admin_operator/import/rooms", methods=["POST"])
@login_required
def import_rooms():
    """
    Import room data from an uploaded CSV file.

    The function reads the file row by row and updates
    existing rooms when the room number already exists.

    :return: Flask response, redirect to the room list or an error response
    """
    file = request.files["file"]

    if not file:
        return "No file uploaded", 400

    csvfile = TextIOWrapper(file, encoding='utf-8')
    reader = csv.DictReader(csvfile)

    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()

        for row in reader:
            if not row.get("room_number") or not row.get("node_id"):
                continue  # Skip invalid row
            room_number = row["room_number"].strip()
            node_id = int(row["node_id"])
            name = row["name"].strip() if row.get("name") else None
            label = row["label"].strip() if row.get("label") else None
            direction_hint_hun = row["direction_hint_hun"].strip() if row.get("direction_hint_hun") else None
            direction_hint_en = row["direction_hint_en"].strip() if row.get("direction_hint_en") else None
            state = row["state"].strip()

            c.execute("""
                INSERT INTO rooms (room_number, node_id, name, label, direction_hint_hun, direction_hint_en, state)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(room_number) DO UPDATE SET
                    node_id = excluded.node_id,
                    name = excluded.name,
                    label = excluded.label,
                    direction_hint_hun = excluded.direction_hint_hun,
                    direction_hint_en = excluded.direction_hint_en,
                    state = excluded.state
            """, (room_number, node_id, name, label, direction_hint_hun, direction_hint_en, state))
        conn.commit()
        log_change(user["username"], "import", "room", None,
                   f"Helyiségek importálva CSV fájlból. / Rooms imported from CSV file.")

        return redirect("/admin_operator/rooms")

# Let users view the rooms
@app.route("/rooms")
def public_rooms():
    """
    Render the public room list.

    The view joins rooms with their corresponding nodes and displays the
    resulting room overview without requiring authentication.

    :return: Flask response, rendered room list page
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT r.room_number, r.node_id, r.name, r.label, r.direction_hint_hun, r.direction_hint_en, r.state, n.name
            FROM rooms r
            LEFT JOIN nodes n ON r.node_id = n.id
            ORDER BY r.room_number
        """)
        rooms = c.fetchall()
        return render_template("admin_operator/view_rooms.html", rooms=rooms, is_public=True)


# ACCOUNT MANAGEMENT:

# Assign nodes to operators
@app.route("/admin_operator/node_assignments", methods=["GET", "POST"])
@login_required
@role_required("admin")
def node_assignments():
    """
    Display and update operator-to-node assignments.

    Admin users can assign nodes to operators through this page.
    Submitted assignments replace the previous mapping in the database.

    :return: Flask response, assignment editor or redirect after update
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()

        if request.method == "POST":
            # Clear old assignments
            c.execute("DELETE FROM operator_nodes")

            # Iterate submitted assignments
            for key, value in request.form.items():
                if key.startswith("node") and value != "":
                    node_id = int(key.split("_")[1])
                    operator_id = int(value)

                    c.execute("""
                        INSERT INTO operator_nodes (operator_id, node_id)
                        VALUES (?, ?)
                    """, (operator_id, node_id))
            conn.commit()

        # Load nodes
        c.execute("SELECT id, name FROM nodes ORDER BY id")
        nodes = c.fetchall()

        # Load operators
        c.execute("""
            SELECT id, username
            FROM users
            WHERE role='operator'
        """)
        operators = c.fetchall()

        # Load current assignments
        c.execute("""
                SELECT operator_id, node_id
                FROM operator_nodes
            """)
        assignments = {
            node_id: operator_id
            for operator_id, node_id in c.fetchall()
        }

        return render_template("admin_operator/node_assignments.html", nodes=nodes, operators=operators, assignments=assignments)

# Create a new operator account
@app.route("/admin_operator/create_user", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_user():
    """
    Create a new operator account.

    Only admins may access this route.
    The password is hashed before storage, and duplicate usernames are rejected.

    :return: Flask response, user creation form or redirect after success
    """
    error = None

    if request.method == ("POST"):
        username = request.form["username"].strip()
        raw_password = request.form["password"].strip()

        if not username or not raw_password:
            error = "Username and password required! / Felhasználónév és jelszó megadása szükséges!"
            return render_template("admin_operator/create_user.html", error=error)

        with get_connection(DB_PATH) as conn:
            c = conn.cursor()

            # Check if username already exists
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            if c.fetchone():
                error = "Username already exists. / Megadott felhasználónév már létezik."
                return render_template("admin_operator/create_user.html", error=error)

            password_hash = generate_password_hash(raw_password)
            c.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, 'operator')
            """, (username, password_hash))
            conn.commit()
            return redirect("/admin_operator")

    return render_template("admin_operator/create_user.html")

# Change password
@app.route("/admin_operator/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """
    Allow a logged-in user to change their password.

    The current password is verified before the new one is accepted.
    The new password is stored as a hash, and basic length validation is applied.

    :return: Flask response, password-change form or success response
    """
    error = None
    success = None
    user = get_current_user()

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        if not current_password or not new_password:
            error = "All fields are required! / Minden mező kitöltése szükséges!"
            return render_template("admin_operator/change_password.html", error=error)

        with get_connection(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT password_hash FROM users WHERE id = ?", (session["user_id"],))
            db_user = c.fetchone()

            if not db_user or not check_password_hash(db_user[0], current_password):
                error = "Current password is incorrect! / Jelenlegi jelszó helytelen!"
                return render_template("admin_operator/change_password.html", error=error)

            if len(new_password) < 6:
                error = "Password must be at least 6 characters long! / A jelszó legalább 6 karakter hosszú kell legyen!"
                return render_template("admin_operator/change_password.html", error=error)

            new_hash = generate_password_hash(new_password)
            c.execute("""
                UPDATE users SET password_hash = ?
                WHERE id = ?
            """, (new_hash, session["user_id"]))
            conn.commit()
            success = "Password successfully changed! / Jelszóváltoztatás sikeres!"
            return render_template("admin_operator/change_password.html", success=success, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

    return render_template("admin_operator/change_password.html", user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))


# OTHER:

# View graph history
@app.route("/admin_operator/history")
@login_required
def view_graph_history():
    """
    Display the graph change log.

    The page shows the audit history stored in the separate change-log
    database, including timestamps, users, action types, and details.

    :return: Flask response, rendered history page
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        c.execute("""
            SELECT id, timestamp, user, action_type, entity_type, entity_id, details
            FROM graph_changes
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        changes = c.fetchall()
        return render_template("admin_operator/graph_history.html", changes=changes, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))

# Graph visualizer
@app.route("/admin_operator/graph/interactive")
@login_required
def interactive_graph():
    """
    Render the interactive graph visualization page.

    The view can optionally filter the displayed graph by floor and is used
    mainly for administration and debugging during graph maintenance.

    :return: Flask response, rendered interactive graph page
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        user = get_current_user()
        floor = request.args.get("floor")

        if floor:
            c.execute("SELECT id, name, type FROM nodes WHERE floor = ?", (floor,))
        else:
            c.execute("SELECT id, name, type FROM nodes")

        nodes = c.fetchall()
        node_ids = [n[0] for n in nodes]
        placeholders = ",".join(["?"] * len(node_ids))

        c.execute(f"""
            SELECT id, from_node, to_node, instruction_en, open
            FROM edges
            WHERE from_node IN ({placeholders}) AND to_node IN ({placeholders})
        """, node_ids * 2)
        edges = c.fetchall()

        # Package data for JS
        node_elements = [{
            "data": {
                "id": str(nid),
                "label": name,
                "type": typ
            }
        } for nid, name, typ in nodes]

        edge_elements = [{
            "data": {
                "id": f"e{eid}",
                "source": str(f),
                "target": str(t),
                "label": instruction or "",
                "open": open_
            }
        } for eid, f, t, instruction, open_ in edges]
        graph_data = node_elements + edge_elements

        return render_template("admin_operator/graph_interactive.html", graph_data=graph_data, floor=floor, user=user, is_admin=(user["role"]=="admin"), is_operator=(user["role"]=="operator"))