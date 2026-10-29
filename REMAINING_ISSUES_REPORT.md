# ReqQuality AI — redesign and verified local demo

## AI Review Assistant — 28 October 2026

Implemented the feedback-based test revision workflow. Per-case and multi-case entry
points open a context-labeled side panel; requirement details also offer coverage
discussion. The backend loads authorized source context, persists conversations and
feedback, validates structured proposals, and keeps saved cases unchanged until
acceptance. Follow-ups use proposal/history context. Accept/reject actions, comparison
previews, retry states, optimistic concurrency, stable case identifiers, immutable
versions, and Pending Review/reapproval use the existing architecture and permissions.

**Verification:** 44 relevant backend tests and 21 frontend tests pass; production build
passes. A Chrome journey using real local authentication/API/isolated SQLite and a
mocked provider passes, including failure/retry, duplicate submission protection,
follow-up, acceptance and context switching with no uncaught exceptions. One live
Gemini request against synthetic isolated SQLite context also returned a validated
proposal without changing saved cases. See `audit/ai-review-*` evidence and
[AI_REVIEW_ASSISTANT.md](AI_REVIEW_ASSISTANT.md) for setup and API behavior.

**Database setup:** schema version 20261028 adds conversation/turn tables through the
existing initializer. This migration was tested on SQLite, not live PostgreSQL;
production records and schema were not changed. Restarting an updated backend against
its configured database invokes the existing additive migration process. No push or
deployment was performed. The older PostgreSQL app-login credential blocker below
remains outside this feature's verification scope.

Updated **26 October 2026**. The isolated demo is running at
**http://127.0.0.1:5174**. Changes remain local; nothing was pushed or deployed.
Existing data, changes and DNS/hosting configuration were preserved. The previous
handoff is archived at `audit/redesign-before/REMAINING_ISSUES_REPORT.md`.

## Findings and implementation

### PostgreSQL follow-up — 26 October 2026

**Current outcome: real PostgreSQL connection/TLS/query/pool checks pass;
existing-account login verification is blocked by missing authorized credentials.**
This supersedes the earlier connectivity blocker recorded below. No application
connection setting, timeout, SSL policy, authentication rule or database was changed.
The earlier TCP timeout did not reproduce with network-enabled execution. Its
historical upstream trigger cannot be proven retrospectively, so no code-fix or
permanent provider-recovery claim is made.

| Check | Actual evidence |
| --- | --- |
| Configuration | WSGI-style import selects `backend/.env`, matches that file, no inherited URL override. Neon pooled endpoint, port 5432, existing `sslmode=require`; no connection-string values emitted. |
| DNS/TCP/TLS | DNS resolved 3 addresses in 140.72 ms. All 3 accepted TCP (110.80–126.22 ms) and certificate/hostname-verified TLS 1.3. |
| Direct PostgreSQL | Connect/authentication 4858.77 ms; read-only SELECT 1 207.49 ms. Schema version 20261023 matches; no missing required columns and no migration performed. |
| Basic pool sample | Initial acquisition 692.75 ms; next acquisitions 0.06/0.03 ms. SELECT durations ~97 ms. These are client-process cold/warm observations, not hosting-cold or login measurements. |
| Repeated/concurrent lifecycle | 6 sequential and 8 concurrent actual PostgreSQL read-only transactions passed, all encrypted. An intentional exception rolled back to IDLE; the following query passed. Final pool: 4 connections, 4 available, 0 waiters, 0 connection errors. No leaked borrowed connection observed. |
| Authorized credential file | Checked the specifically authorized `backend/instance/verified-demo/credentials.txt` in memory. Its 3 local demo account identifiers had **0 matching PostgreSQL accounts**; no passwords, hashes or identities printed. No PostgreSQL password guesses attempted. |
| Configuration account search | README, `.env.example` and account-setup documentation distinguish local credentials from cloud accounts. Common test-account variable names in loaded process/file configuration were absent. `DATABASE_URL` is a database service credential, not an application-user login. No admin was created/reset. |
| Successful application login | **Blocked/not attempted.** No authorized matching PostgreSQL application test account was identified. The ordinary login endpoint writes rate-limit and refresh-token records; it was not used against production under the user's no-production-mutation instruction. SQLite/mock login results are not substituted for this check. |
| Regression/build | **49 relevant backend tests passed**, including pool, auth/token, outage, diagnostics and new probe safety checks; **20 frontend tests passed**; production frontend build passed. No new UI/product features, push or deployment. |

