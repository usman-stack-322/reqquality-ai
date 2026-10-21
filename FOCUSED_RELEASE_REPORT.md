# Focused single-project reliability and workflow release

Date: 21 October 2026. Local changes ready for review; production sign-off remains pending. No deployment, push, schema change, real-account login or real-user mutation. Initial worktree was clean. Tests use synthetic accounts and temporary SQLite. Live PostgreSQL probes use read-only transactions and no migrations.

## Findings and changes

- Login lacked a synchronous submission lock: rapid submit events could overlap before React disabled the button. A ref lock now guards the complete request. Invalid credentials remain generic 401; service/database errors remain distinct. No new login retry or longer timeout was introduced; hashing, sessions, CSRF, rate limits and backend role checks are preserved.
- Public pages previously bootstrapped `/api/auth/me`, potentially starting refresh requests alongside manual login and competing for cold-start/database capacity. Public routes now issue zero background auth requests. Protected navigation/reload still restores and checks sessions, including navigation from a public page with an existing cookie. Explicit login still waits for any already-running cookie rotation to finish safely.
- **The reported three-attempt production login is not reproduced or declared fixed.** Initial sandbox TCP denial was environmental. A broader read-only probe reached all three Neon addresses via TLS 1.3; connect/authentication 1744.84 ms, SELECT 1 106.62 ms, schema checks 438.85 ms, synthetic nonexistent-user lookup 110.80 ms. Correct schema version 20261023, no missing required fields, no migrations. See `audit/focused-login-connectivity-network.json`.
- Twenty real read-only pooled PostgreSQL checkouts succeeded: first acquisition 1540.58 ms, subsequent 0.02-0.10 ms. The installed psycopg driver preserves pooled connections through its context manager; an initially suspected socket-close defect was ruled out. Existing bounded lazy pools, idle validation, cleanup, failure retirement, deadlines and no-SQLite-fallback behavior remain. The probe performs two SELECTs plus read-only transaction setup/commit, not a login. It does not measure hosting cold starts or authenticate a user. Evidence: `audit/focused-postgres-pool.json`; driver-behavior regression in `backend/test_database_pool.py`.
- Login uses the forest/beige/black palette, aligned full-width Sign in and recovery action, reserved feedback space, focus indicators and responsive spacing. Recovery retains the actual existing reset flow. Real SMTP delivery is unverified.
- Creation focuses on the requirement and editable proposal, then opens the saved requirement for refinement/submission. It no longer fetches/renders the repeated saved-requirement register or repeats the full AI draft below its editor. Detail pages retain one editable case/execution interface and one expandable evidence history, fetched only when opened. Saved AI findings are explicitly suggestions; historical source, approvals and executions remain available. Authoring state and submission confirmation are visible separately from SQA review status.
- Analyst/SQE each have one dashboard/register. Repeated metric/distribution/recent lists and duplicate review filters were removed. The workflow dashboard projection returns the metric data actually used, with matching authorization and totals; the legacy default API remains compatible. Admin retains user/invitation/permission/assignment/settings responsibilities; repeated dashboard cards on traceability/reports pages and the redundant Projects navigation were removed. No bulk operations or additional project features were introduced; no existing data was deleted.
- Exports previously loaded requirement details and versioned graphs per record and loaded project metrics twice. Batching now loads project-scoped evidence once per table in a request-local read snapshot, skips private saved proposals, reuses metrics and releases the connection before document rendering. No report cache is shared across users and no AI is invoked. At 20 requirements, CSV SQL statements fell **306 to 17** and project PDF **319 to 24** (including authorization/connection setup). Increasing records does not increase per-requirement query count. This is a verified structural improvement; actual deployed export speed is unverified.
- PDF metadata tables use the printable width and permit row splitting. Long descriptions/review notes flow as small text blocks; review notes no longer sit inside a huge metadata row. Project reports include saved source/analysis/refinement/criteria, qualitative suggestions and review-needed labels. Header/footer/page numbering, safe escaped content, histories and CSV formula protection remain. Export controls display Downloading, guard duplicate clicks, preserve errors and allow explicit retry.

## Timings and limits

Same fixture generators before/after, sequential Flask test client on Windows, Python 3.14.7, Flask 3.1.3, SQLite 3.50.4. Core fixture: 100 requirements, 199 cases, no executions/bugs, 34 synthetic users. Export fixture: 20 requirements and one detailed case. N per run below; nearest-rank p95 is descriptive only. OS load was uncontrolled and other validation processes overlapped parts of the session; some test-runner elapsed times include long environment delays. Do not interpret test-runner wall time as request latency. First observations are after schema/account setup; these are not process/hosting-cold requests. Final dashboard is the lean projection, matching the retained metrics rather than the removed duplicate lists.

| Request | N per run | Before median / p95 ms | Final median / p95 ms | First before / final ms |
| --- | ---: | ---: | ---: | ---: |
| dashboard | 40 | 10.18 / 12.29 | 16.39 / 17.38 | 11.89 / 31.19 |
| admin_dashboard | 40 | 16.72 / 19.09 | 29.56 / 37.13 | 17.12 / 30.01 |
| detail | 40 | 7.17 / 9.87 | 14.58 / 16.28 | 6.48 / 15.69 |
| login | 30 | 225.22 / 846.45 | 447.92 / 1018.69 | 233.26 / 569.83 |
| material_save | 30 | 37.15 / 47.17 | 80.49 / 274.02 | 34.08 / 84.21 |
| requirement_pdf | 20 | 43.75 / 96.81 | 98.03 / 127.37 | 895.23 / 463.31 |
| project_pdf | 20 | 117.60 / 143.39 | 282.65 / 362.22 | 100.97 / 351.91 |
| csv | 20 | 68.03 / 74.17 | 19.92 / 22.55 | 85.13 / 22.25 |

