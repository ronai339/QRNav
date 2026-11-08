from tests.test_db_setup import setup_test_db
from app.services.graph import load_graph, find_path_by_nodes, compute_path_cost, get_node_for_room, get_edge_instruction, generate_instructions, resolve_room
from app.db.db import TEST_DB, get_connection

# T1
def test_load_graph(setup_test_db):
    """
    Verify that the graph can be loaded from the test database.
    """
    g = load_graph(TEST_DB)
    assert g is not None
    assert len(g.nodes) > 0
    assert len(g.edges) > 0

# T2
def test_find_path_by_nodes(setup_test_db):
    """
    Verify that the shortest path between two nodes is found correctly.
    """
    path, error = find_path_by_nodes(1, 3, TEST_DB)
    assert error is None
    assert path == [1, 2, 3]

# T3
def test_compute_path_cost(setup_test_db):
    """
    Verify that the weighted path cost is calculated correctly.
    """
    cost = compute_path_cost(1, 3, TEST_DB)
    assert cost == 5 # 2 + 3 from test DB

# T4
def test_get_node_for_room(setup_test_db):
    """
    Verify that a room number resolves to the correct node ID.
    """
    node_id = get_node_for_room("100", TEST_DB)
    assert node_id == 1

# T5
def test_get_edge_instructions(setup_test_db):
    """
    Verify that edge instructions are returned correctly for a given language.
    """
    with get_connection(TEST_DB) as conn:
        c = conn.cursor()
        instruction = get_edge_instruction(1, 2, c, "en")
        assert instruction == "Go up stairs"
        instruction = get_edge_instruction(2, 3, c, "en")
        assert instruction is None

# T6
def test_generate_instructions(setup_test_db):
    """
    Verify that full turn-by-turn instructions are generated for a path.
    """
    path = [1, 2, 3]
    start_room = {
        "room_number": "100",
        "name": "Office A",
        "direction_hint": "north"
    }
    destination_room = {
        "room_number": "200",
        "name": "Office B"
    }
    instructions = generate_instructions(path, start_room, destination_room, TEST_DB, "en")
    assert len(instructions) >= 2
    assert "Office A" in instructions[0]
    assert "north" in instructions[1]
    assert "Go up stairs" in instructions[2]
    assert "Go from node 2 to node 3." in instructions[3]
    assert "Office B" in instructions[-1]

# T7
def test_no_path(setup_test_db):
    """
    Verify that the navigation logic reports an error when no path exists.
    """
    path, error = find_path_by_nodes(1, 999, TEST_DB)
    assert path is None
    assert error is not None

# T8
def test_resolve_room():
    """
    Verify that room resolution returns the expected room data.
    """
    room = resolve_room("100", db_path=TEST_DB, lang="en")
    assert room["room_number"] == "100"
    assert room["node_id"] == 1
    assert room["name"] == "Office A"
    assert room["label"] == "lab"
    assert room["direction_hint"] == "north"
    assert room["state"] == "free"

# T9
def test_login_success(client):
    """
    Verify that a valid login redirects successfully.
    """
    response = client.post("/login", data={
        "username": "admin",
        "password": "adminpass"
    }, follow_redirects=True)
    assert response.status_code == 200

# T10
def test_login_required(client):
    """
    Verify that protected routes redirect unauthenticated users to login.
    """
    response = client.get("/admin_operator", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

# T11
def test_admin_access(client):
    """
    Verify that an admin session can access the admin area.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "admin"
    response = client.get("/admin_operator")
    assert response.status_code == 200

# T12
def test_operator_blocked_from_admin(client):
    """
    Verify that an operator cannot access admin-only pages.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["role"] = "operator"
    response = client.get("/admin_operator/create_user")
    assert response.status_code == 403

# T13
def test_operator_can_edit_assigned_node(client):
    """
    Verify that an operator may edit a node assigned to them.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["role"] = "operator"
    response = client.get("/admin_operator/nodes/edit/1")
    assert response.status_code == 200

# T14
def test_operator_cannot_edit_unassigned_node(client):
    """
    Verify that an operator cannot edit a node that is not assigned to them.
    """
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["role"] = "operator"
    response = client.get("/admin_operator/nodes/edit/2")
    assert response.status_code == 403