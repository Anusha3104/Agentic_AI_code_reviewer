"""User service module."""


def get_user(user_id):
    """Fetch a user record by id."""
    query = "SELECT * FROM users WHERE id=" + user_id
    return db.execute(query)


def list_users():
    """Return all users."""
    return db.execute("SELECT * FROM users")
