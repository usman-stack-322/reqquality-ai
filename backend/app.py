"""Flask configuration and registration of the layered backend API."""
import sys

# Use one application module for both python app.py and WSGI imports.
if __name__ == "__main__":
    sys.modules["app"] = sys.modules[__name__]

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

load_dotenv(Path(__file__).parent / '.env')

load_dotenv(Path(__file__).parent.parent / '.env')

from flask import Flask, g, jsonify, request, send_file, session

from flask_cors import CORS

from werkzeug.security import check_password_hash

from analyzers.hybrid_analyzer import analyze_hybrid

from database import DATABASE_ERRORS, connect_database, initialize_postgresql_schema

from reporting import build_project_summary_pdf, build_requirement_pdf

from admin_dashboard import initialize_management_schema, record_activity, register_management_routes

DATABASE_URL = os.getenv('DATABASE_URL') or None

app = Flask(__name__)

frontend_origins = [origin.strip() for origin in os.getenv('FRONTEND_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip()]

CORS(app, origins=frontend_origins, supports_credentials=True)

app.config.update(SECRET_KEY=os.getenv('REQQUALITY_SECRET_KEY') or secrets.token_hex(32), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))

LOGGER = app.logger

LOGGER.setLevel(logging.INFO)

DATABASE = Path(__file__).parent / 'instance' / 'reqquality.db'

_POSTGRES_SCHEMA_URL = None

_POSTGRES_SCHEMA_LOCK = Lock()

REQUIREMENT_TYPES = {'Functional', 'Non-Functional', 'Business'}

PRIORITIES = {'High', 'Medium', 'Low'}

REVIEW_STATUSES = {'Pending', 'In Review', 'Approved', 'Needs Revision'}

RISK_LEVELS = {'Low', 'Medium', 'High', 'Critical'}

SCENARIO_CATEGORIES = {'Positive', 'Negative', 'Boundary', 'Edge-case'}

CONTENT_SOURCES = {'original', 'rule_based', 'ai_suggestion', 'ai_assumption', 'confirmed'}

EMAIL_PATTERN = re.compile('^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$')

from invitations import register_invitation_routes

from password_reset import register_password_reset_routes

from middlewares.auth import login_required, roles_required, csrf_required, api_errors, _get_current_user

def get_connection():
    from services.database_service import get_connection as connect
    return connect()

from routes.health_routes import register_routes as register_health_routes
register_health_routes(app)
from routes.auth_routes import register_routes as register_auth_routes
register_auth_routes(app)
from routes.requirements_routes import register_routes as register_requirements_routes
register_requirements_routes(app)
from routes.dashboard_routes import register_routes as register_dashboard_routes
register_dashboard_routes(app)
from routes.reports_routes import register_routes as register_reports_routes
register_reports_routes(app)
from routes.analysis_routes import register_routes as register_analysis_routes
register_analysis_routes(app)

register_password_reset_routes(app, get_connection)
register_invitation_routes(app, get_connection, roles_required, csrf_required)
register_management_routes(app, get_connection, roles_required, csrf_required, login_required)

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
