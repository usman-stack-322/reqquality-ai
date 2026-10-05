# ReqQuality AI

A beginner-friendly starting point for a Requirements Engineering and Software
Quality Engineering platform. It includes a React frontend, a Flask API, and
SQLite/PostgreSQL storage, AI analysis, and session authentication.
Admin-managed invitations assign Analyst and SQA Engineer roles.
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

To enable Gemini analysis, create a `.env` file in the project root (next to
this README) using `.env.example` as a template. Set `GEMINI_API_KEY` and
`GEMINI_MODEL` in that file. `.env` is ignored by Git. Without these settings,
requirement analysis continues with the rule-based analyzer only. Restart Flask
after changing the environment file.

For authentication, set a persistent `REQQUALITY_SECRET_KEY` in the same `.env`
file. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
Create an Admin locally with `backend/.venv/Scripts/python.exe backend/create_admin.py`.
New accounts require an Admin invitation; see [invitation setup](INVITATIONS.md). Set
`SESSION_COOKIE_SECURE=true` when serving over HTTPS. Sessions use HttpOnly,
SameSite=Lax cookies and expire after eight hours.

### Terminal 2: frontend

```powershell
Set-Location "C:\Users\ua589\ReqQuality AI\frontend"
npm install
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` requests to Flask during
development. Flask also enables CORS for frontend requests.

After the first setup, rerun only the backend's `python.exe app.py` command
and the frontend's `npm run dev` command from their respective folders.
Stop either server with Ctrl+C.

## Initial features

- Home page with a brief introduction.
- Requirement input page with typed fields, priorities, and SQLite save confirmation.
- Dashboard placeholder for future summaries and quality indicators.

## API and Database

- `GET /api/health`: returns the API status.
- `POST /api/auth/register`: returns 403; registration now requires an invitation.
- `POST /api/auth/login`: validates credentials and starts a session.
- `POST /api/auth/logout`: ends the session and requires its CSRF token.
- `GET /api/auth/me`: returns the authenticated user's public profile and CSRF token.
- `GET /api/dashboard`: returns requirement, review, risk, type, scenario,
  traceability, recent activity, and high-attention statistics for the dashboard.
- `GET /api/requirements`: returns all saved requirements.
- `POST /api/requirements`: accepts JSON with `title`, `description`,
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
- `POST /api/analyze-requirement`: returns rule-based analysis and adds Gemini
    findings when Gemini is configured and available. The response also includes
    requirement-linked scenarios in positive, negative, boundary, and edge-case
    categories. Gemini generates scenarios when configured; deterministic
    scenarios fill missing categories or provide full fallback when unavailable.

Requirement analysis also returns a deterministic quality risk score from 0 to
100. Ambiguity, missing information, and testability each scale to 100 after
four issues; edge cases scale to 100 after five. These factor scores are weighted
at 25%, 25%, 20%, and 15%. Requirement type contributes 10% (Functional 40,
Non-Functional 80, Business 60), and selected priority contributes 5% (Low 0,
Medium 50, High 100). The weighted total is rounded to the nearest integer.
Scores 0-29 are Low, 30-59 Medium, 60-79 High, and 80-100 Critical. Suggested
priority is Low for Low risk, Medium for Medium risk, and High for High or
Critical risk.

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
requirements; only SQA Engineers can change review status or notes. Authenticated
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
configured for the development server; production hosting is not set up yet.
Flask's debug server is also intended for local development only.