Evidence (sanitized, all under `audit/`): `postgres-followup-diagnosis.json` and
`.txt`, `postgres-followup-pool.txt`, `postgres-followup-lifecycle.json` and `.txt`,
`postgres-followup-credential-config.json`, `postgres-followup-tests.txt`,
`postgres-followup-frontend-tests.txt`, `postgres-followup-build.txt`.

The lifecycle run's initial acquisition was 1412.06 ms, subsequent sequential
acquisitions 0.05–0.11 ms. Concurrent acquisitions were 0.11–983.97 ms while the
pool grew to four connections. Its transaction totals include BEGIN/read-only
setup/SELECT/COMMIT round trips and are not pure SQL or application-login timings.
Production records were not modified: the probes use explicit read-only
transactions and SELECTs, invoke no schema initializer/login endpoint and never
fall back to SQLite. Existing release/cleanup paths were inspected and exercised.

Changes for this focused follow-up only: added opt-in
`backend/verify_postgres_readonly.py`, its two safety regressions in
`backend/test_postgres_readonly.py`, sanitized evidence and this report update.
The tests prove missing PostgreSQL configuration never opens SQLite and raw driver
credentials cannot enter probe output. Existing unrelated changes remain intact.
Reproduce from `backend` with network access:

```powershell
.\.venv\Scripts\python.exe diagnose_login.py --output ../audit/postgres-followup-diagnosis.json
.\.venv\Scripts\python.exe verify_postgres_readonly.py --output ../audit/postgres-followup-lifecycle.json
```

Next requirement for successful PostgreSQL-backed application-login sign-off:
identify an authorized existing test account via a local credential file or named
environment variables, and use a non-production target or explicitly authorized
auth-write scope. Do not put passwords/connection strings in chat or logs. Until
then, connection readiness is verified here; application-login sign-off remains
blocked. This does not establish hosted-login reliability or explain a historical
three-attempt symptom.

