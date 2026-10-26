# ReqQuality AI local verification — 25 October 2026

Changes are local and ready for review. No deployment, DNS/hosting change,
production seed, migration, account reset or existing-record mutation was made.
The initial checkout was clean. Actual stack: React 19/Vite 6, Flask 3,
psycopg PostgreSQL with bounded pools, SQLite for local development, ReportLab PDFs.

| Reported issue | Current finding, action and evidence |
| --- | --- |
| Slow/three-attempt login | Not reproduced locally. Existing synchronous submit lock, public-route auth-request suppression, one-connection login, scrypt, cookie tokens, CSRF and role checks were already present and retained. Chrome verified one POST for double submission, first valid submission, invalid credentials, synthetic 503, session restoration and logout. Live PostgreSQL checkout timed out, so hosted-login reliability is **not** declared fixed. |
| Login alignment/recovery | Existing full-width button, feedback space, responsive form and real reset route were already implemented. Checked at 360/768/1366 px; no horizontal overflow or button movement. Keyboard sequence and focus outlines pass. Recovery delivery via SMTP remains unverified. |
| Repeated dashboard sections | Existing route/layout separation and lean dashboard projection already addressed this. Browser checked creation/detail/dashboard navigation; API checks compare current counts and preserve role/project access. No CSS hiding or unrelated dashboard rewrite added. |
| Dashboard usability | Existing database-backed review/case/execution/bug summaries and requirement register retained. Browser validated values against records, version invalidation and mobile widths. Demo records now exercise mixed review states and linked cases without inventing analysis/risk scores. |
| Slow PDF downloads | Existing batched snapshot loading, duplicate-click guard and useful download errors already present. Individual PDF remains 17 SQL statements in the measured fixture; no AI call on export. Added separate Server-Timing stages for data loading, rendering (including cold ReportLab import) and response preparation. Browser verified real export buttons, duplicate guard and explicit retry. Network delivery is not the same as response preparation. |
| PDF layout/missing data | Short 3-page and long 7-page PDFs open, extract and render, including final long-source/review markers. Visually inspected all page sheets plus a full page: no clipping/overlap/blank pages. Found and fixed misleading “Historical analysis” on an unanalyzed edited draft: metadata-only analysis dictionaries now display “Pending: AI analysis has not been saved.” Regression test added. |
| Demo data | No reusable seed command existed. Added explicit SQLite-only command: four labeled clear/ambiguous/incomplete/edge requirements, criteria, linked cases/case versions, two synthetic review records. No AI results, passing executions, accounts or credentials are fabricated. Existing content and edited demo records survive reruns; one transaction, write lock and durable receipt markers prevent duplicates. Invalid accounts, receipt collisions and mid-seed failure roll back. Tested the actual subprocess CLI, including a bogus configured cloud URL that must be ignored. |

Read-only local inspection found `local-development.db`: 1 user, 0 requirements,
0 scenarios; legacy `reqquality.db`: 3 users, 1 requirement, 8 scenarios. Neither
was seeded or migrated. The local database has only its admin; the legacy file
has old role/schema data and is not a suitable seed target without an intentional
upgrade. All seed execution in this task used disposable test databases.

## Verification

- Frontend: **17 tests passed**, production Vite build passed (49 modules).
- Backend full suite: **223 passed** in 326.798 seconds; see
  `audit/current-backend-verified.txt`. Latest seed category normalization and its
  assertion were also verified by the final targeted seed/report run: **18 passed**
  in `audit/current-targeted-final.txt`. Counts overlap; do not add them together.
- Real headless Chrome with real Flask/cookie auth/CSRF and disposable SQLite:
  all three roles, valid/invalid login, synthetic service failure, single double-submit
  POST, zero public auth bootstraps, protected refresh/session persistence, Analyst
  creation/refinement/save/submit, SQE review/case editing, failure/bug/retest,
  history/version invalidation, traceability, matching dashboard totals, PDF/CSV
  download controls, logout and protected 401s passed. **AI mocked in this browser
  run** (explicit failure then success). Widths 360/768/1366; detail at 360.
  Keyboard order: email, password, show password, sign in, recovery, home.
  Zero uncaught JS exceptions, console errors or transport failures. Nine intentional
  navigation/AbortController cancellations recorded separately. HTTP 401/503 responses
  are expected negative-path checks. Evidence: `audit/current-browser-final.txt`,
  screenshots in `audit/current-browser/`.
- **Live Gemini**: model availability and one synthetic smoke generation succeeded
  (2 criteria, 2 scenarios, 2862.8 ms). Three additional real API checks in disposable
  SQLite saved and reopened clear/security/incomplete-performance analysis: HTTP 200,
  approximately 11.11/6.45/7.17 seconds; 3/2/1 scenarios. Source text preserved;
  incomplete behavior retains clarification markers and rejects a Pass execution
  with 409. Evidence: `audit/current-live-ai-final.txt`, `audit/current-live-api.json`.
  This is a small synthetic sample, not comprehensive AI semantic-quality approval.
