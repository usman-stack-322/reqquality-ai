"""Read-only network and PostgreSQL timings. No app initialization or user data output."""
import json
from pathlib import Path
from time import perf_counter
import urllib.request
from dotenv import dotenv_values
from database import connect_database, close_database_pools

config = {**dotenv_values(Path(__file__).parent.parent / '.env'), **dotenv_values(Path(__file__).parent / '.env')}
for path in ['/', '/api/auth/me', '/api/dashboard']:
    try:
        start = perf_counter()
        try:
            response = urllib.request.urlopen('https://www.reqqualityai.site' + path, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            print(json.dumps({'path': path, 'status': response.status, 'ms': round((perf_counter()-start)*1000, 1), 'bytes': len(body), 'content_type': response.headers.get('Content-Type'), 'server_timing': response.headers.get('Server-Timing')}))
    except Exception as error:
        print(json.dumps({'path': path, 'error_type': type(error).__name__}))
try:
    if not config.get('DATABASE_URL'):
        raise RuntimeError('No configured PostgreSQL URL')
    for sample in range(4):
        start = perf_counter()
        c = connect_database(config['DATABASE_URL'], Path('unused.db'))
        opened = perf_counter()
        try:
            # Enforced by PostgreSQL; cannot migrate or modify any rows.
            with c:
                c.execute('SET TRANSACTION READ ONLY')
                c.execute('SELECT 1').fetchone()
                queried = perf_counter()
                c.execute('SELECT COUNT(*) FROM requirements').fetchone()
                counted = perf_counter()
        finally:
            c.close()
        print(json.dumps({'sample': sample+1, 'connect_ms': round((opened-start)*1000,1), 'select_ms': round((queried-opened)*1000,1), 'count_ms': round((counted-queried)*1000,1)}))
finally:
    close_database_pools()
