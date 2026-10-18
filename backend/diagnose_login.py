"""Read-only staged diagnosis using Flask's actual configuration and lookup SQL.

Run from backend: .venv/Scripts/python.exe diagnose_login.py --output <path>
Optional --email selects a login lookup (never a password or account modification).
Driver messages, account contents, hosts, URLs and credentials are never printed.
"""
import argparse
import json
import os
import socket
import ssl
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

INHERITED = 'DATABASE_URL' in os.environ
import app
import psycopg
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict
from services.auth_service import LOGIN_USER_QUERY
from services.database_diagnostics import exception_details
from services.database_service import _SCHEMA_VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--email', default='diagnostic-no-account@example.invalid')
    args = parser.parse_args()
    rows = []

    def record(stage, **details):
        row = dict(stage=stage, **details)
        rows.append(row)
        print(json.dumps(row), flush=True)

    def failure(stage, error, started):
        record(stage, success=False, elapsed_ms=round((perf_counter()-started)*1000, 2), **exception_details(error))

    def finish(code):
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2), encoding='utf-8')
        return code

    directory = Path(app.__file__).resolve().parent
    record('runtime', executable=sys.executable, cwd=str(Path.cwd()), app_module=str(Path(app.__file__).resolve()),
           database_backend='postgres' if app.DATABASE_URL else 'sqlite',
           config_source='process environment' if INHERITED else 'backend/.env' if app._DATABASE_URL_FROM_BACKEND_ENV else 'root .env/default',
           matches_backend_env=app.DATABASE_URL == dotenv_values(directory/'.env').get('DATABASE_URL'),
           inherited_database_url_present=INHERITED)
    if not app.DATABASE_URL:
        record('connection', success=False, reason='Explicit SQLite configuration: this PostgreSQL probe does not open or change SQLite.')
        return finish(1)
    started = perf_counter()
    try:
        config = conninfo_to_dict(app.DATABASE_URL)
        host, port = config['host'], int(config.get('port', 5432))
        record('configuration', success=True, provider='Neon' if host.endswith('.neon.tech') else 'other',
               pooled='-pooler.' in host, port=port, sslmode=config.get('sslmode', 'prefer'))
        addresses = sorted({row[4][0] for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        record('dns', success=True, addresses=len(addresses), elapsed_ms=round((perf_counter()-started)*1000, 2))
    except Exception as error:
        failure('configuration_or_dns', error, started)
        return finish(1)

    def tcp_tls(item):
        index, address = item
        started = perf_counter()
        try:
            with socket.create_connection((address, port), timeout=3) as connection:
                tcp_ms = round((perf_counter()-started)*1000, 2)
                connection.sendall(struct.pack('!II', 8, 80877103))
                if connection.recv(1) != b'S':
                    return dict(address_index=index, tcp=True, tcp_ms=tcp_ms, tls=False, reason='SSLRequest not accepted')
                with ssl.create_default_context().wrap_socket(connection, server_hostname=host) as secure:
                    return dict(address_index=index, tcp=True, tcp_ms=tcp_ms, tls=True, tls_version=secure.version())
        except Exception as error:
            return dict(address_index=index, success=False, elapsed_ms=round((perf_counter()-started)*1000, 2), **exception_details(error))

    with ThreadPoolExecutor(max_workers=4) as executor:
        probes = list(executor.map(tcp_tls, enumerate(addresses)))
    record('tcp_tls', success=any(probe.get('tls') for probe in probes), results=probes)
    # Independent libpq attempt retains the original exception class, rather than
    # the PoolTimeout raised when Flask's checkout deadline expires. No schema init.
    started = perf_counter()
    try:
        connection = psycopg.connect(app.DATABASE_URL, connect_timeout=3, autocommit=True)
    except Exception as error:
        failure('postgres_connect_authentication', error, started)
        for stage in ('select_1', 'required_schema', 'login_user_lookup'):
            record(stage, success=False, blocked_by='postgres_connect_authentication; no database session established')
        return finish(1)

    with connection, connection.transaction():
        connection.execute('SET TRANSACTION READ ONLY')
        connection.execute("SET LOCAL statement_timeout = '5s'")
        record('postgres_connect_authentication', success=True, elapsed_ms=round((perf_counter()-started)*1000, 2))
        for stage, operation in (
            ('select_1', lambda: dict(result=connection.execute("SELECT 1, current_setting('transaction_read_only')").fetchone())),
            ('required_schema', lambda: check_schema(connection)),
            ('login_user_lookup', lambda: lookup(connection, args.email)),
        ):
            started = perf_counter()
            try:
                details = operation()
                record(stage, success=not bool(details.get('missing') or details.get('initialization_pending')), elapsed_ms=round((perf_counter()-started)*1000, 2), details=details)
            except Exception as error:
                failure(stage, error, started)
                return finish(1)
    return finish(0 if all(row.get('success', True) for row in rows) else 1)


def check_schema(connection):
    required = {'users': {'id', 'name', 'email', 'password_hash', 'role', 'created_at', 'is_active', 'auth_version', 'project_access'},
                'role_permissions': {'role', 'permission', 'enabled'},
                'request_limits': {'key_hash', 'window_start', 'attempts'},
                'auth_refresh_tokens': {'token_hash', 'user_id', 'family_id', 'auth_version', 'created_at', 'expires_at', 'revoked_at', 'replaced_by_hash'}}
    rows = connection.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=ANY(%s)", (list(required),)).fetchall()
    found = {table: {column for name, column in rows if name == table} for table in required}
    missing = {table: sorted(columns-found[table]) for table, columns in required.items() if columns-found[table]}
    marker = connection.execute("SELECT to_regclass('reqquality_schema')").fetchone()[0]
    version = connection.execute('SELECT version FROM reqquality_schema WHERE id=1').fetchone() if marker else None
    current_version = version[0] if version else None
    return dict(missing=missing, schema_version=current_version, expected_schema_version=_SCHEMA_VERSION,
                initialization_pending=current_version != _SCHEMA_VERSION, no_migrations_run=True)


def lookup(connection, email):
    row = connection.execute(LOGIN_USER_QUERY.replace('?', '%s'), (email.strip().lower(),)).fetchone()
    return dict(found=row is not None, active=bool(row[6]) if row else None,
                password_hash_present=bool(row[3]) if row else None, password_not_tested=True)


if __name__ == '__main__':
    raise SystemExit(main())
