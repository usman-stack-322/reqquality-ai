"""Explicit, repeatable importer for the existing SQLite database."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from database import connect_database, initialize_postgresql_schema
from invitations import initialize_invitations
from admin_dashboard import initialize_management_schema

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

TABLE_COLUMNS = {
    "users": (
        "id", "name", "email", "password_hash", "role", "created_at", "is_active", "auth_version",
    ),
    "user_invitations": (
        "id", "name", "email", "role", "token_hash", "status", "failed_attempts",
        "window_failed_attempts", "failure_window_started_at", "last_failed_attempt_at",
        "temporarily_locked_until", "created_at", "expires_at", "accepted_at", "revoked_at",
        "invited_by", "delivery_status",
    ),
    "requirements": (
        "id", "title", "description", "requirement_type", "priority", "created_at",
        "user_priority", "suggested_priority", "risk_score", "risk_level", "review_status",
        "reviewer_notes", "updated_at", "source", "needs_confirmation", "created_by_user_id",
        "reviewed_by_user_id", "reviewed_at", "analysis_summary", "assigned_reviewer_user_id",
    ),
    "requirement_acceptance_criteria": (
        "id", "requirement_id", "criterion_code", "description", "source",
        "needs_confirmation", "introduced_values",
    ),
    "test_scenarios": (
        "id", "requirement_id", "scenario_code", "category", "title", "preconditions",
        "test_steps", "expected_result", "source", "needs_confirmation", "introduced_values",
        "assumption_reasons",
    ),
    "requirement_assumptions": (
        "id", "requirement_id", "assumption_code", "description", "source",
        "needs_confirmation", "introduced_values",
    ),
    "activity_events": ("id", "actor_id", "actor_name", "action", "entity_type", "entity_id", "summary", "created_at"),
    "organization_settings": ("id", "name", "overdue_days"),
}


def migrate(sqlite_path, postgres_url):
    sqlite_path = Path(sqlite_path).resolve()
    if not sqlite_path.is_file():
        raise FileNotFoundError("The source SQLite database file does not exist.")
    if not postgres_url:
        raise ValueError("Set DATABASE_URL to the PostgreSQL destination before importing.")

    source_uri = sqlite_path.as_uri() + "?mode=ro"
    source = sqlite3.connect(source_uri, uri=True)
    source.row_factory = sqlite3.Row
    destination = connect_database(postgres_url, sqlite_path)
    if destination.dialect != "postgres":
        source.close()
        destination.close()
        raise ValueError("DATABASE_URL must identify a PostgreSQL database.")

    try:
        initialize_postgresql_schema(destination)
        initialize_invitations(destination)
        settings_existed = destination.execute("SELECT to_regclass('organization_settings') AS name").fetchone()['name'] is not None
        initialize_management_schema(destination)
        counts = {}
        with destination:
            for table, columns in TABLE_COLUMNS.items():
                if table in ("user_invitations", "activity_events", "organization_settings") and not source.execute("SELECT name FROM sqlite_master WHERE name = ?", (table,)).fetchone():
                    continue
                available = {row['name'] for row in source.execute(f'PRAGMA table_info({table})')}
                # Older source databases legitimately lack the new management columns.
                optional = {'is_active', 'auth_version', 'assigned_reviewer_user_id'}
                columns = tuple(column for column in columns if column in available or column not in optional)
                column_list = ", ".join(columns)
                source_rows = source.execute(
                    f"SELECT {column_list} FROM {table} ORDER BY id"
                ).fetchall()
                if table == 'organization_settings' and not settings_existed and source_rows:
                    destination.execute('DELETE FROM organization_settings WHERE id=1')
                migrated = 0
                already_present = 0
                placeholders = ", ".join("?" for _ in columns)
                insert_statement = (
                    f"INSERT INTO {table} ({column_list}) VALUES ({placeholders}) "
                    "ON CONFLICT (id) DO NOTHING"
                )
                for row in source_rows:
                    values = tuple("SQA Engineer" if column == "role" and row[column] == "SQA Reviewer" else row[column] for column in columns)
                    existing = destination.execute(
                        f"SELECT {column_list} FROM {table} WHERE id = ?",
                        (row["id"],),
                    ).fetchone()
                    if existing is not None:
                        existing_values = tuple(existing[column] for column in columns)
                        if existing_values != values:
                            raise ValueError(
                                f"Conflicting row found in {table} for ID {row['id']}; "
                                "the import was rolled back."
                            )
                        already_present += 1
                        continue
                    cursor = destination.execute(insert_statement, values)
                    if cursor.rowcount:
                        migrated += 1
                    else:
                        already_present += 1
                counts[table] = {
                    "source": len(source_rows),
                    "migrated": migrated,
                    "already_present": already_present,
                }

            for table in TABLE_COLUMNS:
                if table == 'organization_settings':
                    continue
                destination.execute(
                    "SELECT setval(pg_get_serial_sequence(?, 'id')::regclass, "
                    "GREATEST(COALESCE(MAX(id), 1), 1), COUNT(*) > 0) "
                    f"FROM {table}",
                    (table,),
                )
        return counts
    finally:
        source.close()
        destination.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=Path(__file__).parent / "instance" / "reqquality.db",
        help="Existing local SQLite database (read-only source).",
    )
    arguments = parser.parse_args()

    try:
        counts = migrate(arguments.sqlite, os.getenv("DATABASE_URL"))
    except Exception as error:
        print(
            f"Migration failed ({type(error).__name__}); review the source and destination configuration.",
            file=sys.stderr,
        )
        return 1

    print("SQLite to PostgreSQL import completed:")
    for table, count in counts.items():
        print(
            f"{table}: source={count['source']} migrated={count['migrated']} "
            f"already_present={count['already_present']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
