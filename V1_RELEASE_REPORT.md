# ReqQuality AI V1 release validation

Validation date: **21 October 2026, Asia/Karachi**.

**Decision: HOLD for release sign-off. Do not declare V1 complete.** The isolated SQLite workflow passes, including three real-provider API generations after fixes. Disposable PostgreSQL upgrade/restore and deployment behavior remain unverified. Real output review also found unsupported suggestions that need correction before they can be accepted as business requirements. No production-readiness, zero-bug or AI-accuracy guarantee is made.

No deployment, push, live migration, real-account login, email delivery or real-user record mutation was performed. Application tests use temporary SQLite and synthetic accounts. Workstation database upgrade checks use read-only backups and modify only disposable copies. Existing repository changes were preserved.

## Verified features and complete journey

| Step | Result and evidence boundary |
| --- | --- |
| 1. Authentication by role | Browser signs in as Analyst, SQA Engineer and SQA Admin using synthetic credentials. Real password hashing, cookie sessions and CSRF operate; no authentication bypass in the browser. Backend tests cover invalid login, refresh rotation, revocation, rate limits and authorization. |
| 2. Accessible project | Opens authorized singleton project `current`. Unknown project IDs and revoked project access are rejected. Project creation and two-existing-project membership isolation are **not implemented or claimed**; this is the minimal shared-project V1 defined in the plan. |
| 3. Requirement and AI | Browser creates a requirement, encounters a mocked generation failure, explicitly retries and opens the persisted proposal. Separate real-provider API checks generated, validated and saved proposals on disposable data. |
| 4. Editable refinement/criteria | Browser edits the proposal independently of source text; a regression checks that a trailing newline remains editable. Explicit acceptance saves artifacts as Draft without overwriting the original or approving it. Reload does not generate again. |
| 5. Detailed test cases | AI acceptance creates linked Draft scenarios. Browser creates/edits an additional detailed case and checks stable ID, source version, criteria links and numbered steps. An intentionally delayed case-list response verifies that an old executable revision disappears during edit refresh. |
| 6. Manual failure | Browser records actual result, tester/time, environment/build and evidence reference. Generating cases never executes an external application. |
| 7. Linked bug | Reviews/edits prefill, separate severity/priority and creates a failure-linked bug. Double submission creates one report. |
| 8. Retest/closure | Passing retest is a separate immutable execution and permits closure. An additional failed retest reopens the bug; prior closure and evidence remain after reload. |
| 9. Source edit | Source version advances; previous approval/pass do not carry forward. Analysis/criteria need review, cases become stale, dashboard excludes historical tests from current execution totals, and history remains readable. |
| 10. Current-version review | Browser submits the edited source, then records In Review -> Needs Revision on the **new** version with notes explaining the stale analysis/cases. The earlier version's approval remains historical. This does not pretend the changed source has passed testing. |
| 11. Traceability/reports/persistence | Inspects linked source/criteria/case/execution/bug/review data, compares dashboard totals to records, downloads PDF/CSV and checks reload persistence. Backend tests extract report content and check formula-safe CSV text. |
| 12. Logout | Final logout makes project, dashboard, traceability and CSV endpoints return **401**. Earlier role switches also use normal logout/login. |

Browser evidence: [harness](audit/release-browser/check.py), [result](audit/release-browser/results.txt), [capture](audit/release-browser/dashboard.png). **Browser provider is MOCKED**, two fixture invocations (one failure, one success). Separate real-provider evidence is below. The captured page is after logout; the script verifies workflow pages before that point.

## Automated checks and negative cases

