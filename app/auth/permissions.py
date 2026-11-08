from functools import wraps
from flask import session, abort, redirect, url_for, request

# Login required (admin or operator)
def login_required(view):
    """
    Decorator that ensures only authenticated users reach a given view.

    Redirects to the login page if no user session is found.
    The original target URL is preserved in the 'next' parameter.

    :param view: Flask view function
    :return: wrapped function
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return view(*args, **kwargs)
    return wrapper

# Checking role
def role_required(role):
    """
    Decorator that restricts access based on user role.

    Authentication is checked first. If the user is not logged in,
    the request is redirected to the login page. If the logged-in user's role
    does not match the required role, the request is rejected with HTTP 403.

    :param role: str, required role ("admin" or "operator")
    :return: decorator
    """
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login", next=request.url))
            if session.get("role") != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator

# Check if operator has access to node
def operator_has_node_access(user_id, node_id, conn):
    """
    Checks whether an operator has access to a specific node.

    This helper looks up the 'operator_nodes' table and is used by
    the edit-permission helpers to decide whether an operator
    should be allowed to modify a node or an edge connected to it.

    :param user_id: int, operator's user ID
    :param node_id: int, node ID
    :param conn: active database connection
    :return: bool indicating permission
    """
    with conn as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 1
            FROM operator_nodes
            WHERE operator_id = ? AND node_id = ?
        """, (user_id, node_id))
        return c.fetchone() is not None

# Node-editing permission for operators
def can_edit_node(user, node_id, conn):
    """
    Determines whether a user is allowed to edit a given node.

    Admin users can edit all nodes.
    Operator users can only edit nodes assigned to them.

    :param user: dict containing user id and role
    :param node_id: int, node ID
    :param conn: active database connection
    :return: bool indicating permission
    """
    if user["role"] == "admin":
        return True
    if user["role"] == "operator":
        return operator_has_node_access(user["id"], node_id, conn)
    return False

# Edge-editing permission for operators
def can_edit_edge(user, from_node, to_node, conn):
    """
    Determines whether a user is allowed to edit a given edge.

    Admin users can edit all edges.
    Operator users can only edit edges if they have access to both connected nodes.

    :param user: dict containing user id and role
    :param from_node: int, source node ID
    :param to_node: int, destination node ID
    :param conn: active database connection
    :return: bool indicating permission
    """
    if user["role"] == "admin":
        return True
    if user["role"] == "operator":
        return (
            operator_has_node_access(user["id"], from_node, conn)
            and operator_has_node_access(user["id"], to_node, conn))
    return False