# ReqQuality AI

## FYP proposal presentation — 4 November 2026

The current team-confirmed proposal is [here](docs/FYP_PROPOSAL_2026-11-04.md).
Use the [presentation outline and demo script](docs/FYP_PRESENTATION_2026-11-04.md)
and [readiness report](docs/FYP_READINESS_REPORT.md) for rehearsal and limitations.
These supersede the older solo-project/unconfirmed-supervisor documentation.
Current AI analysis is Gemini-based with human review; there is no active rule-based
analysis engine or successful fallback on AI failure. Historical provenance is retained.
Do not start the updated backend against production for presentation rehearsal;
use the explicit isolated demo configuration.

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
  `analysis_mode=ai_only`, `analysis_version=4`, and model provenance. Historical
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

### Verified demo and appearance

The interface uses the inspected AI Shorts visual reference with shared tokens in
`frontend/src/theme.css`. The header's Theme selector offers Light, Dark and System.
Preferences stay in this browser (`reqquality-appearance`); switching themes keeps
the current page and unsaved form values. PDFs retain their separate print styling.

To prepare a separate, persistent demo with generated local credentials, from `backend`:

```powershell
.\.venv\Scripts\python.exe prepare_demo.py
.\.venv\Scripts\python.exe run_demo.py
```

Preparation is explicitly invoked and idempotent. It uses
`backend/instance/verified-demo/demo.db`, never DATABASE_URL, and creates clearly
labeled local admin, Analyst and SQA Engineer accounts with random passwords.
Credentials and local signing secrets remain in the ignored demo directory;
open `backend/instance/verified-demo/credentials.txt` locally to sign in. Rerunning
preparation preserves account passwords and edited demo records. Demo email is
disabled. No production accounts or records are created.

In another terminal, from `frontend`:

```powershell
npm.cmd run dev -- --port 5174
```

Open `http://127.0.0.1:5174`. Port 5173 may belong to the read-only AI Shorts
reference and should not be stopped. ReqQuality's Vite proxy uses the demo backend
on loopback port 5000. The existing local-development startup below remains separate.

The existing seed can also be invoked directly against this prepared database:

```powershell
.\.venv\Scripts\python.exe seed_demo.py --sqlite .\instance\verified-demo\demo.db --owner-id 2 --reviewer-id 3
```

These IDs are established by fresh demo preparation. No AI is invoked by seeding,
navigation or export. AI generation is explicit and uses the configured Gemini
provider. `verify_prepared_demo.py --live --output ../audit/redesign-prepared-demo.json`
is an opt-in synthetic local flow that uses provider quota and writes only demo
records. Tests and browser fixtures that mock AI are documented separately in
`REMAINING_ISSUES_REPORT.md`.

For this workstation, `backend/.env.local` selects `backend/instance/local-development.db` when running `python app.py`. Cloud configuration in `backend/.env` remains separate; WSGI imports do not load `.env.local`. Local login details are in `backend/instance/local-login.txt` (ignored by Git). Start the backend and frontend with the commands above. The local account is separate from your cloud account. `backend/setup_local.py` initializes the local schema and account without resetting an existing account.

### Explicit demo data

`backend/seed_demo.py` adds four clearly labeled requirements (clear, ambiguous,
incomplete and edge case), linked manual criteria/cases, case versions and two
synthetic review records. It does not call AI, invent analysis/risk scores, create
accounts, reset passwords or record passing executions. Samples still require
analysis and human review. Reruns preserve existing samples, including edits.

Select an **existing initialized local/demo SQLite file** and existing active
accounts with project access: an Analyst (or admin) owner and an SQA Engineer
reviewer. The command never uses `DATABASE_URL`, never initializes/migrates a
database and refuses a missing file. Provision missing accounts through the
existing administrator invitation flow before seeding; the workstation's local
database may contain only its administrator. No production seeding runs on startup.

From `backend`, with the chosen account IDs (the following IDs are examples):

```powershell
.\.venv\Scripts\python.exe seed_demo.py --sqlite .\instance\local-development.db --owner-id 2 --reviewer-id 3
```

The JSON result reports preexisting requirement count and created/skipped samples.
Invalid accounts abort without inserting content. To verify the command safely,
including its subprocess invocation, rerun preservation, relationship/dashboard
checks and transaction rollback, use disposable test databases:

```powershell
.\.venv\Scripts\python.exe -m unittest test_seed_demo -v
```

