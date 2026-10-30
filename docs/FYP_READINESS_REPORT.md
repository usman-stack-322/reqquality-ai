# FYP presentation readiness — 4 November 2026

Reviewed **30 October 2026**, for **ReqQuality AI: AI-Powered Requirements & Software
Quality Engineering Platform**. Supervisor **Maam Amina Ghulam Rasool**. Team:
**Muhammad Usman (28104), Hassaan Majid (27916), Hassan Shabbir (27915)**.

**Local prototype flow verified. Hosted login is not signed off.** Real user data,
production schema, hosting, DNS and GitHub were not changed. All write-based verification
used disposable SQLite and synthetic users/requirements. The configured PostgreSQL
diagnosis used a raw read-only connection path, bypassing application initialization.

## Screenshot acceptance and current findings

| Required issue / supplied evidence | Finding, change and verification |
| --- | --- |
| 29 October `111953` login screenshot: timed-out request, large feedback gap, plain recovery link | Current local valid credentials succeed on one attempt. Existing submit/refresh guards remain; browser double-submit emits one login POST. Login spacing tightened, Sign In explicitly aligned and centered to the input width, recovery link styled with a 44px target. Browser checks invalid credentials, synthetic 503, retry, keyboard focus/order and widths 360/768/1366. Hosted timeout remains unresolved; see network blocker below. |
| 29 October `152358` screenshot | This is AI Shorts Studio, not ReqQuality AI. Its neutral/purple/sidebar styling is a reference. Its insufficient-source research error is not a ReqQuality backend error; no unrelated source-retrieval logic or AI Shorts files were changed. |
| Dashboard repeated across pages | The current router already separates dashboard, creation and detail rendering. Browser checks explicitly assert no `.requirements-dashboard` on input or detail. Manager pages render their own content. No new dashboard duplication fix was needed. |
| Confusing Analyst/SQA dashboard | Added role-specific next-step workflow, visible requirement status **and** SQA decision, explicit User priority versus AI suggestion, Draft and Ready for Review filters, and corrected the broken `?` pagination separator. Traceability, approval and manual execution are explained as separate concepts. Backend permissions were preserved. |
| Fast case approval immediately after AI acceptance | A final browser run reproduced a stale row remaining clickable during refresh, leading to a correct backend 409. Acceptance now clears old interactive cases while fetching saved versions. The browser regression deliberately delays case reads and verifies the old row cannot be used, then completes separate case approval. |
| Slow PDF/CSV | Existing bounded query batching, no-AI export path, small report logo and download duplicate/retry guards remain. Current small exports do not reproduce a long application delay. The first PDF's renderer import dominates the measured cold request; subsequent exports are faster. Added data/render/response timings to project PDF and CSV, matching the individual PDF instrumentation, rather than hiding the cost or claiming a speedup. Files reopen and contain source, latest case and approval evidence. Hosted export latency cannot be verified while its database path is unreachable. |
| Incorrect report value found during visual QA | Project PDF represented absent numeric risk as `0/100`. Fixed the summary to retain null and display **Not assessed (no numeric scores recorded)**; genuine historical zero still displays `0.0/100`. New regression covers both. No numeric scoring engine or invented measurement was added. |
| Live domain / database errors | `www.reqqualityai.site` returned HTTPS 200. Bare `reqqualityai.site` failed DNS resolution from this environment. Configured PostgreSQL DNS resolved three addresses, but all timed out connecting to port 5432; no TLS/authentication session was established. No SSL downgrade, password reset, silent SQLite fallback or DNS change was made. |

The exact original screenshots are the user-supplied files in
`C:/Users/ua589/OneDrive/Pictures/Screenshots/`. Their account content was not copied
into new evidence. New screenshots use synthetic fixtures in
`audit/fyp-2026-11-04/browser-light-final/` and `browser-dark/`.

## Measured timings and practical limits

These are single-machine, small-dataset observations, **not a controlled before/after
performance study or a hosted SLA**. Source and AI output size differ between runs;
concurrent tests and filesystem load also vary. No reduction in secure password hashing
was made. No claim that the historical three-attempt symptom is permanently fixed.