| Check | Result | Evidence |
| --- | --- | --- |
| Initial full backend baseline for this validation | 202 passed, 331.815 s | [log](audit/release-backend.txt) |
| Final full backend suite after fixes | **204 passed, 330.639 s** | [log](audit/release-backend-final.txt) |
| Case/bug/report regressions, including explicit clarification | 28 passed, 59.302 s | [log](audit/release-fixes.txt) |
| AI/schema/proposal regressions | 25 passed, 34.616 s | [log](audit/release-ai-fixes.txt) |
| Frontend automated tests | **17 passed** | [log](audit/release-frontend.txt) |
| Production frontend build | **Passed**, final recorded run 27.32 s | [log](audit/release-build.txt) |
| Complete built-frontend browser workflow | Passed; real Flask/auth/SQLite, mocked model | [result](audit/release-browser/results.txt) |
| Synthetic database-outage browser | Public pages usable; protected gate retained; one session request; zero automatic retries | [result](audit/release-outage-browser.txt) |
| Legacy/workstation upgrade copies | Both copies upgraded twice with all preexisting requirement/criterion/scenario values preserved | [result](audit/release-upgrade-copies.jsonl) |
| Synthetic SQLite backup/restore | Exact graph match, integrity and foreign-key checks passed | [result](audit/release-restore.jsonl) |
| Python compilation / Git whitespace | Passed; existing line-ending normalization notices only | Executed against changed modules and scripts |

The full suite includes backend cross-role/project denial, direct unauthorized requests, CSRF, malformed/bounded input, stale revisions/approvals, signed-result tampering, caller/context/configuration-bound AI reuse, no success persistence after provider failure, timeout/malformed/quota/service failures, pool recovery/saturation/cleanup, safe 503 handling without database fallback, repeated/idempotent submissions, separate retests and historical integrity. Provider and database failure injection is **mocked/synthetic**, not a destructive live outage or a deliberately exhausted provider quota.

Initial browser failures were investigated rather than counted as passes. Two harness issues were corrected: a selector targeted original criteria instead of proposal criteria, and a reload wait matched a separate evidence panel before the case list was ready. App defects found by the expanded/real-provider checks are listed next. Broader-filesystem approval was required for esbuild/Chrome; this is an execution-environment constraint. The earlier account-limit blocker did not prevent this validation's checks.

## Defects fixed during release validation

1. **Real provider results falsely rejected as stale.** Installed google-genai normalizes dictionary schemas in place. Passing the shared response schema changed `schema_hash` during generation. Before the fix, clear/security API calls returned 409 despite no source/context edit. The call now receives a deep copy. A regression invokes the installed SDK's real normalizer with a mocked transport result and checks identity stability. Repeating the same three real-provider API inputs then returned 200 for all three, with persisted Draft artifacts.
2. **Explicitly unresolved generated cases could be completed.** `BLOCKED pending clarification` / `TO BE CONFIRMED` text did not necessarily populate `clarification_notes`. New generated/edited cases now carry explicit markers into that flag; approval and Pass/Fail also check markers in existing rows and linked criteria. Blocked remains available with a reason. This is validation of explicit unresolved markers, not rule-based quality scoring or a guarantee of semantic detection.
3. **Bug status panel could act on a stale revision while reloading.** Writes are disabled during detail refresh, and a successful mutation updates its local revision before refetch. Backend optimistic locking remains intact.
4. **Multiline proposal editing discarded a newly typed blank line.** Draft list fields now keep raw editing text while sending normalized list entries. The browser regression checks newline retention and successful acceptance.
5. **Case edit left the previous executable row interactive during refresh.** A successful case write clears those rows until current revisions arrive, preserving execution-form state on ordinary execution refresh. A delayed-read browser regression verifies this behavior.
6. **Duplicate Admin metric reads.** The Admin projection now shares a request-local input snapshot between its filtered projections. This removes one duplicate group of five metric SELECTs; there is no cross-request data or authorization cache. See the measured limits below.

Changed product files in this validation: `backend/analyzers/llm_analyzer.py`, `backend/services/case_service.py`, `backend/services/integrated_service.py`, `backend/services/management_service.py`, `frontend/src/components/AnalysisDraft.jsx`, `ExecutionBugs.jsx`, `TestCases.jsx`. Regression/test tooling adds or extends `backend/test_ai_workflow.py`, `test_test_cases.py`, `benchmark_release.py`, `verify_release_live.py`, `verify_release_restore.py`, and `audit/release-browser/check.py`. Documentation: this report and `V1_PLAN.md`. Schema remains **20261023**; these fixes introduce no additional schema migration.

## Real-provider verification and remaining output-quality issues

