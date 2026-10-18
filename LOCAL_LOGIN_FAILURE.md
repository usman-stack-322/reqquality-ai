# Localhost login failure — 2026-10-17

## Subsequent HTTPS diagnostic findings

A later read-only test used Neon's documented SQL-over-HTTPS interface solely for
diagnosis; the application's psycopg transport was not changed. `SELECT 1` returned
HTTP 200 in 1,677 ms. This verifies the configured database credentials and endpoint
over HTTPS, although the native PostgreSQL TCP path still times out.

The shown application account exists, is active, has admin role, and has a stored
password hash. The hash itself was not retrieved. Its application password has not
been verified. Read-only schema inspection found **users.project_access missing**
and no reqquality_schema marker. Therefore the database also needs its pending
additive schema initialization before the current login query can run successfully.
This supersedes the earlier statement below that schema/account existence were
entirely unverified: they are now inspected over HTTPS, not through psycopg.

No schema change was executed, no application connection fallback was added, and
no password was changed. Evidence: `audit/login-localhost/https-select-check.json`,
`https-schema-account-check.json`, and the fresh native probe `network-retest.json`.
The public protocol is documented in
[Neon's proxy README](https://github.com/neondatabase/neon/blob/main/proxy/README.md#sql-over-http).

The two remaining blockers are native TCP connectivity and pending schema
initialization. Fixing only one does not establish a successful application login.

**The actual PostgreSQL-backed login is still blocked.** The confirmed failing
stage is TCP connectivity to the configured Neon host on port 5432, before TLS,
PostgreSQL authentication, schema checks, user lookup or password verification.
Repository changes below improve diagnostics/retry handling; they do not restore
the network connection and are not presented as a successful login fix.

## Observed exception and request path

The final clean, network-enabled Flask process logged:

```text
database stage=driver_connect elapsed_ms=9029.8
exception_type=ConnectionTimeout sqlstate=None category=connection_timeout
database stage=pool_checkout
connections_errors=1 pool_available=0
login timing total_ms=10009.9 connect_ms=10009.9
user_query_ms=0.0 password_ms=0.0 permissions_ms=0.0
Database unavailable endpoint=login stage=pool_checkout exception_type=PoolTimeout
```

The exact path is:
`auth_controller.login → auth_service.login → app.get_connection →
database_service._get_connection → database.connect_database → pool.getconn`.
The pool worker's original `psycopg.errors.ConnectionTimeout` comes from
`psycopg.Connection.connect`. When checkout reaches its deadline,
`psycopg_pool.PoolTimeout` propagates through `api_errors` to
`app.database_unavailable`, which returns HTTP 503 and the reported message.
This is not an invalid application password result or evidence of missing tables.
Pool statistics show failed attempts and zero available connections; there is no
evidence of a pool filled with successfully borrowed connections.

## Running configuration and connectivity

Started with the documented commands, from the documented directories:

```powershell
# backend
.\.venv\Scripts\python.exe app.py
# frontend
npm.cmd run dev
```

Existing repository servers were present initially; they were stopped and replaced
to remove stale-process uncertainty. The final backend startup identifies PID 3320,
working directory `backend`, PostgreSQL backend and config source `backend/.env`.
The staged probe imports the actual Flask module in the same virtual environment.
Its effective DATABASE_URL exactly matches backend/.env, no DATABASE_URL was
inherited, and no root .env exists. The configured host is a Neon pooled endpoint,
port 5432, sslmode=require. No secret values or full database URL were printed.
The final servers were left running at 127.0.0.1:5000 and 127.0.0.1:5173.

| Stage | Observed result |
| --- | --- |
| Configuration / DNS | Correct source loaded; three addresses resolved in 136 ms. |
| TCP 5432, each resolved address | TimeoutError at 3,011–3,015 ms per address, tested independently. |
| Same configured hostname, TCP 443 | Connected in 243 ms. This is a TCP control, not a PostgreSQL TLS success. |
| Ordinary HTTPS control | neon.com returned 200 in 392 ms; no proxy environment configuration. |
| Direct-host counterpart control | Same three addresses as pooled; TCP 5432 also timed out. Configuration was not switched. |
| PostgreSQL driver | ConnectionTimeout in 9,044 ms, no SQLSTATE; three address attempts explain the elapsed time. |
| TLS / PostgreSQL authentication | Not reached because TCP could not connect. |
| SELECT 1 / required schema / actual user lookup | Blocked; no session established. No migration was invoked by the probe. |

An initial agent process with offline network restrictions produced fast
OperationalError failures. It was replaced with an explicitly network-enabled
process; **the final evidence above comes from that network-enabled process**.
Visible outbound firewall block rules are identity-scoped Codex sandbox rules;
they were not modified or assumed to explain the separate network-enabled 5432
timeout. The evidence identifies the failing transport/port, not which router,
VPN, ISP, firewall, or provider policy drops the connection.

## Changes limited to this issue

- `backend/services/database_diagnostics.py`: logs original exception class,
  SQLSTATE, elapsed time and sanitized stack locations. Driver messages/URLs,
  passwords, tokens and query parameters are never formatted. Also sanitizes
  psycopg_pool's default raw-exception logs.
- `backend/app.py`: logs localhost configuration source/PID and safe stage/stack
  details when returning the existing controlled 503 response.
- `backend/services/database_service.py`: identifies checkout versus schema stage.
- `backend/services/auth_service.py`: records failed connection duration correctly
  (it previously misleadingly logged connect_ms=0); shares the unchanged exact
  user lookup SQL with the read-only diagnostic script. No authentication logic
  or password handling was changed.
- `backend/database.py`: pool starts lazily (`min_size=0`); libpq connect timeout
  is 3 seconds **per address**; checkout retains the configured DB_POOL_TIMEOUT
  (10 seconds here). Disables the default five-minute reconnect budget. The
  installed pool library permits an immediate final retry even with budget zero:
  **up to two driver attempts**, then it stops; do not describe this as exactly
  one network attempt. Healthy connection reuse, release and rollback remain.
- `backend/diagnose_login.py`: reproducible, read-only staged probe using Flask's
  actual configuration and exact user query. When reachable it checks SELECT 1,
  required login columns/tables, schema marker and optional account existence.
  All queries run in a read-only transaction with a five-second statement limit.
- `backend/test_login_diagnosis.py`: six narrow regressions for safe diagnostics,
  error distinctions, failed timing and bounded real-pool retry scheduling.

No .env, password, saved database, role/CSRF policy, Gemini integration or frontend
feature was changed. No SQLite fallback, new administrator or default password was
introduced. Application query logic/timeouts were not speculatively changed when
the observed request never reached SQL. The diagnostic's read-only SQL is bounded;
actual PostgreSQL query execution and query timeout behavior remain unverified.

## Verification and timings

Actual localhost HTTP measurements used synthetic, deliberately nonexistent
credentials: failure occurs before they can be checked. They do not verify the
user's actual correct password. The environment is this Windows workstation,
the project's virtual environment, real configured PostgreSQL and Vite dev proxy.

| Measurement | Before | Final / after | Outcome |
| --- | --- | --- | --- |
| POST login through Vite, n=1 per column | 10,174 ms | 10,091 ms | Both 503; connectivity not fixed. |
| POST login directly to Flask, baseline n=1 | 10,037 ms | Not used for success comparison | 503. |
| Clean network-enabled POST login, separate n=1 | — | 10,063 ms | 503; same root cause. |
| Chrome form submit, separate n=1 | — | Fetch 10,019 ms; visible error 10,108 ms | One login call, zero AI calls; email retained. |
| Anonymous session lookup, separate n=1 | — | 23 ms HTTP; 0.6 ms handler | 200 unauthenticated; no database access. |
| Actual successful login / authenticated dashboard | Unavailable | Unavailable | Blocked; no success timing claimed. |

An intermediate direct request took 370,843 ms during a long execution gap while
the offline agent backend was running. It is retained in `after-http.json`; its
cause was not isolated. It is not hidden, treated as successful performance, or
used to claim that process scheduling/suspension can be bounded by a socket/pool
timeout. Final network-enabled repeats above reproduced roughly ten seconds.
These are sparse individual observations, not median/p95 or cold/warm benchmarks.

Chrome used the actual configured backend, not a database/provider fixture. Its
resource records show one initial `/api/auth/me`, one `/api/auth/login`, no refresh
loop or AI calls, and zero JavaScript exceptions. The dashboard is not opened
because authentication cannot complete.

**42 targeted backend tests passed** (including six new diagnostics regressions,
pool reuse/release, database outages, login connection count, real password hashing,
valid/invalid auth, token expiration/rotation/revocation, session lookup and logout).
Success/auth tests use isolated temporary SQLite; PostgreSQL driver/pool failures
are mocked where required. **16 frontend tests passed.** These tests preserve
security checks but do not establish a successful login to the configured database.
No frontend source changed, so an unchanged production build was not rerun.

Evidence under `audit/login-localhost/`: `before-http.json`, `final-http.json`,
`network-enabled-http.json`, `stages.json`, `tcp-controls.json`,
`direct-control.json`, `network-control.json`, `final-flask-exception.txt`,
`flask-original-exception.txt`, `browser-failure.json`, `browser-failure.png`,
`auth-checks.txt`. The earlier implementation reports are not proof this login works.

## Exact external action and resumption check

The connection must first be permitted from this computer/network to the hostname
already configured in backend/.env on **outbound TCP 5432**, with return traffic.
Use a network/VPN policy that permits PostgreSQL, or have its administrator allow
that specific destination/port. Do not disable the firewall globally or change
sslmode. Verify the Neon branch/compute and current connection details in
**Neon Console → project → Connect**. If an access restriction is configured,
review it for the current egress IP; the responsible drop location cannot be
determined from this machine's timeout alone. A password reset will not open TCP.
Neon's [Connect/pooling instructions](https://neon.com/docs/connect/connection-pooling)
describe the pooled/direct host selection; changing that toggle does not start or
stop the pooler. [Neon's connection-error guide](https://neon.com/docs/connect/connection-errors)
distinguishes unreachable servers from rejected authentication and missing schema.

After network access is restored, run from `backend`:

```powershell
.\.venv\Scripts\python.exe diagnose_login.py --output ..\audit\login-localhost\restored-stages.json --email "your-existing-account-email"
```

This does not ask for a password or modify accounts/schema. It must pass the TCP,
PostgreSQL authentication, SELECT 1 and required-schema stages before actual
account login can be assessed. If missing schema is reported, review the pending
migrations before running any against production. Then verify the real account
in the browser, invalid-password 401, authenticated refresh/dashboard and logout,
recording successful timings separately. Production application credentials are
not available here; SMTP credentials are not login credentials. No deployment,
provider/firewall change or destructive migration was performed.
