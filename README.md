# ReqQuality AI

A beginner-friendly starting point for a Requirements Engineering and Software
Quality Engineering platform. It includes a React frontend, a Flask API, and
SQLite/PostgreSQL storage, AI analysis, and cookie-token authentication.
Admin-managed invitations assign Analyst and SQA Engineer roles.
See the [2026-10-10 audit report](AUDIT_REPORT.md) for measured improvements,
validation results and remaining limits. [Cookie authentication](backend/TOKEN_AUTH.md)
documents local HTTP and production HTTPS setup, expiry, CSRF and rate limits.
See the [reliability follow-up](RELIABILITY_REPORT.md) for current verification,
AI benchmark findings, measured performance, and remaining production blockers.
The existing Admin now opens the QA Manager workspace; see
[dashboard setup, metrics and API documentation](QA_MANAGER_DASHBOARD.md).

## Project structure

```text
reqqualityai/
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── styles.css
│       └── pages/
│           ├── Home.jsx
│           ├── RequirementInput.jsx
│           └── Dashboard.jsx
├── backend/
│   ├── app.py
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Run locally (Windows PowerShell)

Install Node.js 22 or newer and Python 3.10 or newer first.
Use two terminals to keep the backend and frontend running together.

### Terminal 1: backend

```powershell
Set-Location "C:\Users\ua589\ReqQuality AI\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The API runs at http://127.0.0.1:5000. Visit
http://127.0.0.1:5000/api/health to check it. The commands use the virtual
environment directly, so activation is unnecessary.

To enable AI analysis, configure `GEMINI_API_KEY` and `GEMINI_MODEL` in
`backend/.env` (loaded first) or the root `.env`. Verify the configured model with
`backend/.venv/Scripts/python.exe backend/verify_gemini.py`; account availability
must be checked rather than inferred from a model name. Restart Flask after changes.
Analysis requires Gemini. Missing configuration, quota/rate limits, timeout and
invalid output return an explicit retryable failure; saving drafts and authentication
work independently. One semantic call produces the complete analysis and linked
scenarios. `GEMINI_TIMEOUT_MS` defaults to 20,000 (bounded to 1,000?25,000), with
one SDK attempt and a 30-second browser deadline.

For authentication, set separate persistent `REQQUALITY_SECRET_KEY` and
`JWT_SECRET_KEY` values of at least 32 bytes in the same `.env` file.
Generate each with `python -c "import secrets; print(secrets.token_hex(32))"`.
Create an Admin locally with `backend/.venv/Scripts/python.exe backend/create_admin.py`.
New accounts require an Admin invitation; see [invitation setup](INVITATIONS.md). Set
`SESSION_COOKIE_SECURE=true`. Production authentication cookies use Secure, HttpOnly and SameSite=Lax.
Direct `python app.py` execution binds to loopback over HTTP, uses separate
local cookie names without Secure, and ignores forwarded headers. WSGI imports
retain HTTPS enforcement and Secure cookies. No certificate setup is needed locally. Access credentials last up to one hour; refresh rotation keeps
the original 24-hour session deadline. PostgreSQL startup rejects missing or
short secrets instead of generating per-worker keys.

### Terminal 2: frontend

```powershell
Set-Location "C:\Users\ua589\ReqQuality AI\frontend"
npm.cmd install
npm.cmd run dev
```

Open http://127.0.0.1:5173. Vite forwards `/api` requests to Flask during
development. Flask also enables CORS for frontend requests.

After the first setup, rerun only the backend's `python.exe app.py` command
and the frontend's `npm run dev` command from their respective folders.
Stop either server with Ctrl+C.

If localhost login reports that the database is temporarily unavailable, see
[the specific login diagnosis](LOCAL_LOGIN_FAILURE.md). Do not reset passwords or
silently switch databases when the connection fails before authentication.

## Initial features

- Home page with a brief introduction.
- Requirement input page with typed fields, priorities, and SQLite save confirmation.
- Dashboards for saved requirement quality risk, review progress and artifact traceability.