Configured integration: Gemini, installed google-genai **1.75.0**, configured model **gemini-3.5-flash-lite**. Credentials were used internally and never logged. No prompts contained real user requirements.

- Fresh seven-case standalone evaluation: **6 structured successes / 1 transport failure**. Coverage: clear, vague, contradictory, functional, security, missing-performance and specified-performance requirements. [Raw synthetic results](audit/release-live-evaluation.jsonl), [review](audit/release-ai-quality-review.json).
- Separate API checks before the schema fix: clear and security returned false stale-analysis 409; missing-performance returned 200. [Evidence](audit/release-live-api.json).
- After the fix: **three real API calls returned 200**, persisted Draft analyses/cases against their versions, kept source text unchanged, and rejected Pass on explicitly unresolved cases. [Evidence](audit/release-live-api-after.json). Each call used disposable SQLite; the production PostgreSQL path was not exercised.
- The clear case preserved supplied facts but added an unsupported non-librarian denial rule. The functional case unnecessarily questioned an implementation association despite supplied ownership scope; some criteria also redundantly contained AC codes. These remain **model-output quality problems** requiring human correction. Existing prompts already prohibit unsupported rules; schema validation cannot prove semantic compliance.
- Vague/contradictory/missing-performance outputs retained clarification blockers without inventing numeric targets. Specified performance preserved 200 users, 95%, 2 seconds and 30 minutes. This is a limited reviewer assessment, not stakeholder sign-off or an accuracy estimate.
- The security standalone failure yielded no output to grade. Later security API generation succeeded and its persistence/clarification guard passed, but that temporary output was not retained for semantic grading. No claim that the full quality rubric passed is made.

**Release blockers:** obtain stakeholder review/correction of actual outputs, grade the security case, and repeat availability checks in the intended runtime. No unsupported suggestion should be accepted as a business rule merely because it passed JSON validation. Do not hide provider failure behind generated fallback content.

## Performance measurements

Host: **Windows 11 AMD64, 8 logical CPUs; Python 3.14.7; SQLite 3.50.4; Flask 3.1.3; Node 24.21.0; npm 11.19.0**. Request benchmark uses a sequential Flask test client, initialized temporary SQLite, 100 requirements, 199 cases, zero executions/bugs, and 34 synthetic accounts. This dataset measures requirement/case projections; it is not a large execution-history load test. Thirty distinct accounts keep real login limits enabled. Scrypt, sessions, CSRF and authorization are unchanged.

The controlled A/B uses the **same final code and fixture**. The before switch reproduces the former duplicate metric read within each Admin request; after uses request-local reuse. Runs were sequential after suites completed, but OS/host load was not isolated. Original pre-edit diagnostics are also retained in `audit/release-performance-before.json` and `after.json`; they are not substituted for this controlled comparison.

| Request | Samples per run | Before median / p95 ms | After median / p95 ms | First observed before / after ms |
| --- | ---: | ---: | ---: | ---: |
| Login | 30 | 263.67 / 399.00 | 255.04 / 357.23 | 249.02 / 267.65 |
| Analyst/Engineer dashboard | 40 | 9.70 / 16.81 | 9.59 / 14.32 | 21.04 / 21.94 |
| Admin dashboard | 40 | 16.86 / 21.86 | 15.11 / 27.23 | 18.64 / 14.16 |
| Requirement detail | 40 | 6.07 / 12.13 | 6.90 / 10.62 | 5.51 / 11.80 |
| Material source save | 30 | 49.34 / 60.24 | 50.62 / 76.42 | 49.87 / 51.51 |

[Before](audit/release-performance-controlled-before.json), [after](audit/release-performance-controlled-after.json), [reproducer](backend/benchmark_release.py). p95 is the nearest-rank observed sample percentile. Thirty/forty samples support a descriptive sample tail only; confidence and production tail/SLA conclusions are not established. First observations occur **after schema/account setup**, not a true process-cold start. Subsequent observations are included in the median; this is not PostgreSQL connection warm-up or browser network timing.