| Area | Finding and result |
| --- | --- |
| AI Shorts reference | Inspected source in `C:/Users/ua589/short generation`, existing screenshots and its running public interface on port 5173. Adopted purple accents, neutral surfaces, a 248px sidebar, 65px topbar, compact controls, 12px cards, spacing and split sign-in composition. Reference files and account state were not modified. Hero-only captures exclude credential-bearing areas. This is an adaptation, not a claim of pixel identity or identical backend speed. |
| Complete redesign | Removed the forest/beige palette and scattered literal CSS colors. Shared semantic tokens now cover landing/account screens, both role shells, dashboard, input/editing, AI output, criteria, risks, cases, traceability, review, reports, team, permissions, invitations and settings. Existing layout CSS sits in a lower cascade layer so lazy admin CSS cannot override the theme. Roles/content/features and prior route fixes remain. No fake analytics or new framework/dependency. |
| Light/Dark/System | Added one synchronous `public/appearance.js` controller before CSS/React and an accessible header selector. System default, corrupt/denied storage, OS changes in System only, localStorage persistence across reload/login/logout and cross-tab updates are handled. Switching themes preserves unsaved inputs/navigation and does not call AI or reload forms. Reduced motion is respected. |
| Branding | Supplied mark/proportions/transparency retained, with a white backing where needed. Native 192px asset serves small UI/PDF marks; responsive 512px source handles higher-density displays. All favicon sizes/touch icon return actual images in fresh browser contexts. No default Vite/React branding or existing manifest references remain to update. Application/page titles identify ReqQuality. |
| PostgreSQL | Earlier TCP timeouts are historical evidence. The latest focused follow-up above passed real TCP, TLS 1.3, PostgreSQL authentication, read-only SQL and current-schema checks without changing connection settings. The former timeout did not reproduce; its transient trigger is unproven. Successful application login remains blocked by missing authorized matching credentials. |
| Connection handling | Existing bounded lazy pools and `finally` release were retained. Latest real PostgreSQL checks passed 6 sequential/8 concurrent read-only transactions, rollback after an intentional exception and a subsequent query; final pool was 4/4 available with no waiters/errors. Mock/SQLite regression evidence remains separate. |
| Login | Multiple-attempt symptom was not reproduced locally. Existing synchronous submit lock, refresh safeguards, one-connection login, scrypt, cookies, CSRF and backend roles remain. Both theme browser journeys verify one POST for double submit, first valid login, invalid credentials, synthetic 503, reload/session persistence and logout. |
| Recovery | SMTP errors previously fell through to text implying a link would be sent. Missing configuration now gives the same unavailable response for all accounts; otherwise account-neutral wording explicitly leaves delivery unconfirmed, including runtime SMTP failure. Failed tokens are removed and request receipt uses neutral feedback. No enumeration-revealing delivery result or fake success was added. |
| Dashboard duplication | Prior rendering/routing fixes were already present and remain. Creation/detail pages retain their own content; report/traceability/settings pages do not render duplicated dashboard summaries. Metrics remain database-backed and permission-scoped. |
| PDFs/downloads | Oversized 512px logo inflated small report payloads. Using the kit's native 192px variant reduced the same saved live-demo report from **191,652 to 47,369 bytes (~75%)**. Individual fixture exports still use 17 SQL statements, invoke no AI, retain duplicate guards, filename/MIME checks, retry/error feedback, corrected missing-analysis labels and data/render/response timings. PDFs stay print-friendly and independent of UI theme. |
| Persistent demo | Added explicitly invoked `prepare_demo.py` and `run_demo.py`: separate SQLite, clearly labeled admin/Analyst/SQA Engineer accounts, random passwords/signing secrets, disabled email. The existing seed created 4 samples; rerun created 0/skipped 4 without resetting passwords or edited content. Live verification added requirement 5. Existing local/legacy/production DBs were not seeded or migrated. |

## Reference palette and shared tokens

Canonical definitions: `frontend/src/theme.css`; details: `DESIGN_TOKENS.md`.
Typography follows the reference's DM Sans/Manrope stacks with Inter/system
fallbacks; no remote font package was introduced. Two reference colors were
adjusted for AA text contrast. Status text/icons accompany colors.

| Token | Light | Dark |
| --- | --- | --- |
| Canvas / surface | `#f5f6fa` / `#ffffff` | `#111624` / `#1b2030` |
| Alternate / border | `#f8f7fc` / `#eaecf2` | `#242a3b` / `#394154` |
| Text / muted | `#202438` / `#697184` | `#edf0fa` / `#b5bfd3` |
| Accent / primary fill | `#6b58d9` / `#5d49ca` | `#b4a4ff` / `#705bd4` |

## Actual validation

- Backend full suite: **225 passed**, 344.111 seconds (`redesign-backend-full.txt`).
  That run preceded final small-logo optimization. Final affected report/recovery
  tests: **46 passed** (`redesign-report-recovery-final.txt`). Earlier pool/auth/
  diagnosis/outage/seed checks: **71 passed**. Counts overlap; do not add them.
- Frontend final: **20 passed**, including functional theme initialization,
  corrupt/denied storage, OS following, persistence, cross-tab and token-contrast
  checks. Production build passed. Evidence: `audit/redesign-frontend-tests-final.txt`,
  `redesign-build-final.txt`. The obsolete forest-palette assertion was replaced.
