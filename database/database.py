import bcrypt
import psycopg2
import uuid

from datetime import datetime, timezone, timedelta, date as py_date
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL, SCHEMA_PATH

SESSION_DURATION_HOURS = 4


def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    register_vector(conn)
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
        # Execute statements one by one if necessary, or ensure script is idempotent
        cur.execute(schema_sql)

        # Default roles (example, ensure these are created by schema.sql or here)
        default_roles = ['Security Personnel', 'Security Manager', 'Administrator']
        for role_name in default_roles:
            cur.execute("INSERT INTO roles (role_name) VALUES (%s) ON CONFLICT (role_name) DO NOTHING", (role_name,))

        # Initialize default users with hashed passwords
        default_users = [
            ("guard1", "12345", "Security Personnel"),
            ("manager1", "abcde", "Security Manager"),
            ("admin", "adminpass", "Administrator"),
        ]

        for username, password, role_name in default_users:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute("SELECT username FROM users WHERE username = %s", (username,))
            if not cur.fetchone():
                try:
                    cur.execute(
                        "INSERT INTO users (username, password_hash, role_name) VALUES (%s, %s, %s)",
                        (username, hashed_password, role_name)
                    )
                    print(f"Initialized user: {username} with role: {role_name}")
                except Exception as e:
                    print(f"Error initializing user {username}: {e}")
                    conn.rollback()
                    raise e
    conn.commit()
    conn.close()


def create_user_session(username: str) -> str:
    conn = get_conn()
    cur = conn.cursor()
    # Generate a unique session ID (if not using an extension that provides one)
    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(hours=SESSION_DURATION_HOURS)

    try:
        # Clean up any old sessions for this user first (optional, but good practice)
        cur.execute(
            """
            DELETE
            FROM user_sessions
            WHERE username = %s
            """, (username,)
        )
        # Insert new session
        cur.execute(
            """
            INSERT INTO user_sessions (session_id, username, created_at, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (session_id, username, created_at, expires_at)
        )
        conn.commit()
        print(f"Created session {session_id} for user {username}")
        return session_id
    except Exception as e:
        print(f"Error creating user session for {username}: {e}")
        conn.rollback()
        return None  # Indicate failure
    finally:
        conn.close()


def delete_user_session_by_username(username: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE
            FROM user_sessions
            WHERE username = %s
            """, (username,)
        )
        conn.commit()
        print(f"Deleted sessions for user {username}")
    except Exception as e:
        print(f"Error deleting user sessions for {username}: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_active_user_session(username: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT session_id, expires_at
            FROM user_sessions
            WHERE username = %s
              AND expires_at > %s
            ORDER BY created_at DESC
            LIMIT 1
            """, (username, datetime.now(timezone.utc))
        )
        session_record = cur.fetchone()
        return session_record  # Returns dict or None
    finally:
        conn.close()


def log_event(event: str, role: str, logged_student_id: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO logs (timestamp, event, role, logged_student_id)
        VALUES (%s, %s, %s, %s)
        """,
        (datetime.now(timezone.utc), event, role, logged_student_id)
    )
    conn.commit()
    conn.close()


def fetch_logs(limit=None):
    conn = get_conn()
    cur = conn.cursor()
    if limit is None:
        cur.execute("""SELECT id, timestamp, event, role, logged_student_id
                       FROM logs
                       ORDER BY id DESC""")
    else:
        cur.execute("""SELECT id, timestamp, event, role, logged_student_id
                       FROM logs
                       ORDER BY id DESC
                       LIMIT %s""", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_totp_secret(username: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT totp_secret
                   FROM users
                   WHERE username = %s""", (username,))
    result = cur.fetchone()
    conn.close()
    return result['totp_secret'] if result else None


def set_user_totp_secret(username: str, secret: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""UPDATE users
                   SET totp_secret = %s
                   WHERE username = %s""", (secret, username))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT username, role_name
                   FROM users""")
    users = cur.fetchall()
    conn.close()
    return users


def delete_user(username: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""DELETE
                   FROM users
                   WHERE username = %s""", (username,))
    conn.commit()
    conn.close()