- PDF extraction/rendering: `audit/current-pdf-results.txt`, `audit/current-pdf/`.
  Three and seven pages respectively; all pages rendered and long markers extracted.
- Read-only live PostgreSQL connection/SELECT probe: **PoolTimeout before acquisition**,
  even with network execution access. No schema initializer or data mutation invoked.
  Evidence: `audit/current-postgres-readonly.jsonl`. No current database query-time
  measurement or hosted login/PDF result is available from that failed acquisition.
- `git diff --check` passed (informational CRLF normalization notices only).

Intermediate failures were investigated, not counted as passes: sandbox temporary
directory/Chrome launch restrictions; standalone seed circular import (fixed and
subprocess-tested); the browser diagnostic initially counted intentional cancellations
as transport errors (now separated); a concurrent-refresh test read the same lazy
login response from two threads (CSRF is now materialized before threading, with
the existing security assertions unchanged). An intermediate 221-test run reported
that harness race; final full-suite evidence supersedes it.

## Measurements and limits

Same existing fixture generators, sequential Flask test clients, initialized
temporary SQLite. Other validation overlapped, so CPU/filesystem scheduling was
uncontrolled. These measure local application request/body collection, not browser
network or deployed cold starts. Login N=3 per run; individual PDF N=20 per run.

| Measurement | Before | Final |
| --- | ---: | ---: |
| Login median | 277.77 ms | 332.09 ms |
| Login individual samples | 267.86 / 277.77 / 295.57 ms | 278.92 / 332.09 / 1079.74 ms |
| Individual PDF median / p95 | 58.00 / 76.61 ms | 54.79 / 72.77 ms |
| First PDF observation | 391.22 ms | 395.99 ms |
| Individual PDF SQL statements | 17 | 17 |

Final warm PDF stage medians excluding the first sample: data 5.3 ms, render
43.3 ms, response preparation 0.3 ms. First render (including ReportLab import)
381.9 ms. Final login password checks took 164–269 ms; the 1079.74 ms outlier
spent 881.97 ms in token persistence on temporary SQLite. No security cost was
weakened and no causal speedup or production-performance fix is claimed. An
intermediate PDF run was slower (95.48 ms median); all evidence remains available.
Sources: `audit/current-login-before.jsonl`, `current-login-final.jsonl`,
`current-exports-before.json`, `current-exports-after.json`, `current-exports-final.json`.

## Commands and handoff

Existing local startup, in separate PowerShell terminals:

```powershell
Set-Location 'C:\Users\ua589\ReqQuality AI\backend'
.\.venv\Scripts\python.exe app.py
```

```powershell
Set-Location 'C:\Users\ua589\ReqQuality AI\frontend'
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Existing `backend/.env.local` selects the local
database for direct development startup. Existing local credential file remains
ignored and its contents are not reproduced here.

From `backend`, this exact verification command creates disposable accounts and
databases and executes the real seed CLI twice, without touching existing data:

```powershell
.\.venv\Scripts\python.exe -m unittest test_seed_demo -v
```

To retain demo records in an intended initialized local database, first provision
the missing active SQA Engineer via the existing admin invitation flow. Select
existing owner/reviewer IDs; for IDs 2 and 3 the command is:

```powershell
.\.venv\Scripts\python.exe seed_demo.py --sqlite .\instance\local-development.db --owner-id 2 --reviewer-id 3
```

Those IDs are examples, not accounts created by this change. The current local
admin is ID 1 and can be the owner; a valid SQA Engineer ID must exist before a
persistent local seed will run. Missing roles intentionally cause a clear failure
instead of fabricated accounts. The command ignores DATABASE_URL, requires an
existing file, does not migrate it and reports created/skipped counts.

Repeat validation from `backend` with `python -m unittest discover -q`; from
`frontend` use `npm.cmd test` and `npm.cmd run build`. For this sandbox, point
`TEMP` and `TMP` at a created workspace-local `audit/tmp` directory if the Windows
temporary-directory permission error recurs. Real browser verification command
from the repository root is `backend/.venv/Scripts/python.exe audit/focused-browser/check.py`;
the harness needs permission to launch local Chrome.

Changed application/test/tool files: `backend/reporting.py`,
`backend/services/reports_service.py`, `backend/seed_demo.py`,
`backend/test_seed_demo.py`, `backend/test_focused_reports.py`,
`backend/test_token_auth.py`, `backend/benchmark_focused_exports.py`,
`backend/verify_focused_pdfs.py`, `audit/focused-browser/check.py`, `README.md`,
`.gitignore` (workspace-only test temp directory), this report and new audit evidence.
No schema migration or deployment configuration change is required.

Remaining external checks: resolve the current PostgreSQL acquisition failure,
then reproduce the hosted three-attempt login with a synthetic hosted account and
request/worker/database timings; measure actual hosted PDF delivery and cold starts;
verify SMTP reset/invitation delivery. Persistent demo seeding also needs a valid
existing local reviewer account. No automatic deployment was performed.
