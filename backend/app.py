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

# Local overrides apply only to the loopback development entry point.
# Load before shared configuration so explicit empty DATABASE_URL stays empty.
_DATABASE_URL_INHERITED = 'DATABASE_URL' in os.environ
if __name__ == '__main__':
    load_dotenv(Path(__file__).parent / '.env.local')

_DATABASE_URL_FROM_LOCAL_ENV = not _DATABASE_URL_INHERITED and 'DATABASE_URL' in os.environ
load_dotenv(Path(__file__).parent / '.env')

_DATABASE_URL_FROM_BACKEND_ENV = not (_DATABASE_URL_INHERITED or _DATABASE_URL_FROM_LOCAL_ENV) and 'DATABASE_URL' in os.environ
load_dotenv(Path(__file__).parent.parent / '.env')
DATABASE_CONFIG_SOURCE = ('process environment' if _DATABASE_URL_INHERITED else
                          'backend/.env.local' if _DATABASE_URL_FROM_LOCAL_ENV else
                          'backend/.env' if _DATABASE_URL_FROM_BACKEND_ENV else 'root .env/default')

from flask import Flask, g, jsonify, request, send_file, session

from flask_cors import CORS

from werkzeug.security import check_password_hash



from database import DATABASE_ERRORS, DATABASE_UNAVAILABLE_ERRORS, connect_database, initialize_postgresql_schema


from admin_dashboard import initialize_management_schema, record_activity, register_management_routes

DATABASE_URL = os.getenv('DATABASE_URL') or None

if DATABASE_URL and any(len((os.getenv(key) or '').encode('utf-8')) < 32
                        for key in ('REQQUALITY_SECRET_KEY', 'JWT_SECRET_KEY')):
    raise RuntimeError('PostgreSQL deployments require persistent REQQUALITY_SECRET_KEY and JWT_SECRET_KEY of at least 32 bytes each.')

# Direct execution is loopback-only development; WSGI imports stay HTTPS-only.
LOCAL_HTTP_DEVELOPMENT = __name__ == '__main__'
app = Flask(__name__)
app.config['LOCAL_HTTP_DEVELOPMENT'] = LOCAL_HTTP_DEVELOPMENT
from middlewares.observability import register_observability
register_observability(app)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024

def database_unavailable(error):
    # Do not log exception text: drivers may include credentials/connection info.
    from services.database_diagnostics import exception_details
    app.logger.error('Database unavailable endpoint=%s stage=%s pid=%s diagnostic=%s',
                     request.endpoint, getattr(g, 'database_stage', 'unknown'), os.getpid(), exception_details(error))
    response = jsonify(error='The database is temporarily unavailable. Please try again later.', code='database_unavailable')
    response.status_code = 503
    response.headers['Retry-After'] = '30'
    return response

for database_error in DATABASE_UNAVAILABLE_ERRORS:
    app.register_error_handler(database_error, database_unavailable)

from werkzeug.exceptions import HTTPException
@app.errorhandler(HTTPException)
def api_http_error(error):
    return jsonify(error=error.description), error.code

@app.errorhandler(413)
def request_too_large(error):
    return jsonify(error='Request body must be at most 1 MB.'), 413

frontend_origins = [origin.strip() for origin in os.getenv('FRONTEND_ORIGINS', 'https://localhost:5173,https://127.0.0.1:5173,https://www.reqqualityai.site,https://reqqualityai.site').split(',') if origin.strip()]

if LOCAL_HTTP_DEVELOPMENT:
    frontend_origins += ['http://localhost:5173', 'http://127.0.0.1:5173']

CORS(app, origins=frontend_origins, supports_credentials=True)

app.config.update(SECRET_KEY=os.getenv('REQQUALITY_SECRET_KEY') or secrets.token_hex(32), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))

# Production cookies require HTTPS; direct loopback development uses HTTP.
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') or app.config['SECRET_KEY']
if len(app.config['JWT_SECRET_KEY'].encode('utf-8')) < 32:
    raise RuntimeError('JWT_SECRET_KEY must contain at least 32 bytes.')
app.config['SESSION_COOKIE_SECURE'] = not LOCAL_HTTP_DEVELOPMENT
from services.token_service import apply_auth_cookies
app.after_request(apply_auth_cookies)

@app.before_request
def require_secure_authentication():
    local_http = app.config.get('LOCAL_HTTP_DEVELOPMENT', False)
    if local_http and request.host.split(':', 1)[0] not in ('localhost', '127.0.0.1'):
        return jsonify(error='Local development accepts loopback hosts only.'), 403
    if request.path in ('/api/auth/login', '/api/auth/refresh') and not request.is_secure and not local_http:
        return jsonify(error='Use HTTPS for Secure authentication cookies.'), 426
    if request.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('Origin')
        if origin and origin not in frontend_origins and origin != request.host_url.rstrip('/'):
            return jsonify(error='Request origin is not allowed.'), 403

if not LOCAL_HTTP_DEVELOPMENT and int(os.getenv('TRUST_PROXY_HOPS', '0')):
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=int(os.getenv('TRUST_PROXY_HOPS')), x_for=int(os.getenv('TRUST_PROXY_HOPS')))

LOGGER = app.logger

LOGGER.setLevel(logging.INFO)

DATABASE = Path(os.getenv('SQLITE_DATABASE_PATH') or Path(__file__).parent / 'instance' / 'reqquality.db')
if not DATABASE.is_absolute():
    DATABASE = Path(__file__).parent / DATABASE

_POSTGRES_SCHEMA_URL = None

_POSTGRES_SCHEMA_LOCK = Lock()

REQUIREMENT_TYPES = {'Functional', 'Non-Functional', 'Business'}

PRIORITIES = {'High', 'Medium', 'Low'}

REVIEW_STATUSES = {'Draft', 'Ready for Review', 'Pending', 'In Review', 'Approved', 'Needs Revision'}

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
from routes.project_routes import register_routes as register_project_routes
register_project_routes(app)
from routes.case_routes import register_routes as register_test_case_routes
register_test_case_routes(app)
from routes.bug_routes import register_routes as register_bug_routes
register_bug_routes(app)

register_password_reset_routes(app, get_connection)
register_invitation_routes(app, get_connection, roles_required, csrf_required)
register_management_routes(app, get_connection, roles_required, csrf_required, login_required)

from services.workflow_service import project_access_guard
app.before_request(project_access_guard)


if __name__ == "__main__":
    app.logger.info('Local runtime pid=%s cwd=%s database_backend=%s database_config_source=%s',
                    os.getpid(), Path.cwd(), 'postgres' if DATABASE_URL else 'sqlite',
                    DATABASE_CONFIG_SOURCE)
    app.run(debug=False, host="127.0.0.1", port=5000)
