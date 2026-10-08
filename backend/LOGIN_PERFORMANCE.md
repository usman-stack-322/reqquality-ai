# Login performance investigation

## Current changes

Login reuses one database connection. Admin permissions require no query; other role permissions are read fresh from the database. PostgreSQL schema initialization, including invitation migrations, runs once per configured database per process rather than on every request.

The backend now uses the official [Psycopg connection pool](https://www.psycopg.org/psycopg3/docs/advanced/pool.html) across PostgreSQL endpoints. Connections are borrowed and returned instead of opening a new network connection for every request. Pools are created lazily, bounded to five connections by default, separated by database URL and process, and closed at process exit. Forked workers create their own pools.

Login uses autocommit only for its read-only lookup/permission section. This avoids extra BEGIN and ROLLBACK network round trips. The original transaction mode is restored before returning the connection; write operations retain their existing transaction contexts and commit/rollback behavior. Password verification, session authentication, CSRF, and fresh permissions are preserved. Neither passwords nor password hashes are cached.

## Hosted measurements

The original screenshot showed 10.85 seconds, and the reported timing after the first optimization was 3.8–4 seconds. The first investigation could not access PostgreSQL inside the sandbox. A subsequently authorized network probe measured the configured hosted database successfully.

Before pooling, three fresh connections took **703–1,084 ms** to open. Their first SELECT 1 queries took **220–871 ms**. These establish connection setup and network round trips as substantial contributors, though they do not account for every millisecond of the reported Postman request.

After pooling, a second hosted probe measured:

| Operation | Time |
| --- | --- |
| Initial pool connection | 646 ms |
| Subsequent pool checkout | 0–0.2 ms |
| Read-only SELECT 1 | 94–99 ms |
| Warm login, real account with intentionally invalid password | 256–264 ms |

The warm login test ran through Flask's test client against the actual hosted database, including real password verification. It returned 401 and created no authenticated session. This is not a measurement of a successful Postman request. The existing initialization marker was set only in the diagnostic process to skip migrations on an already provisioned database. No persistent user or application data was modified. A temporary table created inside an intentionally rolled-back transaction verified actual pooled PostgreSQL rollback behavior.

One login timing breakdown was:

    connect: 0.0 ms; user_query: 99.3 ms; password: 154.1 ms; total: 253.7 ms

A 100 ms end-to-end login target remains unproven: the measured database read already approached 100 ms, before password verification and HTTP transit. Initial process startup/migration and cold pool creation can take longer than warm requests.

## Apply and inspect

The pooling dependency is included in requirements.txt and was installed in this workspace's backend virtual environment. Other environments should run:

    python -m pip install -r requirements.txt

Restart the process that serves your Postman base URL so it loads the updated code. Repeat login and open Postman's response Headers tab. The Server-Timing header exposes:

    connect;dur=..., user_query;dur=..., password;dur=..., permissions;dur=..., total;dur=...

Matching login timing lines also appear in the backend log. The total covers database work and password verification through connection cleanup, excluding final response serialization, session cookie signing, and client/network transit. If Postman takes seconds while Server-Timing total is a few hundred milliseconds, investigate proxy/client/network latency outside this measured path. If Server-Timing is absent on a well-formed login, verify that Postman targets the restarted backend.

Optional pool configuration:

- DB_POOL_MAX_SIZE: maximum connections per worker (default 5).
- DB_POOL_TIMEOUT: checkout wait timeout in seconds (default 10).

From the backend folder:

    .venv\Scripts\python.exe benchmark_login.py
    .venv\Scripts\python.exe benchmark_postgres.py
    .venv\Scripts\python.exe -m unittest discover -v

benchmark_login.py uses temporary SQLite and synthetic accounts. benchmark_postgres.py connects to the configured database, performs read queries and a rollback-only temporary-table check, and measures invalid-password login without running migrations or sending email.

Validation: all 95 backend regression tests passed. The hosted probe also verified pooled PostgreSQL rollback behavior.
