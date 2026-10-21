"""Read-only connection lifecycle probe; no account access or migrations."""
import json
import time
from pathlib import Path
import app
from database import connect_database, close_database_pools
from services.database_diagnostics import exception_details

rows = []
try:
    if not app.DATABASE_URL:
        raise RuntimeError('This probe requires configured PostgreSQL.')
    for index in range(20):
        start = time.perf_counter()
        connection = connect_database(app.DATABASE_URL, 'unused')
        checkout = (time.perf_counter() - start) * 1000
        try:
            with connection:
                connection.execute('SET TRANSACTION READ ONLY')
                connection.execute('SELECT 1').fetchone()
            # Same adapter is used after the first transaction in login.
            assert not connection._connection.closed
            with connection.autocommit_reads():
                connection.execute('SELECT 1').fetchone()
            rows.append(dict(index=index, checkout_ms=round(checkout, 2), total_ms=round((time.perf_counter()-start)*1000, 2), success=True))
        finally:
            connection.close()
except Exception as error:
    rows.append(dict(success=False, **exception_details(error)))
finally:
    close_database_pools()
Path('../audit/focused-postgres-pool.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps(rows))