Run checks with `npm.cmd test` and `npm.cmd run build` in `frontend`. In `backend`,
install `requirements-dev.txt` and run `.venv/Scripts/python.exe -m unittest discover -v`.
Tests use temporary databases and mocked AI/email; they do not create production records.

## API and Database

- `GET /api/health`: returns the API status.
- `POST /api/auth/register`: returns 403; registration now requires an invitation.
- `POST /api/auth/login`: validates credentials and starts a session.
- `POST /api/auth/logout`: ends the session and requires its CSRF token.
- `GET /api/auth/me`: returns the authenticated user's public profile and CSRF token.
- `GET /api/dashboard`: returns requirement, review, risk, type, scenario,
  traceability, recent activity, and high-attention statistics for the dashboard.
- `GET /api/requirements`: returns a page of authorized saved requirements.
- `POST /api/requirements`: supports a user/payload-bound `Idempotency-Key` header for safe save retries; accepts JSON with `title`, `description`,
    `requirement_type`, and `priority`; optional `analysis` saves risk summary,
    acceptance criteria, and generated test scenarios with the requirement.
- `GET /api/requirements/<id>`: returns one requirement with acceptance criteria
    and its linked scenarios.
- `GET /api/requirements/<id>/report.pdf`: authenticated PDF report for one
    requirement, including analysis findings, linked verification artifacts, and SQA review.
- `GET /api/reports/project.pdf`: authenticated project summary PDF with review,
    risk, type, scenario, traceability, and high-attention summaries.
- `GET /api/exports/requirements.csv`: authenticated CSV export containing the
    documented requirement fields only.
- `PATCH /api/requirements/<id>/review`: atomically updates review status and
    reviewer notes. `PATCH /api/requirements/<id>/review-status` and
    `PATCH /api/requirements/<id>/reviewer-notes` update either field separately.
- `POST /api/analyze-requirement`: AI-only ambiguity, missing-information questions,
  testability, suggested type with explanation, refinement, acceptance criteria,
  qualitative risk/priority with explanations, and criteria-linked test scenarios.
  Generated content remains unconfirmed until human review. New analysis has
  `analysis_mode=ai_only`, `analysis_version=2`, and model provenance. Historical
  saved content remains available and is labelled Historical analysis. Existing
  numeric risk scores are retained; new AI results do not fabricate numeric scores.
- `PATCH /api/requirements/<id>`: Analyst material edits, criteria and clarification
  answers. Requires the latest integer `revision`. Material edits return to Draft,
  clear stale risk/priority assessments and scenario-to-criterion links, and preserve
  the prior requirement and artifacts in history. Unchanged saves retain status.
- `POST /api/requirements/<id>/submit`: Analyst submits Draft or Needs Revision
  (and historical Pending) to Ready for Review. Saved acceptance criteria required.
- `PATCH /api/requirements/<id>/analysis`: Analyst explicitly accepts a complete
  reviewed AI result and its artifacts for the matching saved text and revision.
- `PATCH /api/requirements/<id>/scenarios/<scenario-id>`: SQE revises a scenario and
  its `criterion_codes` while reviewing. Links must belong to this requirement.
- `GET /api/requirements/<id>/history/<history-id>`: authorized historical snapshot.
- `PATCH /api/admin/users/<id>/project-access`: Admin grants/revokes access to the
  existing current project with `{"enabled": true|false}`. Team Management exposes
  this action. Account activation and role permissions remain separate.

Review lifecycle: **Draft ? Ready for Review ? In Review ? Approved / Needs Revision**.
Needs Revision must be resubmitted by an Analyst. Historical Pending records remain
reviewable. All edit, submit, scenario, analysis-acceptance and review writes require
the latest `revision`; stale writes return 409. Only the SQE role with review permission
can decide reviews, and a requirement's author cannot review it even after a role
change. Approval does not automatically confirm AI assumptions or missing facts.