- Real headless Chrome in **both Light and Dark**, disposable SQLite and **MOCKED AI**:
  login → creation → AI failure/retry → edit/save criteria/scenarios → submission →
  SQA review → traceability/manual execution/bug history → individual PDF/CSV controls.
  All three roles, forbidden mutations, reload/session persistence, one login POST,
  zero public auth bootstraps, duplicate export guard and explicit retry passed.
  Theme changes retained unsaved fields and route; preference survived reload/login/
  logout; invalid preference followed System and emulated OS changes.
- Browser coverage includes every existing admin navigation page: dashboard,
  requirements, reviews, team, permissions, invitations, traceability, reports,
  activity and settings. Login/dashboard: 360/768/1366 px; detail/admin pages:
  mobile/desktop. No unintended root horizontal overflow. Keyboard/focus passed.
  **Zero uncaught JS exceptions, console errors or transport failures** in each final
  run. Intentional navigation cancellations and negative-path HTTP responses are
  reported separately. Evidence: `redesign-browser-light-final.txt`,
  `redesign-browser-dark-final.txt`.
- **LIVE AI in the prepared persistent demo:** generated accounts logged in; a
  synthetic owned-ticket requirement was analyzed by real Gemini (~9375 ms), saved
  with 2 criteria, 2 scenarios and Medium risk, submitted and reviewed by a separate
  SQA Engineer. Reopen preserved source/artifacts; Analyst review returned 403;
  traceability and four-page PDF passed (`redesign-prepared-demo.json`). This is a
  synthetic review, not stakeholder approval or execution against an external app.
  No fallback analysis was introduced.
- Actual HTTP path **Vite 5174 → Flask 5000 → prepared SQLite → response** passed
  generated reviewer login, cookies/session, dashboard, traceability, PDF and logout
  with Origin/CSRF handling. No AI or email in this HTTP check.
  Evidence: `redesign-demo-http.json`; report: `redesign-live-demo-final.pdf`.
- Short 3-page, long 7-page and live-demo 4-page PDFs opened/extracted/rendered.
  Visual inspection found readable wrapping, tables, logo headers, page breaks and
  footers; long source/review markers survive extraction. Final optimized live
  renders: `audit/redesign-pdf/final-live-demo-*.png`.
- Before/after desktop/mobile images, including both final themes:
  **`audit/REDESIGN_SCREENSHOTS.md`**. Original UI had no dark mode, so no fictional
  before-dark images are supplied. ReqQuality screenshots use synthetic records;
  reference captures exclude credentials. `git diff --check` passes.

Intermediate failures were investigated, not counted as passes: temporary-directory
and Chrome sandbox restrictions, contrast, legacy auth background, primary-button
text, UTF-8 punctuation and a navigation wait in the browser harness. Initial
hosted checks were not executed during an automatic-approval account-limit error;
after reset, read-only checks completed. In-app reference browsing timed out;
separate read-only Chrome hero capture succeeded.

## Measured performance and limits

Same initialized SQLite fixture generators, sequential requests; login N=3,
exports N=20 with 20 requirements and one detailed case. CPU/filesystem scheduling
and overlapping verification were uncontrolled. These are local observations,
not causal speedup or hosted cold-start claims. No hashing/security cost changed.

| Metric | Starting sample | Final sample |
| --- | ---: | ---: |
| Login median | 361.27 ms | 190.72 ms |
| Individual PDF median / p95 | 324.56 / 380.57 ms | 56.52 / 73.04 ms |
| First observed PDF | 898.86 ms | 325.67 ms |
| Individual PDF SQL statements | 17 | 17 |

Files: `redesign-login-start.jsonl`, `redesign-login-final.jsonl`,
`redesign-exports-start.json`, `redesign-exports-final.json` (all in `audit/`).
Schema/accounts were initialized before these requests; first observations are
not deployed hosting cold starts. Final first PDF rendering includes ReportLab
import (~315.7 ms); later renders were ~43–63 ms. The logo payload reduction is a
deterministic improvement separate from host/run variation.