def update_user_role(username: str, new_role: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""UPDATE users
                   SET role_name = %s
                   WHERE username = %s""", (new_role, username))
    conn.commit()
    rows_affected = cur.rowcount
    conn.close()
    return rows_affected > 0


def fetch_user_role(username: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role_name FROM users WHERE username = %s", (username,))
    result = cur.fetchone()
    conn.close()
    return result['role_name'] if result else None


def add_student(student_id: str, first_name: str, middle_name: str, last_name: str, gender: str, nationality: str, department: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO student (student_id, first_name, middle_name, last_name, gender, nationality, department)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (student_id, first_name, middle_name, last_name, gender, nationality, department)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def record_student_registration(student_id: str, admin_username: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO student_registration (student_id, registered_by, registered_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (student_id) DO UPDATE SET
                registered_by = EXCLUDED.registered_by,
                registered_at = EXCLUDED.registered_at; 
            """,
            # Using now() for registered_at. EXCLUDED updates if student_id already exists.
            (student_id, admin_username, datetime.now(timezone.utc))
        )
        conn.commit()
        print(f"Recorded registration for student {student_id} by admin {admin_username}")
    except Exception as e:
        print(f"Error recording student registration for {student_id}: {e}")
        conn.rollback()
    finally:
        conn.close()


def store_student_embedding(student_id: str, view_angle: str, embedding: list[float], sample_index: int):
    """
    Stores a student's image embedding in the database.
    Args:
        student_id: The ID of the student.
        view_angle: The view angle of the image (e.g., 'front', 'left45').
        embedding: A list of 512 floats representing the embedding vector.
        sample_index: The index of the sample for this view angle (1 to 8, or 1 for mean).
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO student_embeddings (student_id, view_angle, student_embedding, sample_index)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (student_id, view_angle, sample_index) DO UPDATE
                SET student_embedding = EXCLUDED.student_embedding
            """,
            (student_id, view_angle, embedding, sample_index)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error storing embedding for {student_id}/{view_angle}/sample_{sample_index}: {e}")
        raise e
    finally:
        conn.close()


def clear_all_student_embeddings():
    """Deletes all records from the student_embeddings table."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM student_embeddings")
        conn.commit()
        print("Successfully cleared all student embeddings.")
    except Exception as e:
        conn.rollback()
        print(f"Error clearing student embeddings: {e}")
        raise e
    finally:
        conn.close()


def add_user(username: str, password_hash: str, role_name: str, totp_secret: str | None): # totp_secret can be None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO users (username, password_hash, role_name, totp_secret)
                   VALUES (%s, %s, %s, %s)""", (username, password_hash, role_name, totp_secret))
    conn.commit()
    conn.close()


def get_user_password_hash(username: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT password_hash
                       FROM users
                       WHERE username = %s""", (username,))
        result = cur.fetchone()
        if result:
            return result['password_hash']
        else:
            return None
    except Exception as e:
        print(f"Error retrieving password hash: {e}")
        return None
    finally:
        conn.close()


def get_all_students():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT student_id, first_name, middle_name, last_name, gender, nationality, department
                   FROM student""")
    students = cur.fetchall()
    conn.close()
    return students


def find_closest_student(embedding: list[float], k: int = 1) -> list[dict]:
    """
    Returns up to k rows of (student_id, view_angle, distance)
    sorted by ascending L2 distance.
    Now also includes sample_index if you want to know which specific sample matched.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT student_id, view_angle, sample_index, student_embedding <-> %s::vector AS distance
           FROM student_embeddings
           ORDER BY distance
           LIMIT %s;
        """, (embedding, k)) # embedding was already a list
    results = cur.fetchall()
    conn.close()
    return results


# Get student details by ID
def get_student_details_by_id(student_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT student_id, first_name, middle_name, last_name, gender, nationality, department
        FROM student
        WHERE student_id = %s
        """, (student_id,)
    )
    student = cur.fetchone() # Returns a RealDictRow or None
    conn.close()
    return student

# Fetch student entry logs by date, joining with student details
def fetch_student_entry_logs_by_date(target_date: py_date): # Use py_date from import
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT l.timestamp, l.event, l.role, l.logged_student_id,
               s.first_name, s.middle_name, s.last_name, s.department
        FROM logs l
        JOIN student s ON l.logged_student_id = s.student_id
        WHERE l.logged_student_id IS NOT NULL
          AND DATE(l.timestamp AT TIME ZONE 'UTC') = %s -- Assuming timestamps are stored in UTC
          AND l.event LIKE 'Recognized student%%' -- Filter for recognition events
        ORDER BY l.timestamp DESC;
    """
    cur.execute(query, (target_date,))
    logs = cur.fetchall()
    conn.close()
    return logs