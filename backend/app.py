"""A small Flask API with basic SQLite requirement storage."""

import csv
import json
import hmac
import logging
import os
import re
import secrets
from io import BytesIO, StringIO
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(__file__).parent.parent / ".env")

from flask import Flask, g, jsonify, request, send_file, session
from flask_cors import CORS
from werkzeug.security import check_password_hash

from analyzers.hybrid_analyzer import analyze_hybrid
from database import (
    DATABASE_ERRORS,
    connect_database,
    initialize_postgresql_schema,
)
from reporting import build_project_summary_pdf, build_requirement_pdf
from admin_dashboard import initialize_management_schema, record_activity, register_management_routes

DATABASE_URL = os.getenv("DATABASE_URL") or None

app = Flask(__name__)
frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
CORS(app, origins=frontend_origins, supports_credentials=True)
app.config.update(
    SECRET_KEY=os.getenv("REQQUALITY_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
LOGGER = app.logger
LOGGER.setLevel(logging.INFO)
DATABASE = Path(__file__).parent / "instance" / "reqquality.db"
_POSTGRES_SCHEMA_URL = None
_POSTGRES_SCHEMA_LOCK = Lock()
REQUIREMENT_TYPES = {"Functional", "Non-Functional", "Business"}
PRIORITIES = {"High", "Medium", "Low"}
REVIEW_STATUSES = {"Pending", "In Review", "Approved", "Needs Revision"}
RISK_LEVELS = {"Low", "Medium", "High", "Critical"}
SCENARIO_CATEGORIES = {"Positive", "Negative", "Boundary", "Edge-case"}
CONTENT_SOURCES = {"original", "rule_based", "ai_suggestion", "ai_assumption", "confirmed"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _masked_email(email):
    if not isinstance(email, str):
        return "<invalid>"
    normalized_email = email.strip().lower()
    local, separator, domain = normalized_email.partition("@")
    if not separator or not local or not domain:
        return "<invalid>"
    return f"{local[0]}***@{domain}"


def _initialize_database(connection):
    connection.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
        "email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, "
        "role TEXT NOT NULL CHECK(role IN ('admin', 'Analyst', 'SQA Engineer')), "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS requirements "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "description TEXT NOT NULL, "
        "requirement_type TEXT NOT NULL, "
        "priority TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "user_priority TEXT NOT NULL DEFAULT 'Medium', "
        "suggested_priority TEXT, risk_score INTEGER, risk_level TEXT, "
        "review_status TEXT NOT NULL DEFAULT 'Pending', "
        "reviewer_notes TEXT NOT NULL DEFAULT '', "
        "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "source TEXT NOT NULL DEFAULT 'original', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 0, "
        "created_by_user_id INTEGER REFERENCES users(id), "
        "reviewed_by_user_id INTEGER REFERENCES users(id), reviewed_at TEXT, "
        "analysis_summary TEXT NOT NULL DEFAULT '{}')"
    )
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(requirements)")
    }
    new_columns = {
        "user_priority": "TEXT NOT NULL DEFAULT 'Medium'",
        "suggested_priority": "TEXT",
        "risk_score": "INTEGER",
        "risk_level": "TEXT",
        "review_status": "TEXT NOT NULL DEFAULT 'Pending'",
        "reviewer_notes": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT",
        "source": "TEXT NOT NULL DEFAULT 'original'",
        "needs_confirmation": "INTEGER NOT NULL DEFAULT 0",
        "created_by_user_id": "INTEGER REFERENCES users(id)",
        "reviewed_by_user_id": "INTEGER REFERENCES users(id)",
        "reviewed_at": "TEXT",
        "analysis_summary": "TEXT NOT NULL DEFAULT '{}'",
    }
    for name, definition in new_columns.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE requirements ADD COLUMN {name} {definition}")
            if name == "user_priority":
                connection.execute("UPDATE requirements SET user_priority = priority")
            elif name == "updated_at":
                connection.execute("UPDATE requirements SET updated_at = created_at")
            elif name == "source":
                connection.execute(
                    "UPDATE requirements SET source = CASE WHEN review_status = 'Approved' "
                    "THEN 'confirmed' ELSE 'original' END"
                )
            elif name == "needs_confirmation":
                connection.execute(
                    "UPDATE requirements SET needs_confirmation = CASE "
                    "WHEN review_status = 'Approved' THEN 0 ELSE 0 END"
                )
    connection.execute(
        "UPDATE requirements SET updated_at = created_at WHERE updated_at IS NULL"
    )

    connection.execute(
        "CREATE TABLE IF NOT EXISTS requirement_acceptance_criteria "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, "
        "criterion_code TEXT NOT NULL, description TEXT NOT NULL, "
        "source TEXT NOT NULL DEFAULT 'ai_suggestion', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 1, "
        "introduced_values TEXT NOT NULL DEFAULT '[]', "
        "UNIQUE(requirement_id, criterion_code))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS test_scenarios "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, "
        "scenario_code TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, "
        "preconditions TEXT NOT NULL, test_steps TEXT NOT NULL, expected_result TEXT NOT NULL, "
        "source TEXT NOT NULL DEFAULT 'ai_suggestion', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 1, "
        "introduced_values TEXT NOT NULL DEFAULT '[]', "
        "assumption_reasons TEXT NOT NULL DEFAULT '[]', "
        "UNIQUE(requirement_id, scenario_code))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS requirement_assumptions "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, "
        "assumption_code TEXT NOT NULL, description TEXT NOT NULL, "
        "source TEXT NOT NULL DEFAULT 'ai_assumption', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 1, "
        "introduced_values TEXT NOT NULL DEFAULT '[]', "
        "UNIQUE(requirement_id, assumption_code))"
    )

    table_additions = {
        "requirement_acceptance_criteria": {
            "source": "TEXT NOT NULL DEFAULT 'ai_suggestion'",
            "needs_confirmation": "INTEGER NOT NULL DEFAULT 1",
            "introduced_values": "TEXT NOT NULL DEFAULT '[]'",
        },
        "test_scenarios": {
            "source": "TEXT NOT NULL DEFAULT 'ai_suggestion'",
            "needs_confirmation": "INTEGER NOT NULL DEFAULT 1",
            "introduced_values": "TEXT NOT NULL DEFAULT '[]'",
            "assumption_reasons": "TEXT NOT NULL DEFAULT '[]'",
        },
        "requirement_assumptions": {
            "source": "TEXT NOT NULL DEFAULT 'ai_assumption'",
            "needs_confirmation": "INTEGER NOT NULL DEFAULT 1",
            "introduced_values": "TEXT NOT NULL DEFAULT '[]'",
        },
    }
    migrated_tables = set()
    for table, additions in table_additions.items():
        table_columns = {
            row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
        }
        for name, definition in additions.items():
            if name not in table_columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
                migrated_tables.add(table)
    if "requirement_acceptance_criteria" in migrated_tables:
        connection.execute(
            "UPDATE requirement_acceptance_criteria SET source = 'confirmed', needs_confirmation = 0 "
            "WHERE requirement_id IN (SELECT id FROM requirements WHERE review_status = 'Approved')"
        )
    if "test_scenarios" in migrated_tables:
        connection.execute(
            "UPDATE test_scenarios SET source = 'confirmed', needs_confirmation = 0 "
            "WHERE requirement_id IN (SELECT id FROM requirements WHERE review_status = 'Approved')"
        )
    if "requirement_assumptions" in migrated_tables:
        connection.execute(
            "UPDATE requirement_assumptions SET needs_confirmation = 0 "
            "WHERE requirement_id IN (SELECT id FROM requirements WHERE review_status = 'Approved')"
        )
    connection.commit()


def get_connection():
    global _POSTGRES_SCHEMA_URL
    connection = connect_database(DATABASE_URL, DATABASE)
    if connection.dialect == "postgres":
        try:
            if _POSTGRES_SCHEMA_URL != DATABASE_URL:
                with _POSTGRES_SCHEMA_LOCK:
                    if _POSTGRES_SCHEMA_URL != DATABASE_URL:
                        initialize_postgresql_schema(connection)
                        initialize_management_schema(connection)
                        _POSTGRES_SCHEMA_URL = DATABASE_URL
        except Exception:
            connection.close()
            raise
    else:
        from invitations import migrate_sqlite_roles
        migrate_sqlite_roles(connection)
        connection.execute("PRAGMA foreign_keys = ON")
        _initialize_database(connection)
        initialize_management_schema(connection)
    from invitations import initialize_invitations
    initialize_invitations(connection)
    return connection


def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _inserted_id(connection, cursor):
    if connection.dialect == "postgres":
        return cursor.fetchone()["id"]
    return cursor.lastrowid


def _public_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"],
    }