Admin median decreased 1.75 ms (~10.4%), but its p95 increased. Detail/save also show variation/regression. **No overall latency improvement is claimed.** The deterministic improvement is removal of duplicate reads, with unchanged filtered totals/access checks. Login after-run median password verification was 210.57 ms, connection acquisition 3.69 ms and user query 0.50 ms; scrypt dominates and was not weakened. Material save intentionally snapshots history and invalidates evidence; no correctness work was skipped to lower its latency.

AI is measured separately:

| Measurement | N | Median | Range / outcomes |
| --- | ---: | ---: | --- |
| Real standalone generation, all attempts | 7 | 13,721.4 ms | 8,914.1–19,642.5 ms; six successes, one transport failure |
| Real standalone successful outputs only | 6 | 13,009.5 ms | 8,914.1–18,892.9 ms; excludes failed attempt |
| Real API before schema fix | 3 | 10,299.52 ms | Clear 10,299.52 ms/409; security 8,061.88 ms/409; missing-performance 15,901.74 ms/200 |
| Same real API inputs after fix | 3 | 9,556.98 ms | Clear 18,595.12 ms/200; security 9,227.66 ms/200; missing-performance 9,556.98 ms/200 |

No AI p95 is estimated from these small samples. External generation is variable; this demonstrates the corrected outcomes, **not** a statistically established provider speedup. Mocked browser/test timings are not real-model latency. End-to-end SQL/query deadlines still require provider role settings; frontend cancellation alone does not cancel a server query.

Reproduce the controlled request comparison from `backend`:

```powershell
.\.venv\Scripts\python.exe benchmark_release.py --without-metric-reuse --output ../audit/performance-control.json
.\.venv\Scripts\python.exe benchmark_release.py --output ../audit/performance-current.json
```

Run live provider probes only deliberately; they consume configured-provider quota:

```powershell
.\.venv\Scripts\python.exe evaluate_analysis.py --live --output ../audit/live-evaluation-repeat.jsonl
.\.venv\Scripts\python.exe verify_release_live.py --live --output ../audit/live-api-repeat.json
```

## Database migration, rollback and restore

Current schema version: **20261023**. Existing initialization adds the singleton project, source/proposal history, case revisions/executions, bugs/history and version-bound reviews. IDs and historical links are preserved. No PostgreSQL failure silently selects SQLite. The initializers have separate commits; the whole upgrade is **not one rollbackable transaction**, and there is no tested automatic downgrade.

### SQLite

1. Stop writers and identify the configured `SQLITE_DATABASE_PATH`. Direct `app.py` reads `.env.local`; imported administration tools do not. Do not assume they target the same database.
2. Use SQLite's backup API to a **new** protected backup path, including data in WAL; do not copy only the main file while writers are active. Also retain the matching code revision and protected configuration separately. Never put credentials/backups in public artifacts.
3. Rehearse on a copy first. `verify_v1_upgrade.py` opens workstation sources read-only, backs them up and upgrades temporary copies twice. `verify_release_restore.py` verifies restoration of synthetic source/case/execution/bug/review evidence, SQLite integrity and foreign keys. Both passed in this validation.
4. Apply normal initialization to the intended database only after backup and rehearsal approval. Check record counts/IDs, content versions, linked evidence, login, dashboard and exports before allowing writers again.
5. For rollback, keep the failed database intact, restore the backup to a **new path**, select it explicitly and start the matching previous code/configuration. Reconcile any post-backup writes before switching. The restore rehearsal confirms such writes are absent from the backup; they are not magically recovered. No destructive replacement of a real database was rehearsed.

### PostgreSQL — external release gate

No disposable PostgreSQL target was provided; `postgres`, `initdb`, `docker`, `pg_dump` and `pg_restore` were not found on PATH. The schema/importer/restore were not run against a cloud database. Existing transaction-pooler session advisory locks remain unsuitable for a migration connection.

