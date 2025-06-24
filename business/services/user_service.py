import bcrypt

from business.services import log_service
from database import database as db_access


def add_new_user(username: str, plain_password: str, role: str, actor_username: str | None = None, actor_role: str = "System"):
    if db_access.get_user_password_hash(username):  # Check existence
        raise ValueError(f"User '{username}' already exists.")

    hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db_access.add_user(username, hashed_password, role, None)  # totp_secret is None initially
    log_service.record_event(f"Added user '{username}' with role '{role}' by {actor_username or actor_role}", actor_role)
    return f"Added user '{username}' with role '{role}'. 2FA setup required on first login."


def remove_user(username_to_delete: str, actor_username: str, actor_role: str):
    if username_to_delete == actor_username:
        raise ValueError("Cannot delete yourself.")

    db_access.delete_user(username_to_delete)
    log_service.record_event(f"Deleted user '{username_to_delete}' by {actor_username}", actor_role)
    return f"Deleted user '{username_to_delete}'."


def change_user_role(username_to_update: str, new_role: str, actor_username: str, actor_role: str):
    if not db_access.update_user_role(username_to_update, new_role):
        raise ValueError(f"User '{username_to_update}' not found.")

    log_service.record_event(f"Changed role of '{username_to_update}' to '{new_role}' by {actor_username}", actor_role)
    return f"Changed '{username_to_update}' role to '{new_role}'."


def list_all_users():
    return db_access.get_all_users()
