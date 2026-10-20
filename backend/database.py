"""Small SQLite/PostgreSQL connection adapter for the Flask application."""

import re
import atexit
import os
from contextlib import contextmanager
from threading import Lock
import sqlite3
from pathlib import Path
from time import perf_counter, monotonic
from middlewares.observability import record_timing

import psycopg
from psycopg_pool import ConnectionPool, PoolTimeout, TooManyRequests, PoolClosed
from services.database_diagnostics import DiagnosticConnection, LOGGER

# Connectivity failures are service outages, not failed credential checks.
DATABASE_UNAVAILABLE_ERRORS = (psycopg.OperationalError, PoolTimeout, TooManyRequests, PoolClosed,
                               psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable)


def _postgres_row_factory(cursor):
    if cursor.description is None:
        return lambda values: DatabaseRow()
    columns = [column.name for column in cursor.description]

    def make_row(values):
        return DatabaseRow(zip(columns, values))

    return make_row


class DatabaseRow(dict):
    """Mapping row with SQLite-compatible positional access."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class DatabaseConnection:
    def __init__(self, connection, dialect, pool=None):
        self._connection = connection
        self.dialect = dialect
        self._pool = pool
        self._released = False
        self._instrument = True

    def _ensure_open(self):
        if self._released:
            error_type = psycopg.InterfaceError if self.dialect == 'postgres' else sqlite3.ProgrammingError
            raise error_type('This database connection has already been closed.')

    def _adapt_sql(self, statement):
        if self.dialect == "postgres":
            return re.sub(r"\?", "%s", statement)
        return statement

    def execute(self, statement, parameters=()):
        self._ensure_open()
        if not self._instrument:
            return self._connection.execute(self._adapt_sql(statement), parameters)
        start = perf_counter()
        try:
            return self._connection.execute(self._adapt_sql(statement), parameters)
        finally:
            record_timing('db_execute', (perf_counter() - start) * 1000)

    def executemany(self, statement, parameters):
        self._ensure_open()
        cursor = self._connection.cursor()
        start = perf_counter()
        try:
            cursor.executemany(self._adapt_sql(statement), parameters)
        finally:
            if self._instrument:
                record_timing('db_execute', (perf_counter() - start) * 1000)
        return cursor

    def commit(self):
        self._ensure_open()
        self._connection.commit()

    def close(self):
        if self._released:
            return
        self._released = True
        if self._pool is not None:
            self._connection._reqquality_returned_at = monotonic()
            self._pool.putconn(self._connection)
        else:
            self._connection.close()

    @contextmanager
    def autocommit_reads(self):
        """Avoid BEGIN/ROLLBACK round trips for a sequence containing only reads."""
        self._ensure_open()
        if self.dialect != 'postgres':
            yield self
            return
        previous = self._connection.autocommit
        self._connection.autocommit = True
        try:
            yield self
        finally:
            self._connection.autocommit = previous


    def __enter__(self):
        self._ensure_open()
        self._connection.__enter__()
        return self

    def __exit__(self, exception_type, exception, traceback):
        return self._connection.__exit__(exception_type, exception, traceback)


# Pools are created lazily and never shared across worker processes.
_POSTGRES_POOLS = {}
_POOL_LOCK = Lock()


def _check_idle_connection(connection):
    # Warm checkouts avoid a network round trip. Validate sockets after inactivity
    # so serverless freezes/provider idle disconnects don't fail the next login.
    returned = getattr(connection, '_reqquality_returned_at', None)
    if connection.closed or (returned is not None and monotonic() - returned >= 30):
        ConnectionPool.check_connection(connection)


def _get_postgres_pool(database_url):
    key = (os.getpid(), database_url)
    with _POOL_LOCK:
        pool = _POSTGRES_POOLS.get(key)
        if pool is None or pool.closed:
            pool = ConnectionPool(
                conninfo=database_url,
                connection_class=DiagnosticConnection,
                # Do not inject startup timeout options: Neon/PgBouncer rejects
                # them. Query budgets must be configured as database role defaults.
                kwargs={'row_factory': _postgres_row_factory, 'connect_timeout': 3},
                check=_check_idle_connection,
                # No eager connection or five-minute background retry chain. A new
                # request can try again after a failed attempt; no SQLite fallback.
                min_size=0,
                max_size=int(os.getenv('DB_POOL_MAX_SIZE', '5')),
                max_waiting=20,
                timeout=float(os.getenv('DB_POOL_TIMEOUT', '10')),
                max_idle=60,
                max_lifetime=1800,
                reconnect_timeout=0,
                open=True,
            )
            _POSTGRES_POOLS[key] = pool
        return pool


def close_database_pools():
    with _POOL_LOCK:
        pools = list(_POSTGRES_POOLS.values())
        _POSTGRES_POOLS.clear()
    for pool in pools:
        pool.close()


def _reset_pools_after_fork():
    global _POOL_LOCK, _POSTGRES_POOLS
    _POOL_LOCK = Lock()
    _POSTGRES_POOLS = {}


if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=_reset_pools_after_fork)
atexit.register(close_database_pools)


def connect_database(database_url, sqlite_path):
    if database_url:
        normalized_url = database_url.strip()
        if normalized_url.startswith("postgres://"):
            normalized_url = "postgresql://" + normalized_url[len("postgres://"):]
        if normalized_url.startswith("postgresql+psycopg://"):
            normalized_url = "postgresql://" + normalized_url[len("postgresql+psycopg://"):]
        pool = _get_postgres_pool(normalized_url)
        try:
            connection = pool.getconn()
        except PoolTimeout:
            stats = pool.get_stats()
            LOGGER.error('database stage=pool_checkout pid=%s stats=%s', os.getpid(),
                         {key: stats.get(key) for key in ('connections_num', 'connections_errors', 'pool_size', 'pool_available', 'requests_waiting')})
            # psycopg_pool retains expired waiter slots until a connection is
            # delivered. With reconnect_timeout=0 an empty failed pool would
            # eventually fill max_waiting permanently. Retire only pools with
            # no sockets (including borrowed/connecting ones); never disrupt
            # active transactions and never retry this request's writes.
            retire = False
            with _POOL_LOCK:
                key = (os.getpid(), normalized_url)
                if _POSTGRES_POOLS.get(key) is pool and pool.get_stats().get('pool_size') == 0:
                    _POSTGRES_POOLS.pop(key)
                    retire = True
            if retire:
                pool.close()
            raise
        return DatabaseConnection(connection, "postgres", pool=pool)

    database_path = Path(sqlite_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return DatabaseConnection(connection, "sqlite")


DATABASE_ERRORS = (sqlite3.Error, psycopg.Error)
DATABASE_INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)


def initialize_postgresql_schema(connection):
    statements = (
        "CREATE TABLE IF NOT EXISTS users ("
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
        "name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, "
        "role TEXT NOT NULL CHECK(role IN ('admin', 'Manager', 'Analyst', 'SQA Engineer')), "
        "created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text))",
        "CREATE TABLE IF NOT EXISTS requirements ("
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
        "title TEXT NOT NULL, description TEXT NOT NULL, requirement_type TEXT NOT NULL, "
        "priority TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text), "
        "user_priority TEXT NOT NULL DEFAULT 'Medium', suggested_priority TEXT, "
        "risk_score INTEGER, risk_level TEXT, review_status TEXT NOT NULL DEFAULT 'Pending', "
        "reviewer_notes TEXT NOT NULL DEFAULT '', "
        "updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text), "
        "source TEXT NOT NULL DEFAULT 'original', needs_confirmation INTEGER NOT NULL DEFAULT 0, "
        "created_by_user_id BIGINT REFERENCES users(id), "
        "reviewed_by_user_id BIGINT REFERENCES users(id), reviewed_at TEXT, "
        "analysis_summary TEXT NOT NULL DEFAULT '{}')",
        "CREATE TABLE IF NOT EXISTS requirement_acceptance_criteria ("
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
        "requirement_id BIGINT NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, "
        "criterion_code TEXT NOT NULL, description TEXT NOT NULL, "
        "source TEXT NOT NULL DEFAULT 'ai_suggestion', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 1, "
        "introduced_values TEXT NOT NULL DEFAULT '[]', "
        "UNIQUE(requirement_id, criterion_code))",
        "CREATE TABLE IF NOT EXISTS test_scenarios ("
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
        "requirement_id BIGINT NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, "
        "scenario_code TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, "
        "preconditions TEXT NOT NULL, test_steps TEXT NOT NULL, expected_result TEXT NOT NULL, "
        "source TEXT NOT NULL DEFAULT 'ai_suggestion', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 1, "
        "introduced_values TEXT NOT NULL DEFAULT '[]', "
        "assumption_reasons TEXT NOT NULL DEFAULT '[]', UNIQUE(requirement_id, scenario_code))",
        "CREATE TABLE IF NOT EXISTS requirement_assumptions ("
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
        "requirement_id BIGINT NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, "
        "assumption_code TEXT NOT NULL, description TEXT NOT NULL, "
        "source TEXT NOT NULL DEFAULT 'ai_assumption', "
        "needs_confirmation INTEGER NOT NULL DEFAULT 1, "
        "introduced_values TEXT NOT NULL DEFAULT '[]', "
        "UNIQUE(requirement_id, assumption_code))",
        "CREATE INDEX IF NOT EXISTS idx_requirements_created_by_user_id "
        "ON requirements(created_by_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_requirements_reviewed_by_user_id "
        "ON requirements(reviewed_by_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_criteria_requirement_id "
        "ON requirement_acceptance_criteria(requirement_id)",
        "CREATE INDEX IF NOT EXISTS idx_scenarios_requirement_id "
        "ON test_scenarios(requirement_id)",
        "CREATE INDEX IF NOT EXISTS idx_assumptions_requirement_id "
        "ON requirement_assumptions(requirement_id)",
    )
    for statement in statements:
        connection.execute(statement)
    connection.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check")
    connection.execute("UPDATE users SET role = 'SQA Engineer' WHERE role = 'SQA Reviewer'")
    connection.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK(role IN ('admin', 'Manager', 'Analyst', 'SQA Engineer'))")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_normalized ON users(lower(email))")
    connection.commit()
