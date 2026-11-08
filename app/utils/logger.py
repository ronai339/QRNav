from app.db.db import DB_PATH, get_connection

def log_change(user, action_type, entity_type, entity_id, details=""):
    """
    Store a change event in the graph in the graph history database.

    This logger is used by the admin/operator interface to keep a
    simple audit trail of graph edits and account-related actions.

    :param user: str, user identifier or role string recorded in the log
    :param action_type: str, action name such as "add", "edit", or "delete"
    :param entity_type: str, type of affected object, for example "node" or "edge"
    :param entity_id: identifier of the affected object
    :param details: str, optional human-readable description of the change
    :return: None
    """
    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO graph_changes (user, action_type, entity_type, entity_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (str(user), action_type, entity_type, str(entity_id), details))
        conn.commit()