1. Have the database owner provision a disposable database and a **direct/session** migration connection with appropriate permissions. Use a separate transaction-pooled application URL if desired. Confirm region, TLS and outbound access from the actual runtime.
2. Stop writers for a consistent release backup. Using protected PostgreSQL service/password files (never inline credentials), a DBA can run `pg_dump --format=custom --file=<private-backup-path> --dbname=service=reqquality_backup`. Review backup tool/version compatibility.
3. Restore to a **disposable/new database**, e.g. `pg_restore --exit-on-error --no-owner --dbname=service=reqquality_restore <private-backup-path>`. Do not use a destructive clean/restore against live data to test this report.
4. Run current initialization/importer with the direct migration URL against that restored copy. If migrating SQLite, `migrate_sqlite_to_postgres.py --sqlite <source-path>` reads its source read-only and refuses conflicting destination IDs. Validate all source/version/case/execution/bug/review counts and workflows, then repeat for idempotence. This importer is not a complete session/permission backup or a substitute for `pg_dump`.
5. Configure application-role statement/lock/idle-transaction budgets compatible with the pooler; startup timeout options were previously rejected by Neon. Recycle pools and confirm settings in new connections. See V1_PLAN section 7 for the exact prior observations and budget examples.
6. Roll back by restoring the approved backup into a new database, selecting the matching code/configuration and reconciling post-backup records. Never claim that rolling back only the application binary reverses the schema. Rehearse this before release.

## Environment-variable names (no secret values)

| Purpose | Names and requirements |
| --- | --- |
| Database | `DATABASE_URL` for PostgreSQL, or explicitly selected `SQLITE_DATABASE_PATH` for local SQLite. `DB_POOL_MAX_SIZE`, `DB_POOL_TIMEOUT` configure bounded per-process pooling; account for worker count. |
| Authentication | `REQQUALITY_SECRET_KEY`, `JWT_SECRET_KEY`: separate persistent strong secrets, at least 32 bytes each for PostgreSQL startup. No generated per-worker production keys. |
| AI | `GEMINI_API_KEY`, `GEMINI_MODEL`; optional `GEMINI_TIMEOUT_MS` (SDK bounds 1,000–25,000 ms, one attempt). Model availability and successful generation must be checked. |
| Origins/proxy | `FRONTEND_ORIGINS`; `TRUST_PROXY_HOPS` only for a known trusted proxy topology. WSGI enforces HTTPS and Secure cookies. `SESSION_COOKIE_SECURE` is read during configuration but ultimately set from direct-development versus WSGI mode; it is not a supported production HTTPS bypass. |
| Invitations/recovery | `INVITATION_FRONTEND_URL`, optional `PASSWORD_RESET_FRONTEND_URL`; `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_SSL`, and `SMTP_USERNAME`/`SMTP_PASSWORD` when authentication is required. Live delivery remains unverified. |

Process environment wins. Direct `python app.py` loads `backend/.env.local`, then backend/root `.env` for unset values. WSGI imports skip `.env.local`. `DATABASE_URL` being absent versus explicitly empty matters; PowerShell versions differ in how an empty environment assignment is handled. The isolated commands below set it inside Python deliberately. No frontend secret variable is required; Vite proxies relative `/api` locally, while the existing deployment rewrite must be reviewed separately.

## Reproducible local startup and verification

Run from the repository root, with Python 3.10+ and Node 22+ installed (versions above were actually tested). Install dependencies without changing configuration or runtime data:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m pip install pypdf websockets
Set-Location frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
Set-Location ..
backend/.venv/Scripts/python.exe -m unittest discover -s backend -v
```

PDF render verification additionally uses local-only `pypdfium2` and Pillow. Dependency ranges in backend requirements are broad; the observed versions above are evidence, not a fully pinned production lockfile. Browser harness requires Chrome at the Windows path specified in the script and loopback process/network access.

The safest automated demonstration uses only fixtures and tears down its temporary server/database:

```powershell
backend/.venv/Scripts/python.exe audit/release-browser/check.py
backend/.venv/Scripts/python.exe audit/auth-browser/check.py
Set-Location backend
.\.venv\Scripts\python.exe verify_release_restore.py
.\.venv\Scripts\python.exe verify_v1_upgrade.py
```

For an interactive **new local demo database**, use a new terminal in `backend`. First provision only the new file; the admin password prompt is hidden:

```powershell
$demoDb = Join-Path (Get-Location) 'instance/v1-demo.db'
if (Test-Path -LiteralPath $demoDb) { throw 'Choose a new demo filename; do not overwrite existing data.' }
$env:SQLITE_DATABASE_PATH = $demoDb
.\.venv\Scripts\python.exe -c "import os,runpy; os.environ['DATABASE_URL']=''; runpy.run_path('create_admin.py',run_name='__main__')"
.\.venv\Scripts\python.exe -c "import os,runpy; os.environ['DATABASE_URL']=''; runpy.run_path('app.py',run_name='__main__')"
```

This explicitly selects disposable/demo SQLite; it is **not** an outage fallback. In a second terminal run `npm.cmd run dev` from `frontend`, then open `http://127.0.0.1:5173`. Backend is `http://127.0.0.1:5000`; `/api/health` is liveness, not database/provider readiness. Configure provider credentials privately if real analysis is wanted. Production keys must be persistent; local ephemeral defaults invalidate sessions on restart. Interactive Analyst/Engineer provisioning uses authorized Admin invitations and a configured test SMTP inbox. The automated fixture demo needs no email delivery and does not expose its synthetic passwords in output.

