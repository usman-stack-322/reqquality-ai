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

def get_connection():
    import app as config
    connection = connect_database(config.DATABASE_URL, config.DATABASE)
    if connection.dialect == 'postgres':
        try:
            if config._POSTGRES_SCHEMA_URL != config.DATABASE_URL:
                with config._POSTGRES_SCHEMA_LOCK:
                    if config._POSTGRES_SCHEMA_URL != config.DATABASE_URL:
                        initialize_postgresql_schema(connection)
                        initialize_management_schema(connection)
                        config._POSTGRES_SCHEMA_URL = config.DATABASE_URL
        except Exception:
            connection.close()
            raise
    else:
        from invitations import migrate_sqlite_roles
        migrate_sqlite_roles(connection)
        connection.execute('PRAGMA foreign_keys = ON')
        _initialize_database(connection)
        initialize_management_schema(connection)
    from invitations import initialize_invitations
    initialize_invitations(connection)
    return connection