Individual PDF responses expose `report_data`, `report_render` and
`report_response` in `Server-Timing`, alongside database and total request timings.
Response preparation is measured server work; actual network delivery must be
measured in the browser. No SQL text or record contents are added to these headers.

## Versioned AI analysis

The supported project is `current`. It now has persisted context, editable by SQA
Admin under Settings. `GET /api/project` reads context; `PATCH /api/project` requires
Admin, CSRF and the latest project `revision`. Other project IDs are denied.
This is a minimal single-project structure, not multi-project tenancy.

For saved requirements, `POST /api/analyze-requirement` requires
`requirement_id` and `requirement_revision` alongside matching saved input. Save
source edits first. Generation persists a separate editable proposal without
changing source text or review status. Opening the detail page reads that proposal
without another provider call. Explicit acceptance supports validated
`analysis_edits`, preserves the original signed output and keeps review status
Draft. Type, missing facts, clarification questions, refinement, criteria and
qualitative risk/priority suggestions all require human review.

Reuse is bound to user/project, source version, clarification answers, project
context revision and generation configuration. Changes invalidate acceptance and
reuse. Failures preserve input, return a retryable error and never become saved
successful analysis; no rule-based fallback is used.

Schema version 20261020 adds the current project and proposal storage without
rewriting existing requirement bodies, IDs or historical analysis. Rehearse cloud
upgrades on a disposable database first; see [V1_PLAN.md](V1_PLAN.md), section 8.
The seven-case opt-in real-provider evaluation and its limitations are documented
in [backend/evaluation/README.md](backend/evaluation/README.md).

### Detailed test cases, Manual execution and failure-linked bugs

Requirement details now include detailed cases, case-version history and **Manual
execution**. Existing scenario IDs/codes are preserved. Engineers with review
permission can create/edit cases; `execute_test_cases` separately authorizes new
execution records. Each retest preserves earlier observations and their source
snapshot. Pass/Fail requires an actual result; Blocked requires a reason.

In a failed execution's history, select **Bugs for execution**, review existing
bugs, then **Create bug from failed execution**. Review/edit the prefilled details
before saving. SQA Admin and Engineers with `manage_bugs` manage reports; Analysts
read them. Severity and priority are independent. There is no Developer role,
file upload, automatic external test execution or automatic bug closure.

The lifecycle is Open -> In Progress -> Ready for Retest -> Closed. Closure needs
a linked later passing retest of the same case after its latest failure, or a
documented resolution reason. A new linked failed retest can reopen a ready/closed
bug. History retains each change and previous evidence. Evidence references are
plain text, never automatically fetched.

Schema **20261022** additively extends scenarios and introduces case versions,
executions, bugs and bug history. Reanalysis archives cases instead of deleting
their links. Back up and rehearse PostgreSQL upgrades using a direct migration
connection before rollout; no live migration was performed here. See sections
9–10 of [V1_PLAN.md](V1_PLAN.md) for verification and remaining release blockers.

### Version-bound review and integrated reports

Requirement details include **Requirement versions, traceability and SQA review**.
Choose a source version to inspect its acceptance criteria, case snapshots, Manual
executions, failure-linked bugs and recorded reviews. Opening this view never calls
the AI provider. Refresh evidence explicitly after adding an execution or changing
a bug in another panel.

Material edits preserve the previous source/evidence and invalidate the current
approval, analysis and case applicability. Criteria are marked for review; stale
cases must be explicitly rebased before execution. SQA review uses Pending,
In Review, Approved and Needs Revision. Authoring Draft/Ready for Review states
remain separate. A legacy approval without a verified reviewed version is Pending
until an authorized non-author Engineer starts and records a new review.

Dashboard definitions are displayed beside the metrics. Linked cases measure
recorded criterion links, not complete coverage. Latest results use exact current
case revisions; Not Run/Blocked never count as passed. Non-Closed bugs include
Ready for Retest and historical failures. Admin dashboard metrics respect its
requirement filters. Use **Refresh dashboard / Retry** to reload stored data.

Existing requirement/project PDFs now include versioned cases, executions, bugs
and reviews. The requirements CSV preserves its initial columns and adds scalar
version/review fields and JSON columns for linked histories. CSV formula escaping,
PDF text escaping, project authorization and no-store downloads remain enforced.
Schema **20261023** adds `requirement_versions`, `requirement_reviews` and reviewed
version/criteria review flags. No live migration is performed by verification.
See section 11 of [V1_PLAN.md](V1_PLAN.md) for evidence and remaining release checks.
