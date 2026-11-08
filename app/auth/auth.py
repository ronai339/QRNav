from flask import session
from app.db.db import get_connection, DB_PATH

# Get currently used language
def get_current_language():
    """
    Retrieves the currently selected language from the session.

    The application uses the returned value to select the active translation set.
    Defaults to English ("en") if no language is set.

    :return: str, language code ("en" or "hun")
    """
    return session.get("lang", "en")


# Get the id and role of the current user
def get_current_user():
    """
    Retrieves the currently logged-in user from the database.

    The user ID is taken from the session.
    If no user is logged in, the function returns None.

    :return: dict with user data (id, role, username) or None
    """
    user_id = session.get("user_id")
    if user_id is None:
        return None

    with get_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, role, username
            FROM users
            WHERE id = ?
            """, (user_id,)
        )
        row = c.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "role": row[1],
        "username": row[2]
    }