# ReqQuality AI — redesign and verified local demo

Updated **26 October 2026**. The isolated demo is running at
**http://127.0.0.1:5174**. Changes remain local; nothing was pushed or deployed.
Existing data, changes and DNS/hosting configuration were preserved. The previous
handoff is archived at `audit/redesign-before/REMAINING_ISSUES_REPORT.md`.

## Findings and implementation

| Area | Finding and result |
| --- | --- |
| AI Shorts reference | Inspected source in `C:/Users/ua589/short generation`, existing screenshots and its running public interface on port 5173. Adopted purple accents, neutral surfaces, a 248px sidebar, 65px topbar, compact controls, 12px cards, spacing and split sign-in composition. Reference files and account state were not modified. Hero-only captures exclude credential-bearing areas. This is an adaptation, not a claim of pixel identity or identical backend speed. |
| Complete redesign | Removed the forest/beige palette and scattered literal CSS colors. Shared semantic tokens now cover landing/account screens, both role shells, dashboard, input/editing, AI output, criteria, risks, cases, traceability, review, reports, team, permissions, invitations and settings. Existing layout CSS sits in a lower cascade layer so lazy admin CSS cannot override the theme. Roles/content/features and prior route fixes remain. No fake analytics or new framework/dependency. |
| Light/Dark/System | Added one synchronous `public/appearance.js` controller before CSS/React and an accessible header selector. System default, corrupt/denied storage, OS changes in System only, localStorage persistence across reload/login/logout and cross-tab updates are handled. Switching themes preserves unsaved inputs/navigation and does not call AI or reload forms. Reduced motion is respected. |
| Branding | Supplied mark/proportions/transparency retained, with a white backing where needed. Native 192px asset serves small UI/PDF marks; responsive 512px source handles higher-density displays. All favicon sizes/touch icon return actual images in fresh browser contexts. No default Vite/React branding or existing manifest references remain to update. Application/page titles identify ReqQuality. |
| PostgreSQL | DNS resolves 3 Neon pooler addresses, but TCP to all 3 times out at ~3 seconds before TLS/authentication. Independent libpq authentication/connect attempt fails after ~9025 ms. This is upstream connectivity, not evidence of pool exhaustion. No increase to waits, weakened SSL, automatic write retry or SQLite fallback was introduced. Safe diagnostic categories now distinguish network timeout, pool checkout deadline and full waiter queue. **External connectivity remains blocked, not declared fixed.** |
| Connection handling | Existing bounded lazy pools and `finally` release were retained. Pool/auth/outage tests cover return on success/error, rollback, idle-socket validation, repeated/concurrent synthetic requests and bounded failure responses. No real PostgreSQL session was established, so live connection-leak/concurrency/cold/warm verification remains blocked. |
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

PostgreSQL diagnosis (`redesign-database-diagnosis.json`) shows TCP timeouts before
TLS. Upstream cause (provider reachability vs network/egress restriction) cannot
be resolved from app code here. Restore connectivity from the intended host, then
measure real pool/concurrent/cold/warm requests and hosted login/PDF delivery.
No existing authorized hosted test-account journey was available; no hosted
accounts, credentials or records were created/modified.

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