def _get_current_user():
    if not hasattr(g, "current_user"):
        user_id = session.get("user_id")
        if not user_id:
            g.current_user = None
        else:
            connection = get_connection()
            try:
                g.current_user = connection.execute(
                    "SELECT id, name, email, role, created_at, is_active, auth_version FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if g.current_user is not None and (not g.current_user["is_active"] or g.current_user["auth_version"] != session.get("auth_version", 0)):
                    g.current_user = None
                    session.clear()
            finally:
                connection.close()
    return g.current_user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _get_current_user() is None:
            return jsonify(error="Please log in to continue."), 401
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = _get_current_user()
            if user is None:
                return jsonify(error="Please log in to continue."), 401
            g.current_user = user
            if user["role"] not in roles:
                return jsonify(error="Your account does not have permission for this action."), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


def csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return jsonify(error="CSRF validation failed. Refresh your session and try again."), 403
        return view(*args, **kwargs)
    return wrapped


def api_errors(public_message):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                return view(*args, **kwargs)
            except Exception as error:
                LOGGER.exception(
                    "API endpoint failed endpoint=%s exception_type=%s",
                    request.endpoint,
                    type(error).__name__,
                )
                return jsonify(error=public_message), 500
        return wrapped
    return decorate


def _get_requirement_detail(connection, requirement_id):
    row = connection.execute(
        "SELECT r.*, u.name AS assigned_reviewer FROM requirements r LEFT JOIN users u ON u.id=r.assigned_reviewer_user_id WHERE r.id = ?", (requirement_id,)
    ).fetchone()
    if row is None:
        return None

    requirement = dict(row)
    requirement["needs_confirmation"] = bool(requirement["needs_confirmation"])
    try:
        analysis = json.loads(requirement.get("analysis_summary") or "{}")
        requirement["analysis_summary"] = analysis if isinstance(analysis, dict) else {}
    except (ValueError, TypeError):
        requirement["analysis_summary"] = {}
    if requirement.get("reviewed_by_user_id") is not None:
        reviewer = connection.execute(
            "SELECT name FROM users WHERE id = ?",
            (requirement["reviewed_by_user_id"],),
        ).fetchone()
        requirement["reviewed_by_name"] = reviewer["name"] if reviewer else None
    else:
        requirement["reviewed_by_name"] = None
    requirement["acceptance_criteria"] = [
        dict(item)
        for item in connection.execute(
            "SELECT criterion_code, description, source, needs_confirmation, introduced_values "
            "FROM requirement_acceptance_criteria "
            "WHERE requirement_id = ? ORDER BY id",
            (requirement_id,),
        ).fetchall()
    ]
    for criterion in requirement["acceptance_criteria"]:
        criterion["needs_confirmation"] = bool(criterion["needs_confirmation"])
        criterion["introduced_values"] = json.loads(criterion["introduced_values"])
    scenarios = connection.execute(
        "SELECT id, scenario_code, category, title, preconditions, test_steps, expected_result, "
        "source, needs_confirmation, introduced_values, assumption_reasons "
        "FROM test_scenarios WHERE requirement_id = ? ORDER BY id",
        (requirement_id,),
    ).fetchall()
    requirement["test_scenarios"] = []
    for scenario_row in scenarios:
        scenario = dict(scenario_row)
        scenario["preconditions"] = json.loads(scenario["preconditions"])
        scenario["test_steps"] = json.loads(scenario["test_steps"])
        scenario["needs_confirmation"] = bool(scenario["needs_confirmation"])
        scenario["introduced_values"] = json.loads(scenario["introduced_values"])
        scenario["assumption_reasons"] = json.loads(scenario["assumption_reasons"])
        requirement["test_scenarios"].append(scenario)
    assumptions = connection.execute(
        "SELECT assumption_code, description, source, needs_confirmation, introduced_values "
        "FROM requirement_assumptions WHERE requirement_id = ? ORDER BY id",
        (requirement_id,),
    ).fetchall()
    requirement["assumptions"] = [dict(item) for item in assumptions]
    for assumption in requirement["assumptions"]:
        assumption["needs_confirmation"] = bool(assumption["needs_confirmation"])
        assumption["introduced_values"] = json.loads(assumption["introduced_values"])
    return requirement


def _validate_analysis_payload(analysis):
    if analysis is None:
        return None
    if not isinstance(analysis, dict):
        return "Analysis must be an object."

    risk_score = analysis.get("risk_score")
    if risk_score is not None and (
        isinstance(risk_score, bool) or not isinstance(risk_score, int) or not 0 <= risk_score <= 100
    ):
        return "Risk score must be an integer from 0 to 100."
    suggested_priority = analysis.get("suggested_priority")
    if suggested_priority is not None and suggested_priority not in PRIORITIES:
        return "Analysis contains an invalid suggested priority."
    risk_level = analysis.get("risk_level")
    if risk_level is not None and risk_level not in RISK_LEVELS:
        return "Analysis contains an invalid risk level."
    criteria = analysis.get("acceptance_criteria", [])
    if not isinstance(criteria, list) or any(not isinstance(value, str) for value in criteria):
        return "Acceptance criteria must be a list of strings."
    scenarios = analysis.get("test_scenarios", [])
    if not isinstance(scenarios, list):
        return "Test scenarios must be a list."
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            return "Each test scenario must be an object."
        if scenario.get("category") not in SCENARIO_CATEGORIES:
            return "A test scenario has an invalid category."
        if not isinstance(scenario.get("title"), str) or not scenario["title"].strip():
            return "Each test scenario must have a title."
        if not isinstance(scenario.get("expected_result"), str):
            return "Each test scenario must have an expected result."
        for field in ("preconditions", "test_steps"):
            values = scenario.get(field, [])
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                return f"Scenario {field.replace('_', ' ')} must be a list of strings."
        if scenario.get("source") is not None and scenario["source"] not in CONTENT_SOURCES:
            return "A test scenario has an invalid source."
        if scenario.get("needs_confirmation") is not None and not isinstance(scenario["needs_confirmation"], bool):
            return "Scenario needs_confirmation must be true or false."
        for field in ("introduced_values", "assumption_reasons"):
            values = scenario.get(field, [])
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                return f"Scenario {field.replace('_', ' ')} must be a list of strings."
    labeled_analysis = analysis.get("labeled_analysis", {})
    if not isinstance(labeled_analysis, dict):
        return "Labeled analysis must be an object."
    for field in ("acceptance_criteria", "assumptions"):
        items = labeled_analysis.get(field, [])
        if not isinstance(items, list):
            return f"Labeled {field.replace('_', ' ')} must be a list."
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                return f"Each labeled {field.replace('_', ' ')} item must include text."
            if item.get("source") not in CONTENT_SOURCES:
                return f"A labeled {field.replace('_', ' ')} item has an invalid source."
            if not isinstance(item.get("needs_confirmation"), bool):
                return f"A labeled {field.replace('_', ' ')} item needs a confirmation flag."
            values = item.get("introduced_values", [])
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                return "Introduced values must be a list of strings."
    return None


@app.get("/api/health")
def health():
    return jsonify(status="ok", message="ReqQuality AI API is running")


@app.post("/api/auth/register")
def register():
    return jsonify(error="Account creation requires an invitation from your administrator."), 403


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        LOGGER.warning("login failure normalized_email=<invalid> reason=invalid_payload")
        return jsonify(error="Send a JSON object with your email and password."), 400
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        LOGGER.warning("login failure normalized_email=%s reason=invalid_input", _masked_email(email))
        return jsonify(error="Enter a valid email address and password."), 400
    normalized_email = email.strip().lower()
    safe_email = _masked_email(normalized_email)
    LOGGER.info("login attempt normalized_email=%s", safe_email)

    connection = get_connection()
    try:
        user = connection.execute(
            "SELECT id, name, email, password_hash, role, created_at, is_active, auth_version FROM users WHERE lower(email) = ?",
            (normalized_email,),
        ).fetchone()
    finally:
        connection.close()
    if user is None or not user["is_active"]:
        LOGGER.warning("login user_found=false normalized_email=%s", safe_email)
        LOGGER.warning("login password_verification=not_run reason=user_not_found")
        return jsonify(error="Email or password is incorrect."), 401
    LOGGER.info("login user_found=true normalized_email=%s user_id=%s", safe_email, user["id"])
    if not check_password_hash(user["password_hash"], password):
        LOGGER.warning("login password_verification=false normalized_email=%s", safe_email)
        return jsonify(error="Email or password is incorrect."), 401
    LOGGER.info("login password_verification=true normalized_email=%s", safe_email)

    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["auth_version"] = user["auth_version"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(user=_public_user(user), csrf_token=session["csrf_token"])


@app.get("/api/auth/me")
def current_user():
    user = _get_current_user()
    if user is None:
        return jsonify(authenticated=False)
    return jsonify(
        authenticated=True,
        user=_public_user(user),
        csrf_token=session.get("csrf_token"),
    )


@app.post("/api/auth/logout")
@login_required
@csrf_required
def logout():
    session.clear()
    return jsonify(message="Logged out successfully.")


@app.post("/api/requirements")
@api_errors("Unable to save the requirement. Please try again.")
@login_required
@roles_required("Analyst")
@csrf_required
def create_requirement():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object with requirement details."), 400

    title = data.get("title")
    description = data.get("description")
    requirement_type = data.get("requirement_type")
    priority = data.get("user_priority", data.get("priority"))
    analysis = data.get("analysis")

    if not isinstance(title, str) or not title.strip():
        return jsonify(error="Please enter a requirement title."), 400
    if not isinstance(description, str) or not description.strip():
        return jsonify(error="Please enter a requirement description."), 400
    if not isinstance(requirement_type, str) or requirement_type not in REQUIREMENT_TYPES:
        return jsonify(error="Choose a valid requirement type."), 400
    if not isinstance(priority, str) or priority not in PRIORITIES:
        return jsonify(error="Choose a valid priority."), 400
    validation_error = _validate_analysis_payload(analysis)
    if validation_error:
        return jsonify(error=validation_error), 400

    analysis = analysis or {}
    acceptance_criteria = [
        value.strip() for value in analysis.get("acceptance_criteria", []) if value.strip()
    ]
    labeled_analysis = analysis.get("labeled_analysis", {})
    criteria_details = {
        item["text"].strip(): item
        for item in labeled_analysis.get("acceptance_criteria", [])
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    }
    assumption_details = labeled_analysis.get("assumptions", [])
    if not assumption_details:
        assumption_details = [
            {
                "text": value,
                "source": "ai_assumption",
                "needs_confirmation": True,
                "introduced_values": [],
            }
            for value in analysis.get("assumptions", [])
        ]
    scenarios = analysis.get("test_scenarios", [])
    analysis_summary = {
        field: analysis[field]
        for field in (
            "ambiguity_issues",
            "missing_information",
            "testability_issues",
            "assumptions",
            "edge_cases",
            "improved_requirement",
            "labeled_analysis",
            "analysis_mode",
            "llm_status",
        )
        if field in analysis
    }

    connection = get_connection()
    try:
        with connection:
            insert_statement = (
                "INSERT INTO requirements "
                "(title, description, requirement_type, priority, user_priority, "
                "suggested_priority, risk_score, risk_level, updated_at, created_by_user_id, analysis_summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            )
            if connection.dialect == "postgres":
                insert_statement += " RETURNING id"
            cursor = connection.execute(
                insert_statement,
                (
                    title.strip(), description.strip(), requirement_type, priority, priority,
                    analysis.get("suggested_priority"), analysis.get("risk_score"),
                    analysis.get("risk_level"), _utc_timestamp(), g.current_user["id"],
                    json.dumps(analysis_summary, ensure_ascii=True),
                ),
            )
            requirement_id = _inserted_id(connection, cursor)
            connection.executemany(
                "INSERT INTO requirement_acceptance_criteria "
                "(requirement_id, criterion_code, description, source, needs_confirmation, introduced_values) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        requirement_id,
                        f"AC-{index:03d}",
                        criterion,
                        criteria_details.get(criterion, {}).get("source", "rule_based"),
                        int(criteria_details.get(criterion, {}).get("needs_confirmation", False)),
                        json.dumps(criteria_details.get(criterion, {}).get("introduced_values", [])),
                    )
                    for index, criterion in enumerate(acceptance_criteria, start=1)
                ],
            )
            scenario_records = []
            for index, scenario in enumerate(scenarios, start=1):
                scenario_code = scenario.get("id") or f"SC-{index:03d}"
                scenario_records.append((
                    requirement_id,
                    scenario_code,
                    scenario["category"],
                    scenario["title"].strip(),
                    json.dumps(scenario.get("preconditions", [])),
                    json.dumps(scenario.get("test_steps", [])),
                    scenario["expected_result"].strip(),
                    scenario.get("source", "rule_based"),
                    int(scenario.get("needs_confirmation", False)),
                    json.dumps(scenario.get("introduced_values", [])),
                    json.dumps(scenario.get("assumption_reasons", [])),
                ))
            connection.executemany(
                "INSERT INTO test_scenarios "
                "(requirement_id, scenario_code, category, title, preconditions, test_steps, expected_result, "
                "source, needs_confirmation, introduced_values, assumption_reasons) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                scenario_records,
            )
            connection.executemany(
                "INSERT INTO requirement_assumptions "
                "(requirement_id, assumption_code, description, source, needs_confirmation, introduced_values) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        requirement_id,
                        f"AS-{index:03d}",
                        item["text"].strip(),
                        "ai_assumption",
                        int(item.get("needs_confirmation", True)),
                        json.dumps(item.get("introduced_values", [])),
                    )
                    for index, item in enumerate(assumption_details, start=1)
                    if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()
                ],
            )
            record_activity(connection, g.current_user, "requirement_created", "requirement", requirement_id, f"Created REQ-{requirement_id}")
            requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()

    return jsonify(requirement=requirement), 201