**No overall speedup or production login/PDF performance fix is claimed.** CSV improved in these samples; final login, dashboard/detail/save and PDFs regressed relative to the initial run. Earlier intermediate export measurements were faster (`audit/focused-exports-after.json`), illustrating host/run variation; they are not substituted for the final numbers. SQL-count reduction and prevention of redundant/duplicate frontend requests are deterministic improvements. Remote query RTT and the old N+1 pattern plausibly contributed to export timeouts, but this is an inference, not a measured production export.

Sources: `audit/focused-before.json`, `focused-after.json` (intermediate), `focused-after-final.json`, `focused-exports-before.json`, `focused-exports-after.json` (intermediate), `focused-exports-final.json`. AI was mocked in this follow-up and no real generation latency/quality claim is added.

## Verification actually run

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -q
.\.venv\Scripts\python.exe -m unittest test_focused_reports -q
.\.venv\Scripts\python.exe -m unittest test_database_pool -q
.\.venv\Scripts\python.exe benchmark_release.py --workflow-dashboard --output ../audit/focused-after-final.json
.\.venv\Scripts\python.exe benchmark_focused_exports.py --output ../audit/focused-exports-final.json
.\.venv\Scripts\python.exe verify_focused_pdfs.py
```

- Broad full suite: **215 passed** (`audit/focused-backend-final.txt`), before the final lean-dashboard/pagination refinements and added driver-context test. After those changes, affected report/integrated/dashboard checks: **12 passed**; pool/driver-context checks: **13 passed**. These subsets overlap existing tests; do not add counts or call this a fresh full 217-test run.
- Existing targeted auth/pool/diagnostic/integrated checks earlier in the session: **32 passed** (`audit/focused-targeted.txt`). Synthetic outage checks remain mocks; no live database disruption was attempted.
- Frontend `npm.cmd test`: **17 passed**; `npm.cmd run build`: **passed**. PowerShell initially blocked `npm.ps1`; `npm.cmd` avoids that policy issue. Esbuild initially failed parent-directory sandbox access; the same commands passed outside that restriction. Environment failures were not counted as application defects.
- From repository root, ` .\backend\.venv\Scripts\python.exe audit/focused-browser/check.py`: real headless Chrome, built frontend, real Flask/password hashing/cookie auth/CSRF, disposable SQLite; **MOCKED AI** (failure then success). All three roles, invalid login, synthetic 503, one POST for rapid double submit, zero public auth calls, protected session restoration, Analyst creation through UI, AI retry/refinement/save/submission, SQE case editing/review/manual failure, bug duplicate guard, passing retest/closure/failed retest/reopening, reload/version invalidation, dashboard totals, actual export buttons and explicit retry, final logout/protected 401 all pass. Result: `audit/focused-browser/results.txt`.
- Login checked at 360/768/1366 px; submission/error did not move the Sign in button. Dashboard checked at the same widths and detail at 360 px with no horizontal overflow. Captures in `audit/focused-browser/`. Current prototype browser selectors use synthetic field labels, not real user data.
- Rendered all pages of short (3-page) and long (7-page) PDFs with PDFium and visually inspected page sheets and representative full pages. No clipping/overlap/blank pages observed; final source/review markers survive extraction. Artifacts: `audit/focused-pdf/`, `audit/focused-pdf-results.txt`. CSV tests check headers/JSON evidence, quote/comma/newline round-trip, formula neutralization and role/project access. Real provider output quality and non-Latin font coverage are not newly verified.
- `git diff --check`: passed apart from informational CRLF normalization notices.

Browser harness failures during refinement were not counted as passes: duplicate scenario removal invalidated an old delayed-refresh text selector; lazy history required opening the correct disclosure. A genuine missing post-submit authoring confirmation was corrected. Final harness uses the current UI and passes.

## Remaining verification and release boundary

1. Reproduce deployed first-login/three-attempt behavior with synthetic hosted accounts, collecting request IDs, Server-Timing stages, backend process-start logs, proxy deadlines and database acquire/query/token timings. Confirm browser cookies/proxy scheme and actual worker/pool configuration in that runtime. No hosting logs/production account journey were accessed here. Do not increase timeouts or add retries as a substitute.
2. Measure production cold and warm login/PDF/CSV separately, at representative record volumes and concurrency; local PDF/login regressions above prevent a blanket speed claim. Inspect database role statement/lock deadlines and host sleep behavior using actual evidence before changing provider configuration.
3. Verify SMTP recovery delivery and real AI availability/semantic quality in the intended runtime. Existing AI-only behavior is unchanged; no fallback or fabricated success is introduced.
4. Re-run the complete final-state suite before release sign-off if a single full-suite result for the final tree is required; affected final checks have passed. Existing PostgreSQL migration/restore and deployment sign-off blockers in `V1_RELEASE_REPORT.md` remain.

No schema migration is required for these changes. Rollback is a code rollback; back up existing data before any later release migration. New probes never print URLs, credentials or private records. Changes remain uncommitted and unpushed.
