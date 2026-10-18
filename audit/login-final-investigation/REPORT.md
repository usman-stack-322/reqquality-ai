# Localhost login: resolved with isolated local database

On 2026-10-18 the user authorized a separate local database. Direct `python app.py` now loads ignored `backend/.env.local` before shared configuration and uses `backend/instance/local-development.db`. Cloud configuration and data were not modified. WSGI does not load the local override. A new local admin was provisioned; credentials are in ignored `backend/instance/local-login.txt`.

Duplicate repository backend processes were stopped and a single local backend restarted. Five real HTTP journeys through Vite passed: login, authenticated profile, admin dashboard, repeat profile/session check, logout, and unauthenticated profile. `verify_local.py` reproduces these checks without printing credentials. The 24 tests in test_local_transport, test_database_pool and test_token_auth passed. Browser rendering was not verified in this run.

The cloud TCP connectivity issue below remains separate. The historical investigation follows.

# Localhost login: Not resolved

## Latest repeat check

The current listeners are backend PID 16688 and Vite PID 18240. Their command
lines point to this repository's virtual environment/app.py and frontend Vite.
The fresh diagnostic uses the same virtual environment, loads backend/.env,
matches its database URL, and has no inherited DATABASE_URL override.

- One synthetic-credentials request through the running Vite proxy: HTTP 503,
  10,049.07 ms; database checkout 10,003.8 ms. This is an outage reproduction,
  not verification of the user's password.
- DNS succeeds in 165.76 ms. Each of the three TCP addresses times out after
  3,000.89–3,015.64 ms on port 5432.
- The native driver raises ConnectionTimeout after 9,016.52 ms, before
  authentication, SELECT 1, schema access or user lookup.
- A separate certificate-verified HTTPS read-only query using the configured
  database credentials returns HTTP 200 in 1,646.56 ms and SELECT 1 succeeds.
  users.project_access and the schema-version marker are still missing.
- The port-443 WebSocket experiment accepts a connection but advertises inner
  PostgreSQL password authentication rather than native TLS channel binding.
  No password was sent in that experiment. The configured channel_binding=require
  was not removed; this transport was not enabled in the application.

No application/configuration/schema/account changes were made in this repeat
check. The experimental WebSocket dependency downgrade was restored. There are
still **0 of 5 verified successful login flows**. Restore native outbound TCP
5432 and return traffic for the configured Neon endpoint without disabling TLS
or channel binding. Once native connectivity works, the missing schema must
also be migrated safely before account login can be verified.

Latest evidence: current-localhost-reproduction.json, current-native-stages.json,
current-https-database-facts.json. The original investigation below describes
the earlier processes and measurements, not the current process IDs.

This investigation made no application, configuration, account or schema changes.
It reproduces the actual failure and distinguishes the active transport failure
from the separately pending schema migration. No mocked test is offered as proof
of a successful login.

## Actual running application

- Port 5173: PID 5252, Vite from this repository's frontend/node_modules.
- Port 5000: PID 3320, launched with this repository's
  backend/.venv/Scripts/python.exe app.py. The base Windows executable is
  C:/Python314/python.exe, as expected for this virtual-environment launcher.
- frontend/vite.config.js proxies /api to http://127.0.0.1:5000.
- The backend startup identifies backend as its working directory, PostgreSQL as
  its selected database, and backend/.env as its configuration source. That file
  predates the backend process; no root .env or inherited DATABASE_URL override
  was found. The same virtual-environment diagnostic imports this project's app.py
  and reports an effective URL matching backend/.env. No URL value was printed.
- Read-only Windows token inspection completed after an initial temporary approval
  quota block. Both Flask and Vite have unrestricted tokens and zero restricted
  SIDs. A restricted-token difference is not supported by this check.

## Observed failure

One request through the actual Vite proxy returned HTTP 503 in **10,061.57 ms**.
Server-Timing: database connection 10,003.1 ms; request 10,007.5 ms.
Flask's logs also confirm the user's manual attempts hit this same backend and
failed before SQL/password verification. The most recent reproduced traceback,
with driver messages/credentials removed, is:

```text
DiagnosticConnection.connect -> psycopg.Connection.connect
exception_type=ConnectionTimeout, category=connection_timeout, sqlstate=None
driver elapsed_ms=9016.6

auth_controller.login -> auth_service.login -> app.get_connection
-> database_service.get_connection -> database_service._get_connection
-> database.connect_database -> psycopg_pool.ConnectionPool.getconn
exception_type=PoolTimeout, stage=pool_checkout
user_query_ms=0.0, password_ms=0.0, permissions_ms=0.0, db_execute_ms=0.0
```

app.database_unavailable handles the propagated PoolTimeout and emits the exact
reported message with code=database_unavailable. Failed connection creation and
zero available connections are observed, rather than a pool full of successfully
borrowed connections. The installed pool performs its bounded final retry, then
stops; reducing its waiting time would not restore connectivity.

## Independent stages, same Python environment

| Stage | Result | Elapsed |
| --- | --- | --- |
| DNS | Three addresses resolve | 14.27 ms |
| TCP 5432 | All three addresses time out independently | 3,005–3,007 ms each |
| Native PostgreSQL connect | ConnectionTimeout, no SQLSTATE | 9,039.22 ms |
| Native TLS/authentication | No TCP connection established | Blocked |
| Native SELECT 1/schema/user lookup/session creation | Not reached | Blocked |
| HTTPS SQL SELECT 1 with configured database credentials | HTTP 200, ok=1 | 1,662.2 ms, combined read-only query |
| HTTPS account check | Shown account exists and is active | Same combined query |
| HTTPS schema check | users.project_access absent; reqquality_schema marker absent | Same combined query |

The HTTPS checks use Neon's documented SQL-over-HTTP endpoint only as a diagnostic;
the app remains on psycopg/native TCP. The query retrieved booleans only, without
password hashes, tokens, names, or email values. HTTPS success establishes that
the configured endpoint/database credentials work over that transport. It does
not establish native TCP reachability or verify the application's account password.

**The current 503 is caused by failure to establish the native database connection.**
The missing column is a real subsequent schema blocker, not the cause of this
particular pre-SQL timeout. Initialization/migrations, user lookup and token writes
cannot cause the observed wait because they never begin.

## External action required

Restore native outbound TCP 5432 from this computer to the Neon hostname already
configured in backend/.env, with return traffic. The Windows process performing
the connection is C:/Python314/python.exe (started through the project's venv).
The relevant network/VPN/endpoint-security policy must allow that destination and
port; do not disable TLS or globally disable the firewall. If local/network policy
is confirmed to permit it, ask Neon support to investigate native-TCP ingress for
this endpoint, providing the timestamped native timeout and successful HTTPS check.
These observations cannot locate the packet drop to a specific firewall/router or
prove a particular external policy is responsible.

After TCP works, review/apply the existing pending additive schema initialization
before assessing login. Do not merely add a schema-version marker without running
the corresponding migrations. No migration was executed in this investigation.

## Required five-run verification

**0 of 5 successful flows verified.** Login currently fails at checkout, so no
authenticated dashboard, session restoration or logout flow can be completed.
Five failed retries would not satisfy this requirement and were not performed.
The successful five-run sequence, including one backend restart, remains blocked
until connectivity and schema are repaired and an authorized account can sign in.

Evidence: localhost-reproduction.json, native-stages.json,
https-database-facts.json in this directory. Earlier sanitized server stack evidence
is also under ../login-localhost/final-flask-exception.txt. No passwords, URLs,
tokens, data records, security settings or unrelated work were changed.