This repository has one project, `current` (ReqQuality AI). Existing users retain their
current-project access by default. Admin controls access; unknown `project_id` values
are rejected rather than mapped to the current project. Revocation blocks requirement
reads/writes, analysis, dashboard, PDF and CSV exports on the backend. No independent
multi-project tenancy model is claimed. Admin/Manager organization management retains
its existing scope. Analysts may collaborate on requirements within the shared project.

`GET /api/requirements` is paginated (`page`, `page_size`, default 50, maximum 100),
returning `requirements`, `total`, `page`, `page_size`. `view=summary` excludes analysis
bodies. Queue filters are `status`, `risk`, `priority` (user priority), and `type`.
Dashboard attention lists are bounded to 20. PDF/CSV exports still cover the project.
Detailed traceability identifies criteria with no scenarios, unlinked scenarios and
invalid links; existence of two artifact sets alone does not establish criteria coverage.

Before deploying, read [implementation, performance evidence and rollout steps](IMPLEMENTATION_REPORT.md).

SQLite is included with Python. The API creates
`backend/instance/reqquality.db` and its `requirements` table automatically.
Existing databases are migrated automatically while retaining the original
`priority` column for compatibility. The requirements table adds user and
suggested priority, risk score and level, review status and notes, and update
time. Acceptance criteria and test scenarios live in linked tables with
`requirement_id` foreign keys. Database files are ignored by Git.

Authentication adds a `users` table with password hashes and roles. Requirements
gain nullable `created_by_user_id`, `reviewed_by_user_id`, and `reviewed_at` fields
so existing records remain intact. Passwords use Werkzeug's scrypt hash and user
responses never include password hashes. Analysts can analyze and create
requirements; only SQA Engineers can record review decisions or notes. Authenticated
write requests require a CSRF token.

## PostgreSQL Production Setup

When `DATABASE_URL` is unset or empty, the backend continues using the existing
`backend/instance/reqquality.db` SQLite file. When it contains a PostgreSQL URL,
the backend uses psycopg and initializes the PostgreSQL schema on first database
access. SQLite-to-PostgreSQL data transfer is never run automatically.

Set the variables listed in `.env.example` through the deployment environment or
secret manager. Production deployments should use a persistent
`REQQUALITY_SECRET_KEY`, invitation SMTP configuration, a provider-issued
`DATABASE_URL`, and `SESSION_COOKIE_SECURE=true` when requests are served over
HTTPS. Do not commit real values.

To import existing local data, first create and back up the PostgreSQL database,
set `DATABASE_URL` in the environment, then run the importer explicitly from the
backend directory:

```powershell
.\.venv\Scripts\python.exe .\migrate_sqlite_to_postgres.py
```

The importer opens the SQLite source read-only, copies users, requirements,
analysis summaries, criteria, scenarios, assumptions, and review data in foreign
key order, preserves IDs and timestamps, and reports imported/already-present
row counts. Identical existing rows are skipped, making a rerun safe; a
same-ID/different-data conflict aborts the transaction. Use `--sqlite` to select
a different source file. The SQLite file is not deleted or modified by the
importer.

For production on a Gunicorn-supported platform, set the environment variables
and start the WSGI application from the project root:

```sh
gunicorn --chdir backend wsgi:app --bind 0.0.0.0:8000 --workers 2
```

The Flask development entry point has debug mode disabled. Put the WSGI server
behind the hosting provider's HTTPS reverse proxy and configure its health check
to use `GET /api/health`.

## Frontend build

From `frontend`, run `npm run build` to create `dist/`. The API proxy is only
configured for the development server; the existing production frontend rewrites `/api` to the Vercel Flask API.
Flask's debug server is also intended for local development only.

## Isolated local database

For this workstation, `backend/.env.local` selects `backend/instance/local-development.db` when running `python app.py`. Cloud configuration in `backend/.env` remains separate; WSGI imports do not load `.env.local`. Local login details are in `backend/instance/local-login.txt` (ignored by Git). Start the backend and frontend with the commands above. The local account is separate from your cloud account. `backend/setup_local.py` initializes the local schema and account without resetting an existing account.