| Measurement | Observed result | Evidence |
| --- | --- | --- |
| Initial isolated login baseline | 3/3 valid requests HTTP 200, 255–295 ms; password verification 201–227 ms | `login-baseline.txt` |
| First mocked full rehearsal | Analyst 391 ms; SQA 281 ms, each one attempt | `flow-mocked/result.json` |
| Live-provider full rehearsal | Analyst 498 ms; SQA 550 ms, each one attempt; analysis ~8.8 s | `flow-live/result.json` |
| Mocked export baseline | First requirement PDF 1110 ms, with 1097 ms in render/import; later PDFs ~57 ms; CSV 9–12 ms | `flow-mocked/result.json` |
| Live-generated report samples | Requirement PDFs 97–301 ms, CSV 10–13 ms; more generated cases/history than mocked baseline | `flow-live/result.json` |
| Final local run | Detailed request/data/render/response measurements are saved for each of three export samples; all succeed | `flow-final/result.json` |
| PostgreSQL path | DNS ~148 ms; 3 TCP attempts each ~3 s timeout; direct authentication attempt ~9 s timeout | `postgres-readonly.json` |

All paths in this table are relative to `audit/fyp-2026-11-04/`.
Report import cost remains visible. Preflight a saved report before presenting; do not
describe warming the local process as proof of faster production exports.

## End-to-end verification

Both mocked and **real Gemini** disposable-database rehearsals passed:

1. Valid Analyst and SQA logins, each one submission.
2. Analyst creates source requirement; AI analysis is explicitly accepted without
   overwriting original requirement text.
3. Linked criteria and generated scenarios persist.
4. AI Review Assistant loads server context and proposes a revision; saved case remains
   unchanged until acceptance. Acceptance saves Pending Review.
5. Separate SQA case review and approval; Analyst requirement submission; independent
   SQA requirement approval. Analyst approval attempt returns 403.
6. PDF/CSV export, reopening/parsing and expected-content assertions; version and review
   history remain linked. Manual execution remains Not Run in this basic rehearsal.

The browser journey uses actual Chrome, built frontend, Flask auth/API and temporary
SQLite with **mocked** providers. It also tests generation failure/retry, proposal edits,
case revision acceptance and separate approval, refresh/logout, no repeated dashboard,
download retry/duplicate guards, mobile layouts and recorded execution/defect histories.
Any Pass/Fail in that separate regression journey is a synthetic fixture observation,
not execution of an external application.

## Checks and evidence

- **81 backend tests passed** for login performance, token auth, database pool/outage,
  exports, integrated reporting, AI Review Assistant and analysis. `backend.txt`.
- An additional export-stage timing test passed (`report-timings-test.txt`). A final
  affected report/integration run after the null-score fix passed **19 tests** (`reports-final.txt`).
  Counts overlap; do not add them as independent test totals.
- **22 frontend tests passed**, including role next-step guidance. Production frontend
  build passed (`frontend.txt`, `build.txt`).
- Light and dark full browser rehearsals passed, including separate case approval,
  one POST for double submit, no uncaught exceptions/console errors/transport failures.
  Expected test-induced 401/503 responses and canceled stale requests are recorded,
  not mislabeled as unexplained live errors (`browser.txt`, `browser-dark.txt`).
- PDFs opened with pypdf, CSV parsed with `csv.DictReader`; requirement/project pages
  rendered with bundled PDFium and visually inspected. Final report examples are in
  `flow-final/`; the real-provider run is separately labeled `flow-live/`.

## Blockers, access and approvals needed

1. **Hosted PostgreSQL connectivity:** provider/network administrator must investigate
   why TCP 5432 is unreachable from this environment. DNS works but no server session
   opens; the client cannot determine whether a provider outage, firewall, routing
   restriction or another upstream issue is responsible. Hosted logs and an authorized
   diagnostic route are needed for exact hosted root cause. Do not extend timeouts and
   declare success.
2. **Hosted valid-account login:** requires an existing authorized application test
   account supplied through a local file/environment, and permission to create normal
   login rate-limit/refresh-token records on the intended non-production target.
   Local fixture passwords are not PostgreSQL application account credentials. No
   password guessing, live account creation/reset or production login writes were done.
3. **Bare-domain DNS:** needs DNS-provider/hosting read access to establish authoritative
   configuration and an explicit approval before any record/domain change. A successful
   `www` page load does not establish database/API health.
4. **Release:** no push, deployment or production migration was attempted. Publishing
   requires explicit release approval and a separately reviewed production migration
   plan. Current application initialization may apply existing additive schema changes,
   so do not use it as a read-only production probe.
5. **Research evaluation:** no model accuracy, time-savings percentage, usability-study
   results, external automated tests, or academic approval are claimed. SMTP delivery,
   hosted cold starts, large export histories and multi-project tenancy are not signed off.

Use `FYP_PRESENTATION_2026-11-04.md` for the outline, safe startup, demo script and
failure fallback. Use `FYP_PROPOSAL_2026-11-04.md` for the current team-confirmed scope.