@app.get("/api/dashboard")
@api_errors("Unable to load dashboard data. Please try again.")
@login_required
def dashboard_summary():
    connection = get_connection()
    try:
        totals = connection.execute(
            "SELECT COUNT(*) AS total_requirements, "
            "SUM(CASE WHEN review_status = 'Pending' THEN 1 ELSE 0 END) AS pending_count, "
            "SUM(CASE WHEN review_status = 'In Review' THEN 1 ELSE 0 END) AS in_review_count, "
            "SUM(CASE WHEN review_status = 'Approved' THEN 1 ELSE 0 END) AS approved_count, "
            "SUM(CASE WHEN review_status = 'Needs Revision' THEN 1 ELSE 0 END) AS needs_revision_count, "
            "SUM(CASE WHEN risk_level = 'Low' THEN 1 ELSE 0 END) AS low_risk_count, "
            "SUM(CASE WHEN risk_level = 'Medium' THEN 1 ELSE 0 END) AS medium_risk_count, "
            "SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END) AS high_risk_count, "
            "SUM(CASE WHEN risk_level = 'Critical' THEN 1 ELSE 0 END) AS critical_risk_count, "
            "SUM(CASE WHEN requirement_type = 'Functional' THEN 1 ELSE 0 END) AS functional_count, "
            "SUM(CASE WHEN requirement_type = 'Non-Functional' THEN 1 ELSE 0 END) AS non_functional_count, "
            "SUM(CASE WHEN requirement_type = 'Business' THEN 1 ELSE 0 END) AS business_count, "
            "COALESCE(ROUND(AVG(risk_score), 1), 0) AS average_risk_score "
            "FROM requirements"
        ).fetchone()
        total_scenarios = connection.execute(
            "SELECT COUNT(*) FROM test_scenarios"
        ).fetchone()[0]
        traceable_count = connection.execute(
            "SELECT COUNT(*) FROM requirements AS requirement "
            "WHERE EXISTS (SELECT 1 FROM requirement_acceptance_criteria AS criterion "
            "WHERE criterion.requirement_id = requirement.id) "
            "AND EXISTS (SELECT 1 FROM test_scenarios AS scenario "
            "WHERE scenario.requirement_id = requirement.id)"
        ).fetchone()[0]

        requirement_fields = (
            "id, title, description, requirement_type, priority, user_priority, "
            "suggested_priority, risk_score, risk_level, review_status, created_at, updated_at"
        )
        recent_requirements = connection.execute(
            f"SELECT {requirement_fields} FROM requirements "
            "ORDER BY COALESCE(updated_at, created_at) DESC, id DESC LIMIT 5"
        ).fetchall()
        high_attention_requirements = connection.execute(
            f"SELECT {requirement_fields} FROM requirements "
            "WHERE risk_level IN ('High', 'Critical') OR review_status = 'Needs Revision' "
            "ORDER BY CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, "
            "risk_score DESC, COALESCE(updated_at, created_at) DESC, id DESC"
        ).fetchall()
    finally:
        connection.close()

    total_requirements = int(totals["total_requirements"] or 0)
    status_counts = {
        field: int(totals[field] or 0)
        for field in (
            "pending_count", "in_review_count", "approved_count", "needs_revision_count",
        )
    }
    risk_counts = {
        field: int(totals[field] or 0)
        for field in (
            "low_risk_count", "medium_risk_count", "high_risk_count", "critical_risk_count",
        )
    }
    type_counts = {
        field: int(totals[field] or 0)
        for field in ("functional_count", "non_functional_count", "business_count")
    }
    average_risk_score = float(totals["average_risk_score"] or 0)
    total_test_scenarios = int(total_scenarios or 0)
    traceable_count = int(traceable_count or 0)
    traceability_coverage = (
        float(round(traceable_count * 100 / total_requirements, 1))
        if total_requirements else 0.0
    )
    return jsonify(
        total_requirements=total_requirements,
        **status_counts,
        **risk_counts,
        **type_counts,
        average_risk_score=average_risk_score,
        total_test_scenarios=total_scenarios,
        traceability_coverage_percent=traceability_coverage,
        traceable_requirement_count=traceable_count,
        recent_requirements=[dict(row) for row in recent_requirements],
        high_attention_requirements=[dict(row) for row in high_attention_requirements],
    )


