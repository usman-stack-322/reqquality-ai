# Access and refresh cookie authentication

## Credentials and expiry

- Access: signed HS256 JWT using PyJWT. One-hour lifetime, with issuer, audience, subject, expiry, not-before, token ID, token type, auth version, token-family ID and signed CSRF claim. Only HS256 is accepted.
- Refresh: 48 cryptographically random bytes encoded as an opaque token. SHA-256 hashes are stored in auth_refresh_tokens; the raw token is never stored in the database. High-entropy random tokens do not need password-style slow hashing.
- In production, both credentials travel only in host-only Secure, HttpOnly, SameSite=Lax cookies. They are never returned in JSON or stored in localStorage/sessionStorage.
- Access cookie: __Secure-reqquality_access, path /api/.
- Refresh cookie: __Secure-reqquality_refresh, path /api/auth/.
- The refresh family expires 24 hours after login. Rotation keeps the original deadline; it does not extend the session indefinitely. An access token issued near that deadline is capped at the remaining family lifetime.

A JWT's signature and expiry can be verified without server-side session storage. Protected endpoints still check the account, auth_version and an active token family in the database, so disabled accounts, changed roles/passwords and logout take effect immediately. This is intentionally not a completely database-free authorization system. Flask session cookies no longer authenticate users; invitation email verification keeps its separate temporary session.

## Rotation and revocation

POST /api/auth/refresh requires the refresh cookie and X-CSRF-Token. The server locks the stored refresh row and atomically issues a successor and revokes the previous token. Reusing an already-revoked refresh token revokes its entire family and requires a new login. SQLite uses BEGIN IMMEDIATE; PostgreSQL uses SELECT FOR UPDATE. Failed writes roll back without issuing new cookies.

POST /api/auth/logout requires CSRF, revokes the current family and deletes both cookies. It also works after the access token expires if the refresh cookie remains. Other device/browser families stay logged in. Password changes/resets and account role/active-status changes revoke all refresh tokens for that account.

Old refresh hashes are retained for reuse detection through the family deadline. Operators may periodically delete rows whose expires_at epoch timestamp is in the past, outside the request path.

## CSRF and frontend behavior