Actual local proxy sample: login **443.72 ms** (password check 362.2 ms), session
read 23.44 ms, dashboard **36.8 ms** (server 19.9 ms, SQL execute 8.3 ms),
traceability 30.22 ms, PDF server **159.6 ms** (data 6.7, render 147.5, response
preparation 0.6 ms). Earlier HTTP samples were faster; variability is not hidden.
Response preparation is not browser network delivery. No successful remote
PostgreSQL cold/warm/login timings could be measured.

## Demo startup and seed

The demo processes are running on loopback ports 5174/5000. If stopped:

```powershell
Set-Location 'C:\Users\ua589\ReqQuality AI\backend'
.\.venv\Scripts\python.exe prepare_demo.py
.\.venv\Scripts\python.exe run_demo.py
```

In another terminal:

```powershell
Set-Location 'C:\Users\ua589\ReqQuality AI\frontend'
npm.cmd run dev -- --port 5174
```

Open **http://127.0.0.1:5174**. Open the ignored local
`backend/instance/verified-demo/credentials.txt` to get the generated passwords;
they are not printed in logs, screenshots, reports or frontend UI. Signing secrets
are also isolated in that ignored directory. Demo email is explicitly disabled.
AI Shorts owns 5173 and was left running unchanged.

Direct repeatable seed against the prepared database and actual local Analyst 2 /
SQA Engineer 3:

```powershell
.\.venv\Scripts\python.exe seed_demo.py --sqlite .\instance\verified-demo\demo.db --owner-id 2 --reviewer-id 3
```

Preparation created 4 examples, rerun skipped 4; live verification added the fifth.
Seed examples retain unassessed AI/risk fields until explicitly analyzed. Existing
local-development and legacy databases were not seeded/migrated.

Repeat tests from backend: `python -m unittest discover -q`; frontend:
`npm.cmd test`, `npm.cmd run build`. Browser command from root:
`backend/.venv/Scripts/python.exe audit/focused-browser/check.py --theme dark --output audit/redesign-dark-final`
(also run `--theme light`). Sandbox tests use workspace-local TEMP/TMP; Chrome/live
provider checks require their execution/network access.

## Readiness and remaining blockers

**Local demo: ready for review.** Both themes, local roles, persistent demo seed,
live AI/save/review/PDF and real Vite/Flask HTTP path are verified. No new app
dependency or schema migration is required.

**Hosted demo: not signed off.** Read-only checks returned 200 for the `www` page
and API health. Hosted HTML lacks the new appearance script, so these local changes
need a later deployment before hosted visual/theme verification. One apex lookup
failed from this environment; no global domain outage is inferred and DNS was not
changed. Health verifies liveness, not database-backed login. Evidence:
`audit/redesign-hosted-readonly.json`.

The old PostgreSQL diagnosis (`redesign-database-diagnosis.json`) captured TCP
timeouts before TLS; the latest follow-up now establishes real encrypted
connections and verifies read-only pooled lifecycle behavior. The earlier transient
trigger is not proven, and current success does not establish permanent network
availability. No matching authorized PostgreSQL application test account was found,
so successful application login/hosted login sign-off remains blocked. No hosted
accounts, credentials or production records were created/modified.

Local SMTP settings are present but its invitation URL is localhost; hosted
runtime SMTP values were not accessed and must not be inferred from local files.
No email or delivery test was sent. Delivery remains **unverified**. No Git push,
deployment, live seed, live mutation, domain or hosting configuration change occurred.

Changed/new continuation files: shared theme/controller/selector/workspace shell,
BrandLogo, App/main/index, base/admin styles, login/admin/recovery pages and theme
tests; `backend/prepare_demo.py`, `run_demo.py`, `verify_prepared_demo.py`, safe DB
diagnostics, recovery service, report logo asset/path and affected tests; browser
and HTTP audit tools, README, `DESIGN_TOKENS.md`, this report and audit evidence.
Previously existing changes, brand assets and reliability fixes were preserved.
