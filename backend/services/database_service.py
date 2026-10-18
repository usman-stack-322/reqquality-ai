from threading import Lock
_SQLITE_READY = set()
_SQLITE_LOCK = Lock()

from database import connect_database, initialize_postgresql_schema
from admin_dashboard import initialize_management_schema

def _initialize_database(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin', 'Manager', 'Analyst', 'SQA Engineer')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    connection.execute("CREATE TABLE IF NOT EXISTS requirements (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL, requirement_type TEXT NOT NULL, priority TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, user_priority TEXT NOT NULL DEFAULT 'Medium', suggested_priority TEXT, risk_score INTEGER, risk_level TEXT, review_status TEXT NOT NULL DEFAULT 'Pending', reviewer_notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, source TEXT NOT NULL DEFAULT 'original', needs_confirmation INTEGER NOT NULL DEFAULT 0, created_by_user_id INTEGER REFERENCES users(id), reviewed_by_user_id INTEGER REFERENCES users(id), reviewed_at TEXT, analysis_summary TEXT NOT NULL DEFAULT '{}')")
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(requirements)')}
    new_columns = {'user_priority': "TEXT NOT NULL DEFAULT 'Medium'", 'suggested_priority': 'TEXT', 'risk_score': 'INTEGER', 'risk_level': 'TEXT', 'review_status': "TEXT NOT NULL DEFAULT 'Pending'", 'reviewer_notes': "TEXT NOT NULL DEFAULT ''", 'updated_at': 'TEXT', 'source': "TEXT NOT NULL DEFAULT 'original'", 'needs_confirmation': 'INTEGER NOT NULL DEFAULT 0', 'created_by_user_id': 'INTEGER REFERENCES users(id)', 'reviewed_by_user_id': 'INTEGER REFERENCES users(id)', 'reviewed_at': 'TEXT', 'analysis_summary': "TEXT NOT NULL DEFAULT '{}'"}
    for name, definition in new_columns.items():
        if name not in columns:
            connection.execute(f'ALTER TABLE requirements ADD COLUMN {name} {definition}')
            if name == 'user_priority':
                connection.execute('UPDATE requirements SET user_priority = priority')
            elif name == 'updated_at':
                connection.execute('UPDATE requirements SET updated_at = created_at')
            elif name == 'source':
                connection.execute("UPDATE requirements SET source = CASE WHEN review_status = 'Approved' THEN 'confirmed' ELSE 'original' END")
            elif name == 'needs_confirmation':
                connection.execute("UPDATE requirements SET needs_confirmation = CASE WHEN review_status = 'Approved' THEN 0 ELSE 0 END")
    connection.execute('UPDATE requirements SET updated_at = created_at WHERE updated_at IS NULL')
    connection.execute("CREATE TABLE IF NOT EXISTS requirement_acceptance_criteria (id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, criterion_code TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'ai_suggestion', needs_confirmation INTEGER NOT NULL DEFAULT 1, introduced_values TEXT NOT NULL DEFAULT '[]', UNIQUE(requirement_id, criterion_code))")
    connection.execute("CREATE TABLE IF NOT EXISTS test_scenarios (id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, scenario_code TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, preconditions TEXT NOT NULL, test_steps TEXT NOT NULL, expected_result TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'ai_suggestion', needs_confirmation INTEGER NOT NULL DEFAULT 1, introduced_values TEXT NOT NULL DEFAULT '[]', assumption_reasons TEXT NOT NULL DEFAULT '[]', UNIQUE(requirement_id, scenario_code))")
    connection.execute("CREATE TABLE IF NOT EXISTS requirement_assumptions (id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE, assumption_code TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'ai_assumption', needs_confirmation INTEGER NOT NULL DEFAULT 1, introduced_values TEXT NOT NULL DEFAULT '[]', UNIQUE(requirement_id, assumption_code))")
    table_additions = {'requirement_acceptance_criteria': {'source': "TEXT NOT NULL DEFAULT 'ai_suggestion'", 'needs_confirmation': 'INTEGER NOT NULL DEFAULT 1', 'introduced_values': "TEXT NOT NULL DEFAULT '[]'"}, 'test_scenarios': {'source': "TEXT NOT NULL DEFAULT 'ai_suggestion'", 'needs_confirmation': 'INTEGER NOT NULL DEFAULT 1', 'introduced_values': "TEXT NOT NULL DEFAULT '[]'", 'assumption_reasons': "TEXT NOT NULL DEFAULT '[]'"}, 'requirement_assumptions': {'source': "TEXT NOT NULL DEFAULT 'ai_assumption'", 'needs_confirmation': 'INTEGER NOT NULL DEFAULT 1', 'introduced_values': "TEXT NOT NULL DEFAULT '[]'"}}
    migrated_tables = set()
    for table, additions in table_additions.items():
        table_columns = {row['name'] for row in connection.execute(f'PRAGMA table_info({table})')}
        for name, definition in additions.items():
            if name not in table_columns:
                connection.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
                migrated_tables.add(table)
    if 'requirement_acceptance_criteria' in migrated_tables:
        connection.execute("UPDATE requirement_acceptance_criteria SET source = 'confirmed', needs_confirmation = 0 WHERE requirement_id IN (SELECT id FROM requirements WHERE review_status = 'Approved')")
    if 'test_scenarios' in migrated_tables:
        connection.execute("UPDATE test_scenarios SET source = 'confirmed', needs_confirmation = 0 WHERE requirement_id IN (SELECT id FROM requirements WHERE review_status = 'Approved')")
    if 'requirement_assumptions' in migrated_tables:
        connection.execute("UPDATE requirement_assumptions SET needs_confirmation = 0 WHERE requirement_id IN (SELECT id FROM requirements WHERE review_status = 'Approved')")
    connection.commit()

_SCHEMA_VERSION = 20261017
_SCHEMA_LOCK_ID = 7265717175616


def _schema_current(connection):
    with connection.autocommit_reads():
        table = connection.execute("SELECT to_regclass('reqquality_schema') AS name").fetchone()
        if not table or not isinstance(table['name'], str):
            return False
        row = connection.execute('SELECT version FROM reqquality_schema WHERE id=1').fetchone()
        return bool(row and row['version'] == _SCHEMA_VERSION)


def _initialize_production_schema(connection):
    from invitations import initialize_invitations
    from services.token_service import initialize_token_schema
    from services.rate_limit_service import initialize_rate_limit_schema
    from services.workflow_service import initialize_workflow_schema
    if _schema_current(connection):
        return
    # Session lock spans the existing initializers' commits and serializes workers.
    with connection.autocommit_reads():
        acquired = connection.execute('SELECT pg_try_advisory_lock(?)', (_SCHEMA_LOCK_ID,)).fetchone()[0]
        if not acquired:
            from psycopg_pool import PoolTimeout
            raise PoolTimeout('Schema initialization is in progress; retry this request.')
    try:
        if _schema_current(connection):
            return
        initialize_postgresql_schema(connection)
        initialize_management_schema(connection)
        initialize_invitations(connection)
        initialize_token_schema(connection)
        initialize_rate_limit_schema(connection)
        initialize_workflow_schema(connection)
        with connection:
            connection.execute('CREATE TABLE IF NOT EXISTS reqquality_schema (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)')
            connection.execute('INSERT INTO reqquality_schema(id,version) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version', (_SCHEMA_VERSION,))
    finally:
        if connection._connection.info.transaction_status.name != 'IDLE':
            connection._connection.rollback()
        with connection.autocommit_reads():
            connection.execute('SELECT pg_advisory_unlock(?)', (_SCHEMA_LOCK_ID,))


def _get_connection():
    import app as config
    from flask import g, has_request_context
    from invitations import initialize_invitations, migrate_sqlite_roles
    from services.token_service import initialize_token_schema
    from services.rate_limit_service import initialize_rate_limit_schema

    if has_request_context():
        g.database_stage = 'pool_checkout' if config.DATABASE_URL else 'sqlite_connect'
    connection = connect_database(config.DATABASE_URL, config.DATABASE)
    # Initialization is part of db_connect; avoid double-counting its schema SQL.
    connection._instrument = False
    try:
        if has_request_context():
            g.database_stage = 'schema_check'
        if connection.dialect == 'postgres':
            # All schema work belongs to initialization, never the warm request path.
            # Publish the marker only after every migration succeeds.
            if config._POSTGRES_SCHEMA_URL != config.DATABASE_URL:
                with config._POSTGRES_SCHEMA_LOCK:
                    if config._POSTGRES_SCHEMA_URL != config.DATABASE_URL:
                        _initialize_production_schema(connection)
                        config._POSTGRES_SCHEMA_URL = config.DATABASE_URL
        else:
            connection.execute('PRAGMA foreign_keys = ON')
            key = (str(config.DATABASE.resolve()), config.DATABASE.stat().st_ino)
            with _SQLITE_LOCK:
                if key not in _SQLITE_READY:
                    migrate_sqlite_roles(connection)
                    _initialize_database(connection)
                    initialize_management_schema(connection)
                    initialize_invitations(connection)
                    initialize_token_schema(connection)
                    initialize_rate_limit_schema(connection)
                    from services.workflow_service import initialize_workflow_schema
                    initialize_workflow_schema(connection)
                    _SQLITE_READY.add(key)
        connection._instrument = True
        if has_request_context():
            g.database_stage = 'connected'
        return connection
    except Exception:
        connection.close()
        raise


def get_connection():
    from time import perf_counter
    from middlewares.observability import record_timing
    start = perf_counter()
    try:
        return _get_connection()
    finally:
        record_timing('db_connect', (perf_counter() - start) * 1000)