Cookie authentication still needs CSRF protection. HttpOnly prevents JavaScript reading the authentication credentials; it does not prevent a browser sending cookies on an unwanted request. The official [Flask cookie authentication guidance](https://flask-jwt-extended.readthedocs.io/en/stable/token_locations.html#cookies) describes this distinction.

Login and refresh return csrf_token, user information, and no authentication credentials in JSON. GET /api/auth/csrf safely recovers the CSRF value from the existing access or refresh cookie. The CSRF value is bound to the signed access claim and current refresh credential.

frontend/src/api.js keeps only CSRF in memory, supplies credentials: include, obtains one refresh per batch of concurrent unauthorized requests, and retries the denied request once. It also recovers from an explicit csrf_failed rejection before retrying once. Permission failures are not retried. Public invitation requests retain their separate invitation CSRF token.

## Postman

Use this local base URL:

    http://127.0.0.1:5000

Local direct execution uses HTTP without certificates. Keep certificate validation enabled. Production must use a trusted HTTPS certificate.

1. POST /api/auth/login with the existing email/password JSON. Leave Postman's cookie jar enabled.
2. Save csrf_token from the response. Tokens are in Set-Cookie and must not be copied to Authorization or JSON.
3. Send X-CSRF-Token on protected POST/PATCH requests, including logout and refresh.
4. POST /api/auth/refresh needs no body. Save the NEW csrf_token from its response; both cookies rotate.
5. POST /api/auth/logout needs no body and deletes both cookies.
6. If you lose the CSRF value, call GET /api/auth/csrf and use its csrf_token.

Attach this Postman post-response script to login, refresh and CSRF bootstrap:

    const data = pm.response.json();
    if (data.csrf_token) pm.environment.set('csrf_token', data.csrf_token);

Set the request header to:

    X-CSRF-Token: {{csrf_token}}

Production WSGI rejects plain-HTTP login/refresh with 426. Existing session-based logins must log in again after migration.

## Local HTTP and production HTTPS

From backend, run `.venv\Scripts\python.exe app.py`. From frontend, run
`npm.cmd run dev`. Open http://127.0.0.1:5173; Vite proxies `/api` over HTTP
to http://127.0.0.1:5000. The backend binds only to loopback, accepts only
localhost/127.0.0.1 Host headers, and ignores forwarded headers in this mode.
Local access/refresh cookies use `reqquality_access` and `reqquality_refresh`,
with the same paths, HttpOnly, SameSite, CSRF, expiry and rotation rules, but
without Secure. Invitation sessions also work over local HTTP.

Only direct execution selects this mode; importing `wsgi:app` keeps HTTPS
login/refresh enforcement, Secure cookies and their `__Secure-` names.
No environment variable disables production cookie security. Local certificate
files are unused and certificate validation does not need to be bypassed.

PyJWT and cryptography are in requirements.txt. A persistent, generated JWT_SECRET_KEY was added to this workspace's ignored backend/.env without printing its value. Configure a separate strong JWT_SECRET_KEY of at least 32 bytes in each deployed environment and share it across that deployment's workers. Changing it invalidates existing JWTs and CSRF values; users must log in again.

If TLS terminates at a trusted reverse proxy, configure TRUST_PROXY_HOPS to the exact number of trusted forwarded-protocol hops. Default is 0. Do not enable forwarded-header trust for arbitrary direct clients. Configure FRONTEND_ORIGINS for the deployed HTTPS frontend.

The existing PostgreSQL connection pool remains in use. Successful login now also persists a refresh hash transactionally; access/refresh tokens are an authentication change, not a guarantee of lower password-login latency.

## Audit improvements (2026-10-10)

Public home/login pages render while session recovery runs. Protected routes retain
an authentication gate with a skeleton. Session bootstrap is shared across React
StrictMode effect replay; late bootstrap responses cannot overwrite a successful
login. Anonymous `/me` responses include `refresh_available: false` when no
refresh cookie exists, avoiding an unnecessary CSRF bootstrap. Cookie expiration
and server authorization remain authoritative.

Session permission lookup reuses its user-lookup connection. API responses now
include `Server-Timing` for `request`, `db_connect` and `db_execute`; login also
reports password, token and rate-limit stages. `db_connect` includes initialization
on cold connections; `db_execute` excludes initialization and does not include
fetch/serialization/commit/connection-close time. Request time includes those
stages. Timings do not include browser or proxy transit.

Rate limits use atomic, database-backed 15-minute fixed windows across workers:

| Action | Limit |
| --- | --- |
| Login | 100 requests/IP and 10 requests/IP + normalized email |
| Forgot password | 20 requests/IP and 5 requests/IP + normalized email |
| Reset password | 20 requests/IP, before password hashing |
| Public invitation actions | 60 requests/IP, in addition to invitation mismatch locks |
| Create/resend invitations | 30 requests/authenticated administrator |

Limited responses return HTTP 429 and `Retry-After`. Successful and failed
attempts count; only keyed hashes of identities are stored. Counters are separate
from invitation tokens, so throttling never revokes an invitation. The existing
five-mismatch temporary lock, 24-hour expiry and single-use transaction remain.
Prune obsolete `request_limits` rows outside request handling using their
`window_start` epoch value; no user or requirement rows need removal.

PostgreSQL deployments must explicitly configure both persistent secrets with at
least 32 bytes; startup rejects missing or short values instead of generating
different keys per worker. Development without PostgreSQL keeps its existing
temporary-key fallback. `TRUST_PROXY_HOPS` now covers forwarded client IP as well
as HTTPS scheme: set it only for the exact trusted chain that overwrites both
headers. Default 0 ignores forwarded headers. IP limits may affect users sharing
a NAT/proxy; review deployment topology before release.

Cookie-authenticated API writes retain CSRF checks, and writes with an explicit
unapproved `Origin` are rejected. Configure `FRONTEND_ORIGINS` to include the real
frontend origin when it differs from the API host. All API responses use
`no-store`, `nosniff` and `no-referrer`. Request bodies are capped at 1 MB; new
titles at 200 characters, descriptions/reviewer notes at 20,000. Existing stored
content is not truncated or rewritten.

The workspace still contains one shared project. Signed-in roles can read its
requirements and exports; reviewer assignment is a workload aid, not an access
boundary. Analyst creation and Engineer review remain subject to fresh role
permissions. The `admin` role is displayed as SQA Admin and keeps management and
inspection access. Its static permission metadata lists all permissions, but
creation/review routes reject that role; the UI now respects those effective
restrictions. The legacy configurable Manager role remains supported.