## Short demonstration script

1. Run the built-frontend fixture harness or start a new isolated demo as above. Label model mode clearly: mocked in the automated browser, real only in the separate opt-in provider checks.
2. Analyst opens `current`, saves a source requirement, generates analysis, edits refinement/criteria and explicitly accepts Draft artifacts. Reload and show no new provider request or source overwrite.
3. Engineer edits a detailed case, then records a **Manual execution** failure with observations and build/environment. Open linked bugs, review prefill, edit severity/priority and save once.
4. Move Open -> In Progress -> Ready for Retest. Record a separate passing retest and link it to closure. Show both attempts/history. Optionally record a later failure and reopen.
5. Analyst edits source text. Show new source version, stale analysis/cases and invalidated current approval while old evidence survives. Submit; Engineer reviews the current version and records the appropriate decision/notes (the automated demo uses Needs Revision for stale evidence).
6. Inspect traceability and dashboard definitions, export PDF/CSV, reload, then log out. Confirm protected resources reject access. Do not describe synthetic observations as testing a real external application.

## Release checklist and unresolved gates

- [x] Preserve existing code changes and real data; use isolated accounts/records.
- [x] Final backend/frontend/build checks and complete mocked-provider browser journey.
- [x] Real-provider schema/API persistence checks; explicit failure/clarification behavior.
- [x] Three roles, direct authorization/CSRF/project denials, duplicates, stale revisions and immutable retests.
- [x] Stored-record dashboard/report comparisons, reload, logout and synthetic outage behavior.
- [x] Additive SQLite upgrade-copy and synthetic backup/restore rehearsal.
- [x] Record comparable request measurements without weakening hashing, sessions, limits or authorization.
- [ ] Stakeholder-review/correct unsupported real AI suggestions; grade the security case and repeat provider availability checks in the intended runtime.
- [ ] Disposable PostgreSQL migration/import/restore and concurrency verification using the actual deployment connection mode.
- [ ] Production network access, role-level query budgets, worker/pool budget, persistent secrets, proxy/origin/Secure-cookie configuration.
- [ ] Live invitation/recovery delivery to authorized test inboxes; no mail was sent by this validation.
- [ ] Representative data/history volume, concurrent-user latency, operational monitoring and backup/restore ownership; no production p95 guarantee.
- [ ] Deployment-owner review of the existing frontend backend-origin rewrite and backend WSGI deployment. No deployment or push is authorized here.

These outstanding gates prevent an unconditional V1-complete declaration. Unknown historical versions remain labeled unknown; single-project scope, reference-only evidence and manual external execution remain explicit limits.


## Focused single-project follow-up (21 October 2026)

See `FOCUSED_RELEASE_REPORT.md` for current changes, measured regressions as well as improvements, test boundaries and exact evidence paths. Login now prevents duplicate submissions and public pages avoid competing session bootstrap; the reported production three-attempt login remains unverified. Export reads are batched and snapshot-consistent, dashboard/workflow duplication is reduced, and short/long PDF pagination and responsive layouts are verified on synthetic data. Existing security and AI-only behavior are retained. No schema change, real-user mutation, deployment or push. Prior production/provider/migration sign-off blockers remain; this follow-up does not declare V1 complete.
