import bcrypt
import pyotp

from database import database as db_access


def establish_session_for_user(username: str):
    """Called after successful login and 2FA."""
    db_session_id = db_access.create_user_session(username)
    if db_session_id:
        print(f"DB session record created for {username} with ID: {db_session_id}")
    else:
        print(f"Failed to create DB session record for {username}")


def clear_session_for_user(username: str):
    """Called on logout."""
    db_access.delete_user_session_by_username(username)
    print(f"DB session records cleared for {username}")


def verify_user_credentials(username: str, plain_password: str) -> bool:
    password_hash = db_access.get_user_password_hash(username)
    if password_hash and bcrypt.checkpw(plain_password.encode('utf-8'), password_hash.encode('utf-8')):
        return True
    return False


def get_user_role(username: str) -> str | None:
    return db_access.fetch_user_role(username)


def get_totp_secret_for_user(username: str) -> str | None:
    return db_access.get_user_totp_secret(username)


def set_totp_secret_for_user(username: str, secret: str):
    db_access.set_user_totp_secret(username, secret)


def generate_new_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, username: str, issuer_name: str = "YourApp") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer_name)


def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)