@app.get("/api/requirements")
@login_required
def list_requirements():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM requirements ORDER BY id DESC"
        ).fetchall()
    finally:
        connection.close()

    return jsonify(requirements=[dict(row) for row in rows])


@app.get("/api/requirements/<int:requirement_id>")
@login_required
def get_requirement(requirement_id):
    connection = get_connection()
    try:
        requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    if requirement is None:
        return jsonify(error="Requirement not found."), 404
    return jsonify(requirement=requirement)


def _project_report_summary(connection):
    rows = connection.execute(
        "SELECT review_status, risk_level, requirement_type, risk_score FROM requirements"
    ).fetchall()
    review_counts = {status: 0 for status in REVIEW_STATUSES}
    risk_counts = {level: 0 for level in RISK_LEVELS}
    risk_counts["Unscored"] = 0
    type_counts = {requirement_type: 0 for requirement_type in REQUIREMENT_TYPES}
    risk_scores = []
    for row in rows:
        review_counts[row["review_status"]] = review_counts.get(row["review_status"], 0) + 1
        risk_level = row["risk_level"] or "Unscored"
        risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
        type_counts[row["requirement_type"]] = type_counts.get(row["requirement_type"], 0) + 1
        if row["risk_score"] is not None:
            risk_scores.append(row["risk_score"])

    total_requirements = len(rows)
    total_test_scenarios = connection.execute(
        "SELECT COUNT(*) FROM test_scenarios"
    ).fetchone()[0]
    traceable_requirement_count = connection.execute(
        "SELECT COUNT(*) FROM requirements AS requirement "
        "WHERE EXISTS (SELECT 1 FROM requirement_acceptance_criteria AS criterion "
        "WHERE criterion.requirement_id = requirement.id) "
        "AND EXISTS (SELECT 1 FROM test_scenarios AS scenario "
        "WHERE scenario.requirement_id = requirement.id)"
    ).fetchone()[0]
    high_attention_requirements = [
        dict(row)
        for row in connection.execute(
            "SELECT id, title, risk_score, risk_level, review_status "
            "FROM requirements WHERE risk_level IN ('High', 'Critical') "
            "OR review_status = 'Needs Revision' "
            "ORDER BY CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, "
            "risk_score DESC, COALESCE(updated_at, created_at) DESC, id DESC"
        ).fetchall()
    ]
    return {
        "total_requirements": total_requirements,
        "review_counts": review_counts,
        "risk_counts": risk_counts,
        "type_counts": type_counts,
        "average_risk_score": round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0,
        "total_test_scenarios": total_test_scenarios,
        "traceable_requirement_count": traceable_requirement_count,
        "traceability_coverage_percent": (
            round(traceable_requirement_count * 100 / total_requirements, 1)
            if total_requirements else 0
        ),
        "high_attention_requirements": high_attention_requirements,
    }


