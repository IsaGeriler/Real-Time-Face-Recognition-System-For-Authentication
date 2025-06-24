from database import database as db_access
from datetime import date, datetime, timezone


# MODIFIED: Added student_id parameter
def record_event(event_description: str, actor_role: str, student_id: str | None = None):
    db_access.log_event(event_description, actor_role, logged_student_id=student_id)


def get_application_logs(limit: int | None = None):
    return db_access.fetch_logs(limit=limit)


# NEW FUNCTION
def get_detailed_student_entries(target_date: date | None = None):
    """
    Fetches student entry logs for a given date, including student details.
    Defaults to today if target_date is None.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()  # Get current UTC date

    raw_logs = db_access.fetch_student_entry_logs_by_date(target_date)

    entries = []
    for row in raw_logs:
        # Construct full name, handling potential None for middle_name
        middle_name_str = row.get('middle_name') or ''
        full_name = f"{row['first_name']} {middle_name_str} {row['last_name']}".replace('  ', ' ').strip()

        entries.append({
            "timestamp": row['timestamp'],  # Already a datetime object from RealDictCursor
            "student_id": row['logged_student_id'],
            "full_name": full_name,
            "department": row['department'],
            "event_description": row['event']  # Original log event string
        })
    return entries