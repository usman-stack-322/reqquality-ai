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
        "id", "name", "email", "password_hash", "role", "created_at", "is_active", "auth_version", "project_access",
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
        "reviewed_by_user_id", "reviewed_at", "analysis_summary", "assigned_reviewer_user_id", "revision", "project_id", "content_revision", "reviewed_content_revision", "criteria_review_required",
    ),
    "requirement_acceptance_criteria": (
        "id", "requirement_id", "criterion_code", "description", "source",
        "needs_confirmation", "introduced_values",
    ),
    "test_scenarios": (
        "id", "requirement_id", "scenario_code", "category", "title", "preconditions",
        "test_steps", "expected_result", "source", "needs_confirmation", "introduced_values",
        "assumption_reasons", "criterion_codes", "project_id", "requirement_revision", "case_revision", "test_data", "test_type", "priority", "review_status", "review_notes", "clarification_notes", "archived", "created_by_user_id",
    ),
    "requirement_assumptions": (
        "id", "requirement_id", "assumption_code", "description", "source",
        "needs_confirmation", "introduced_values",
    ),
    "activity_events": ("id", "actor_id", "actor_name", "action", "entity_type", "entity_id", "summary", "created_at"),
    "organization_settings": ("id", "name", "overdue_days"),
    "requirement_history": ("id", "requirement_id", "actor_id", "action", "created_at", "snapshot"),
}
TABLE_COLUMNS = {"projects": ("id", "name", "context", "revision"), **TABLE_COLUMNS,
                 "requirement_analysis_drafts": ("id", "requirement_id", "project_id", "requirement_revision", "user_id", "input_hash", "result", "created_at")}
TABLE_COLUMNS.update({
    "test_case_versions": ("id","scenario_id","case_revision","project_id","requirement_revision","actor_id","recorded_at","snapshot"),
    "test_executions": ("id","scenario_id","case_version_id","project_id","requirement_revision","status","actual_result","blocked_reason","tester_id","tester_name","executed_at","environment","build","notes","evidence_reference","request_key","input_hash"),
    "bugs": ("id","project_id","requirement_id","scenario_id","failed_execution_id","title","preconditions","steps_to_reproduce","expected_result","actual_result","severity","priority","environment","build","evidence_reference","status","reporter_id","reporter_name","created_at","updated_at","revision","last_retest_execution_id","resolution_reason","request_key","input_hash"),
    "requirement_versions": ("id","requirement_id","project_id","content_revision","actor_id","recorded_at","origin","snapshot"),
    "requirement_reviews": ("id","requirement_id","project_id","content_revision","status","reviewer_id","reviewer_name","notes","reviewed_at","snapshot"),
    "bug_history": ("id","bug_id","action","from_status","to_status","actor_id","actor_name","recorded_at","note","retest_execution_id","snapshot"),
})


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
        from services.workflow_service import initialize_workflow_schema
        initialize_workflow_schema(destination)
        projects_existed = destination.execute("SELECT to_regclass('projects') AS name").fetchone()['name'] is not None
        from services.project_service import initialize_project_schema
        initialize_project_schema(destination)
        from services.case_service import initialize_test_case_schema, ensure_version
        initialize_test_case_schema(destination)
        from services.bug_service import initialize_bug_schema
        initialize_bug_schema(destination)
        from services.integrated_service import initialize_integrated_schema, remember_version
        initialize_integrated_schema(destination)
        counts = {}
        with destination:
            for table, columns in TABLE_COLUMNS.items():
                if table in ("requirement_versions", "requirement_reviews", "bugs", "bug_history", "test_case_versions", "test_executions", "projects", "requirement_analysis_drafts", "user_invitations", "activity_events", "organization_settings", "requirement_history") and not source.execute("SELECT name FROM sqlite_master WHERE name = ?", (table,)).fetchone():
                    continue
                available = {row['name'] for row in source.execute(f'PRAGMA table_info({table})')}
                # Older source databases legitimately lack the new management columns.
                optional = {'is_active', 'auth_version', 'assigned_reviewer_user_id', 'project_access', 'revision', 'criterion_codes', 'project_id', 'content_revision', 'reviewed_content_revision', 'criteria_review_required'}
                if table=='test_scenarios':
                    optional.update(('requirement_revision','case_revision','test_data','test_type','priority','review_status','review_notes','clarification_notes','archived','created_by_user_id'))
                columns = tuple(column for column in columns if column in available or column not in optional)
                column_list = ", ".join(columns)
                source_rows = source.execute(
                    f"SELECT {column_list} FROM {table} ORDER BY id"
                ).fetchall()
                if table == 'organization_settings' and not settings_existed and source_rows:
                    destination.execute('DELETE FROM organization_settings WHERE id=1')
                if table == 'projects' and not projects_existed and source_rows:
                    destination.execute("DELETE FROM projects WHERE id='current'")
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
                        if table=='requirements' and 'content_revision' not in columns:
                            destination.execute('UPDATE requirements SET content_revision=revision WHERE id=?',(row['id'],))
                    else:
                        already_present += 1
                counts[table] = {
                    "source": len(source_rows),
                    "migrated": migrated,
                    "already_present": already_present,
                }

            destination.execute('UPDATE test_scenarios SET requirement_revision=(SELECT content_revision FROM requirements WHERE id=test_scenarios.requirement_id) WHERE requirement_revision IS NULL')
            destination.execute("UPDATE test_scenarios SET priority=COALESCE((SELECT user_priority FROM requirements WHERE id=test_scenarios.requirement_id),'Medium') WHERE priority IS NULL")
            for case in destination.execute('SELECT * FROM test_scenarios').fetchall():
                ensure_version(destination,case)

            for row in destination.execute('SELECT * FROM requirements').fetchall():
                value=dict(row)
                value['acceptance_criteria']=[dict(v) for v in destination.execute('SELECT * FROM requirement_acceptance_criteria WHERE requirement_id=?',(row['id'],))]
                remember_version(destination,value,origin='first observed during import')

            for table in TABLE_COLUMNS:
                if table in ('organization_settings', 'projects'):
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