def _download_response(file_stream, filename, mimetype):
    response = send_file(
        file_stream,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/requirements/<int:requirement_id>/report.pdf")
@login_required
def export_requirement_pdf(requirement_id):
    connection = get_connection()
    try:
        requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    if requirement is None:
        return jsonify(error="Requirement not found."), 404
    return _download_response(
        build_requirement_pdf(requirement),
        f"reqquality-requirement-{requirement_id}.pdf",
        "application/pdf",
    )


@app.get("/api/reports/project.pdf")
@login_required
def export_project_pdf():
    connection = get_connection()
    try:
        summary = _project_report_summary(connection)
    finally:
        connection.close()
    return _download_response(
        build_project_summary_pdf(summary),
        "reqquality-project-summary.pdf",
        "application/pdf",
    )


@app.get("/api/exports/requirements.csv")
@login_required
def export_requirements_csv():
    fields = (
        "id", "title", "requirement_type", "user_priority", "suggested_priority",
        "risk_score", "risk_level", "review_status", "created_at", "updated_at",
    )
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, title, requirement_type, COALESCE(user_priority, priority) AS user_priority, "
            "suggested_priority, risk_score, risk_level, review_status, created_at, updated_at "
            "FROM requirements ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(fields)
    for row in rows:
        cells = []
        for field in fields:
            value = row[field]
            if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
                value = "'" + value
            cells.append(value)
        writer.writerow(cells)
    return _download_response(
        BytesIO(output.getvalue().encode("utf-8-sig")),
        "reqquality-requirements.csv",
        "text/csv; charset=utf-8",
    )


def _save_review(requirement_id, data, required_fields=()):
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object with review details."), 400
    if not any(field in data for field in ("review_status", "reviewer_notes")):
        return jsonify(error="Provide a review status or reviewer notes."), 400
    if any(field not in data for field in required_fields):
        return jsonify(error="Include the required review field."), 400

    updates = []
    values = []
    if "review_status" in data:
        review_status = data["review_status"]
        if not isinstance(review_status, str) or review_status not in REVIEW_STATUSES:
            return jsonify(error="Choose a valid review status."), 400
        updates.append("review_status = ?")
        values.append(review_status)
        updates.extend(("source = ?", "needs_confirmation = 0"))
        values.append("confirmed" if review_status == "Approved" else "original")
    if "reviewer_notes" in data:
        reviewer_notes = data["reviewer_notes"]
        if not isinstance(reviewer_notes, str):
            return jsonify(error="Reviewer notes must be text."), 400
        updates.append("reviewer_notes = ?")
        values.append(reviewer_notes.strip())
    review_timestamp = _utc_timestamp()
    updates.extend(("reviewed_by_user_id = ?", "reviewed_at = ?"))
    values.extend((g.current_user["id"], review_timestamp))
    updates.append("updated_at = ?")
    values.append(review_timestamp)
    values.append(requirement_id)

    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                f"UPDATE requirements SET {', '.join(updates)} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                return jsonify(error="Requirement not found."), 404
            if "review_status" in data:
                _update_related_confirmation(
                    connection,
                    requirement_id,
                    approved=review_status == "Approved",
                )
            record_activity(connection, g.current_user, "review_updated", "requirement", requirement_id, f"Reviewed REQ-{requirement_id}: {data.get('review_status', 'notes updated')}")
            requirement = _get_requirement_detail(connection, requirement_id)
    finally:
        connection.close()
    return jsonify(requirement=requirement)


def _update_related_confirmation(connection, requirement_id, approved):
    if approved:
        for table in (
            "requirement_acceptance_criteria",
            "test_scenarios",
            "requirement_assumptions",
        ):
            connection.execute(
                f"UPDATE {table} SET needs_confirmation = 0 WHERE requirement_id = ?",
                (requirement_id,),
            )
        return

    criteria = connection.execute(
        "SELECT id, source, introduced_values FROM requirement_acceptance_criteria "
        "WHERE requirement_id = ?",
        (requirement_id,),
    ).fetchall()
    for item in criteria:
        source = item["source"]
        needs_confirmation = source in {"ai_assumption", "confirmed"} or bool(
            json.loads(item["introduced_values"])
        )
        if source == "confirmed":
            source = "ai_suggestion"
        connection.execute(
            "UPDATE requirement_acceptance_criteria SET source = ?, needs_confirmation = ? WHERE id = ?",
            (source, int(needs_confirmation), item["id"]),
        )

    scenarios = connection.execute(
        "SELECT id, source, introduced_values, assumption_reasons FROM test_scenarios "
        "WHERE requirement_id = ?",
        (requirement_id,),
    ).fetchall()
    for item in scenarios:
        source = item["source"]
        needs_confirmation = (
            source in {"ai_assumption", "confirmed"}
            or bool(json.loads(item["introduced_values"]))
            or bool(json.loads(item["assumption_reasons"]))
        )
        if source == "confirmed":
            source = "ai_suggestion"
        connection.execute(
            "UPDATE test_scenarios SET source = ?, needs_confirmation = ? WHERE id = ?",
            (source, int(needs_confirmation), item["id"]),
        )
    connection.execute(
        "UPDATE requirement_assumptions SET needs_confirmation = 1 WHERE requirement_id = ?",
        (requirement_id,),
    )


@app.patch("/api/requirements/<int:requirement_id>/review")
@login_required
@roles_required("SQA Engineer")
@csrf_required
def update_review(requirement_id):
    return _save_review(requirement_id, request.get_json(silent=True))


@app.patch("/api/requirements/<int:requirement_id>/review-status")
@login_required
@roles_required("SQA Engineer")
@csrf_required
def update_review_status(requirement_id):
    return _save_review(
        requirement_id,
        request.get_json(silent=True),
        required_fields=("review_status",),
    )


@app.patch("/api/requirements/<int:requirement_id>/reviewer-notes")
@login_required
@roles_required("SQA Engineer")
@csrf_required
def update_reviewer_notes(requirement_id):
    return _save_review(
        requirement_id,
        request.get_json(silent=True),
        required_fields=("reviewer_notes",),
    )


@app.post("/api/analyze-requirement")
@login_required
@roles_required("Analyst")
@csrf_required
def analyze_requirement_endpoint():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object with requirement details."), 400

    title = data.get("title")
    description = data.get("description")
    requirement_type = data.get("requirement_type")
    priority = data.get("priority")

    if not isinstance(title, str) or not title.strip():
        return jsonify(error="Please enter a requirement title."), 400
    if not isinstance(description, str) or not description.strip():
        return jsonify(error="Please enter a requirement description."), 400
    if not isinstance(requirement_type, str) or requirement_type not in REQUIREMENT_TYPES:
        return jsonify(error="Choose a valid requirement type."), 400
    if not isinstance(priority, str) or priority not in PRIORITIES:
        return jsonify(error="Choose a valid priority."), 400

    return jsonify(analyze_hybrid(title, description, requirement_type, priority))


from invitations import register_invitation_routes
register_invitation_routes(app, get_connection, roles_required, csrf_required)
register_management_routes(app, get_connection, roles_required, csrf_required, login_required)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
