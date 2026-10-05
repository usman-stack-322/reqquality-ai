# Admin invitations: implementation and setup

The existing React/Vite hash routing, Flask signed sessions, CSRF helpers,
Werkzeug scrypt passwords, and SQLite/PostgreSQL connection adapter are reused.
Public registration is now invitation-only; existing user accounts remain usable.
`SQA Reviewer` records migrate to `SQA Engineer`, retaining user IDs and linked data.
The Admin role is stored as `admin`.

## Changed files

Created: `backend/invitations.py`, `backend/create_admin.py`,
`backend/test_invitations.py`, `frontend/src/pages/Admin.jsx`,
`frontend/src/pages/AcceptInvitation.jsx`, and this document.

Modified: `backend/app.py`, `backend/database.py`,
`backend/migrate_sqlite_to_postgres.py`, `frontend/src/App.jsx`,
`frontend/src/pages/Login.jsx`, `frontend/src/pages/Register.jsx`,
`frontend/src/pages/Home.jsx`, `frontend/src/pages/RequirementDetails.jsx`,
`frontend/src/styles.css`, `frontend/index.html`, `.env.example`, and `README.md`.
No new runtime dependencies are required.

## Database changes

Schema initialization adds `user_invitations` with invited identity, assigned role,
SHA-256 token hash, status, invitation Admin ID, lifecycle timestamps, cumulative
failed attempts, attempt-window timestamps/counts, temporary lock timestamp, and
email delivery status. Pending invitations remain separate from registered users.

A unique index on `lower(users.email)` prevents duplicate accounts and a partial
unique index prevents multiple pending invitations per normalized email. Existing
SQLite role constraints are migrated by rebuilding the users table in a transaction;
PostgreSQL role constraints are updated transactionally. The importer also copies
invitations when present and translates legacy role names. Back up existing databases
before deployment. Legacy PostgreSQL accounts that differ only by email case must be
resolved before the unique index can be created; migration will fail rather than
silently delete or merge those accounts.

## APIs

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/api/admin/invitations` | Admin only |
| GET | `/api/admin/invitations/<id>` | Admin only |
| POST | `/api/admin/invitations` | Admin + CSRF |
| POST | `/api/admin/invitations/<id>/resend` | Admin + CSRF |
| POST | `/api/admin/invitations/<id>/revoke` | Admin + CSRF |
| POST | `/api/invitations/validate` | Invitation token in JSON |
| POST | `/api/invitations/verify-email` | Token + entered email |
| POST | `/api/invitations/accept` | Token + password + verified session + CSRF |

The old `/api/auth/register` endpoint returns 403 and directs users to invitations.
Account acceptance rejects client-supplied identity, role, and lifecycle fields.

## Frontend

`#admin` (also direct `/admin`) shows the Admin Panel using existing card, form, and
button styling. Non-Admins receive a Forbidden page and all management APIs return
403. `/accept-invitation?token=...` opens the public acceptance page. It validates
without disclosing the expected email, prompts for email, then asks for a password
and confirmation. Successful creation offers Sign In. `#register` explains that an
invitation is required. Existing dashboards and requirement review behavior remain.

The token stays in component memory and is removed from the current URL/history
when the acceptance page mounts. Reloading requires reopening the original email
link. Referrer policy prevents the URL being sent to other sites.

## Configuration and provisioning

Use environment variables or ignored `.env` files. The backend loads `backend/.env`
and the root `.env`, without overriding variables already set in the process.

- `REQQUALITY_SECRET_KEY`: persistent, high-entropy session signing secret.
- `SESSION_COOKIE_SECURE=true`: production HTTPS cookies.
- `FRONTEND_ORIGINS`: allowed frontend origins, comma-separated.
- `DATABASE_URL`: optional PostgreSQL URL; unset uses existing SQLite location.
- `INVITATION_FRONTEND_URL`: frontend origin/base URL used to build invitation links.
- `SMTP_HOST`, `SMTP_FROM`: required SMTP host and sender address.
- `SMTP_PORT`: default 587 with STARTTLS, or 465 with implicit TLS.
- `SMTP_SSL=true`: use implicit TLS; otherwise STARTTLS is always required.
- `SMTP_USERNAME`, `SMTP_PASSWORD`: SMTP credentials when authentication is required.

Configure a verified sender and TLS-capable SMTP provider. Emails use the validated,
normalized recipient address with no substitution or alias routing. SMTP acceptance
is recorded as sent; eventual bounces are not tracked. Failures return 502, retain a
pending invitation with `delivery_status=failed`, and allow Admin regeneration/retry.
No credentials, raw tokens, or SMTP exception bodies are logged.

Create the first Admin locally from the repository root:

```powershell
backend/.venv/Scripts/python.exe backend/create_admin.py
```

The command prompts for name, email, and password (password input is hidden).
There is no public Admin registration endpoint.

### Gmail SMTP setup

For a Gmail sender, use `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, and
`SMTP_SSL=false` (the existing sender requires STARTTLS). Set `SMTP_FROM` and
`SMTP_USERNAME` to the sending Gmail address. Enable Google 2-Step Verification,
then create an App Password for ReqQuality AI at
https://myaccount.google.com/apppasswords. Put that App Password in `SMTP_PASSWORD`
inside the ignored `backend/.env` file. Use the 16-character value without display
spaces; the ReqQuality AI login password is a separate credential.

Set `INVITATION_FRONTEND_URL` to the frontend URL that recipients can open.
`http://localhost:5173` is suitable only for testing on the frontend's own computer.
Restart the Flask backend after changing `.env`.

Check configuration from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe backend/check_email_config.py
.\backend\.venv\Scripts\python.exe backend/check_email_config.py --connect
```

The first command reports missing settings without printing credentials. The second
also verifies TLS and SMTP authentication; neither command sends an email. After a
successful connection check, use Resend / regenerate for failed pending invitations.
Existing registered accounts cannot receive a new registration invitation.

Provider references: [Google SMTP settings](https://support.google.com/a/answer/176600)
and [Google App Password requirements](https://support.google.com/accounts/answer/185833).

## Security and lifecycle

Tokens use `secrets.token_urlsafe(32)` (256 random bits); only SHA-256 hashes are
persisted. All expiration uses UTC server time and exactly 24 hours. Lookup checks
accepted, revoked, and expired states before allowing verification or acceptance.
Expired state is persisted on access or Admin listing; a scheduled sweep is not
needed to enforce expiry.

`pending` becomes `accepted` only after atomic account creation, or `expired` at its
expiry, or `revoked` when Admin cancels it. Resending pending/expired invitations
replaces the token hash, resets creation/expiry to a fresh 24 hours, and resets
failed attempts/locks. Accepted and revoked records cannot be resent; create a new
invitation for a revoked record. Previously verified sessions cannot use a new token
without verifying again.

Wrong email attempts increment a cumulative counter, leave the invitation pending,
and never disclose the expected address. Five mismatches within a 15-minute window
cause a 15-minute temporary verification lock, shared across all clients and backend
workers through the database. Locked requests do not increment the counter or extend
the lock. The expiry is never extended. Correct email can be retried after the lock
passes, provided the original invitation is still valid.

Identity verification uses the existing signed session with a separate invitation
CSRF value. Account creation rechecks the token and session proof, reads identity
and role only from the database, and hashes passwords with scrypt. SQLite uses
`BEGIN IMMEDIATE`; PostgreSQL uses invitation row locks. Unique account indexes and
the transaction prevent simultaneous acceptance from creating duplicate users.
Invitation APIs return `Cache-Control: no-store`. Security logs contain invitation
IDs and generic events only.

## Executed verification

Run backend tests from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p test_invitations.py -v
```

29 SQLite backend tests passed, covering the requested API scenarios, concurrent
acceptance, temporary-lock recovery, expiry boundaries, role/email tampering, failed
SMTP delivery/retry, secure SMTP message construction, CSRF, duplicate pending
invitations, preservation of foreign keys during legacy role migration, and clearing existing
sessions on successful account creation.
SMTP tests use mocks; no live email was sent. Non-Admin API denial is tested for
both Analyst and SQA Engineer roles.

The final Vite production build passed (`npm.cmd run build`), Python compilation
passed, and `git diff --check` reported no whitespace errors. Browser verification
used an isolated database and mocked email sender: Admin login/table/form submission
and success feedback, direct `/admin` forbidden pages for Analyst and SQA Engineer,
URL token removal, generic wrong-email feedback, successful retry with correct
email, password setup, successful account creation, return to Sign In, and login to the server-assigned
SQA dashboard all worked. No JavaScript
errors were reported by the browser CLI.

## Deployment checks and improvements

PostgreSQL integration and concurrent acceptance need a run against a disposable
PostgreSQL instance; no PostgreSQL test database was available for this implementation.
Live SMTP delivery needs a configured provider and authorized test recipient.
Configure reverse-proxy/access logs to redact invitation query strings, since the
first HTTP request necessarily includes the emailed token. Use HTTPS in production.
A transactional mail outbox, bounce tracking, pagination, and broader IP-based API
throttling are useful future improvements. Current SMTP delivery occurs inside the
invitation transaction: a database commit failure after SMTP acceptance can result
in an email link that does not work. An outbox would address that failure window.
