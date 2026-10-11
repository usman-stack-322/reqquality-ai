# Local login diagnosis — 2026-10-11

The sign-in request reaches Flask through Vite's HTTP proxy. The configured
PostgreSQL pool cannot obtain a connection: database DNS resolves to three
addresses, but all three TCP connections on port 5432 time out (about 3,013 ms
each, tested concurrently outside the tool sandbox). This happens before rate
limit queries, account lookup or password verification. The existing backend
logs identify PoolTimeout after 10 seconds. No connection strings, passwords
or tokens are included here.

The exact external reason for TCP failure is not established. Possible network
or database-provider restrictions must be checked by the operator; no firewall,
provider setting, account, role, password or database URL was changed. No fallback
database was substituted. Reducing a timeout would not restore connectivity.

## Implemented changes

- `backend/database.py`: classify PostgreSQL operational failures and pool
  timeouts as database unavailability.
- `backend/app.py`: shared safe HTTP 503 handler with `database_unavailable` and
  `Retry-After: 30`; logs exception class and endpoint without driver messages.
- `backend/middlewares/auth.py`: propagate connectivity errors to that handler,
  retaining the generic handler for unrelated application failures.
- `frontend/src/pages/Login.jsx` and `frontend/src/login-errors.js`: distinguish
  unavailable database/backend, non-JSON proxy failures and throttling; keep
  invalid credentials generic. Network failures show a useful backend message.
- Backend/frontend regression tests and runtime-log ignore patterns.

Production HTTPS enforcement, Secure cookie names and flags, local loopback HTTP,
CSRF validation, rate limits and credentials inclusion remain in place. Both login
and API requests include credentials. Local origins are approved only by the direct
development entry point. Login does not need an existing authenticated CSRF token;
refresh/logout and protected writes do. Authentication cookies are issued only
after successful password verification and a committed refresh-token write.

## Actual observations

| Request through Vite | Result |
| --- | --- |
| Login before fix | 500, generic sign-in error, 10,064 ms, no cookies |
| Login after fix | 503, database unavailable, 10,021 ms, no cookies |
| Health | 200, 41 ms |
| Anonymous session | 200, authenticated false, 21 ms |
| Login from unapproved Origin | 403, 15 ms, before database access |

Timing samples are individual requests, not performance averages. Diagnostic login
used synthetic credentials, not an existing account. Flask was restarted to apply
the handler; Vite served the updated login module and the production build passed.

34 targeted backend tests passed for outages, pool behavior, login, token rotation,
local HTTP, HTTPS enforcement, CSRF, logout and session checks. 13 frontend tests
passed, including error classification and existing credentials/refresh behavior.
All authenticated test flows used isolated temporary SQLite fixtures. Outage tests
confirm existing auth cookies are retained and the session works after recovery.
Two additional tests passed for login throttling across clients, window recovery,
origin rejection, input bounds and SQL safety (36 backend tests total).

**PostgreSQL remains unreachable.** Successful login, dashboard redirect/rendering,
session persistence after reload and logout against the configured database could
not be verified. React still redirects successful SQA Admin/Manager login to
`#admin` and other roles to `#dashboard`; that is source inspection, not a browser
test against PostgreSQL. No browser success or configured-database success is claimed.

Local frontend: http://127.0.0.1:5173/#login

Local backend health: http://127.0.0.1:5000/api/health

Health indicates the API process is alive, not that PostgreSQL is available.
Nothing was deployed.
