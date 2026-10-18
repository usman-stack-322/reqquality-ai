# Reliability follow-up — 2026-10-17

Changes were implemented in the existing working tree, preserving its earlier
uncommitted implementation and saved application database. All writes for testing
used temporary SQLite databases and synthetic users/requirements. No production
deployment, migration, account change, or data write was performed.

## Baseline and architecture

React 19/Vite 6 frontend; Flask API; SQLite locally and psycopg connection-pool
PostgreSQL in configured production; google-genai/Gemini semantic analysis.
`frontend/vercel.json` forwards API traffic to reqquality-api.vercel.app. The
repository contains the Flask WSGI entrypoint; actual platform duration, region,
instance lifecycle and database reachability from that runtime are unverified.
No repository AGENTS.md was found. React review and full-story verification skills
were applied without changing stack or introducing new services.

Initial checks: **137 backend tests**, **13 frontend tests**, and the Vite build
passed. Four newly added reproductions then failed against the baseline, proving
gaps that the pre-existing suite did not cover. Baseline evidence is in
`audit/reliability-followup/backend-baseline.txt`, `reproductions.txt`, and
`performance-before.jsonl`. Prior implementation evidence remains untouched under
`audit/2026-10-17/`.

## Defects and fixes

| Defect / cause | Implemented fix and regression evidence |
| --- | --- |
| Browser-supplied JSON could impersonate completed AI analysis and set risk/provenance/confirmation values. Schema validation establishes shape, not origin. | HMAC receipt using the existing persistent JWT secret binds the entire generated result to the authenticated user, normalized title/description/type/priority, and clarification answers. New creates and explicit analysis acceptance verify it. Forgery, tampering, cross-user replay and changed input are rejected. |
| Analysis generated for different text could be attached to an existing record by supplying that record's title separately. | Acceptance verifies the signed input against the locked saved revision, including type/priority/clarifications. |
| Text edits replaced all criteria with source=original and confirmation=false; a no-op save returned empty history. | Unchanged criteria preserve source, confirmation, introduced values and codes even when reordered; replacement criteria receive new codes. Material edits invalidate scenario links and reset review as before. No-op saves return history without advancing revision. |
| Nested generated fields had no length bounds; provider extras could carry provenance flags. | Bound refinement/explanation/scenario text and collections; project only schema-approved scenario fields. Equivalent limits protect human scenario edits. Invalid output fails retryably, never via a fallback. |
| Clarification answers were saved but not sent on reanalysis. | Validated answers now reach Gemini as untrusted input, participate in duplicate detection, and are bound to acceptance. |
| A late session response could refresh after logout; a network exception during refresh hid the original unauthorized response. | Auth-generation checks cover login/logout/password changes, CSRF recovery and refresh. Network refresh failure preserves the original unauthorized response. Caller aborts never replay writes. Three new frontend regressions cover logout, network failure and cancellation. |
| Accepting analysis or submitting while edits were unsaved could discard draft fields on remount. | Disable these transitions until edits are saved; explain the pending edits. Suggestion review now includes type, questions, conflicts, risk/priority explanations, criteria and linked scenarios. |
| Session initialization failure silently looked like a logged-out session. | Explicit session-unavailable feedback with retry/sign-in; duplicate logout requests are blocked. |
| A stale analysis worker could overwrite or delete a replacement worker's lease/result after lease expiry. | Lease completion/cleanup checks the claimed expiry and uncompleted state. Deterministic overlapping/expired-worker tests verify ownership. Cache keys include the analysis contract version. |
| History capture reread the same requirement and child tables during save/edit. | Reuse the already fetched snapshot record, then refresh history only. Creation removes four SQL execute calls. |
| Saved findings were nested inside the optional refinement card; legacy analysis without refinement could disappear. | Render finding cards independently, show conflict/type/risk/priority explanations, and display the actual saved analysis version. |

AI analysis remains AI-only. Ordinary validation, CSRF, object/project access,
role checks, hashing, secure production cookies, and private no-store responses
remain enforced. Historical results load without new receipts. New results are
version 3; old AI version 2 and older historical results retain their identities.

Important implementation files:

- `backend/services/analysis_receipts.py`, `analysis_service.py`,
  `analysis_requests.py`: authenticity, input binding, retry and lease isolation.
- `backend/analyzers/llm_analyzer.py`, `ai_analyzer.py`: prompt, schema, bounds,
  untrusted clarification context, provenance and version.
- `backend/services/workflow_service.py`, `requirements_service.py`,
  `requirement_helpers.py`: criteria provenance, revisions/history, query reuse.
- `frontend/src/api.js`, `App.jsx`, `components/WorkflowEditor.jsx`,
  `pages/RequirementInput.jsx`, `pages/RequirementDetails.jsx`: session recovery,
  safe transitions and complete suggestion review.
- `backend/test_reliability.py`, `test_ai_workflow.py`, `frontend/src/api.test.js`:
  meaningful regressions; benchmark/probe scripts and raw evidence accompany them.

## Journeys and final verification

The automated suite covers actual SQLite/API writes plus isolated mocks for
provider/SMTP/PostgreSQL failure paths. It checks valid/invalid/oversized/unusual
inputs, SQL and CSV injection handling, password hashing, failed login, session
expiration/rotation/replay/revocation, CSRF, role revocation, user/project/object
boundaries, idempotent creation, stale revisions, historical records, pagination,
filters, PDF parsing and exports. Two new threaded SQLite tests prove concurrent
save retries create one record/history entry and competing edits yield one 200
and one 409. Mocked AI timeout/quota/malformed output all fail explicitly, preserve
the absence of a saved result and allow retry.

Final complete backend: **148 passed**, 322.461 seconds, recorded in
`audit/reliability-followup/backend-final.txt`; frontend: **16 passed**, build:
**passed**, 43 modules, 2.22 seconds. `git diff --check` passed. The first restricted
frontend attempt failed because esbuild could not read parent directories; the
identical suite/build passed with the necessary read access.

Real Chrome tested the final production bundle through local Vite preview and a
restarted Flask server with temporary SQLite and real cookie authentication/CSRF:

- Failed login, Analyst login, forbidden admin and unknown-project API requests.
- Queue filtering without another dashboard-statistics request.
- Double analysis click under 250 ms added network latency; provider failure,
  actual browser offline failure, retained text and successful safe retry.
- Double save creates one record; refresh restores session and requirement detail.
- Analyst submission, SQE start/revision feedback, Analyst edit/resubmission,
  scenario linking, SQE approval, then approved material edit returns to Draft.
- Unsaved edit prevents submission; unconfirmed AI labels and review history remain.
- Authenticated PDF and CSV responses; Admin team UI/API; logout denies later access.

**All browser assertions passed; zero JavaScript exceptions.** The expected offline
request failure is recorded. See `browser-results.jsonl`, `browser-events.json`,
`browser-approved.png`, and the reproducible `browser_check.py` in the evidence
directory. Browser provider outcomes were mocked, not live Gemini.

Separately, one real Gemini API analysis/save/reopen/PDF journey passed using
temporary SQLite, with exactly one stored requirement, valid criterion links,
null numeric risk score, and all generated artifacts unconfirmed. Its evidence is
`live-api-journey.json`. No production workflow is inferred from these checks.

## Performance measurements

Same Windows workstation, local Flask test client and temporary SQLite with 100
synthetic requirements/criteria/scenarios. Per operation: one first-use request,
then **20 warm samples**. Median and nearest-rank p95 below are milliseconds.
Each measurement is one direct API request, not a whole browser navigation.
Login keeps real scrypt and token issuance; synthetic rate-limit counters are
cleared outside the timed interval so the benchmark does not measure throttling.
Queries count SQL execute calls, excluding executemany/schema initialization.
Raw samples, bytes, query counts and last Server-Timing headers are retained in
`performance-before.jsonl` and `performance-after.jsonl`.

| Operation | Median before → after | p95 before → after | Execute calls before → after | Response bytes before → after |
| --- | --- | --- | --- | --- |
| Login | 270.69 → 217.70 | 551.05 → 436.61 | 5 → 5 | 257 → 257 |
| Session | 3.51 → 2.50 | 4.55 → 3.86 | 2 → 2 | 223 → 223 |
| Dashboard | 6.14 → 5.30 | 6.98 → 5.94 | 6 → 6 | 2,160 → 2,160 |
| Queue summary | 5.71 → 4.54 | 6.75 → 5.05 | 3 → 3 | 17,206 → 17,206 |
| Detail | 5.80 → 4.77 | 6.46 → 5.19 | 6 → 6 | 5,609 → 5,609 |
| Save draft | 91.66 → 38.20 | 124.94 → 121.57 | 17 → 13 | 872 → 872 |
| Requirement PDF | 34.27 → 30.81 | 50.03 → 32.79 | 6 → 6 | 5,236 → 5,267 |
| Project PDF | 22.00 → 19.66 | 23.94 → 23.55 | 5 → 5 | 2,934 → 2,934 |
| CSV | 6.02 → 5.43 | 7.10 → 6.18 | 2 → 2 | 13,498 → 13,498 |

The evidence-backed code improvement is removal of four repeated detail queries
on create, plus equivalent snapshot reuse on edits/analysis acceptance. Login and
read query counts did not change in this follow-up; their small timing differences
are workstation/run variation, not evidence of a new optimization. Save still has
a broad tail; its p95 did not materially improve. SQLite filesystem/commit timing
and machine scheduling are included, not isolated causal measurements.

First-use save was 458.97 → 29.34 ms and first requirement PDF 342.68 → 290.64 ms.
These first-use values are n=1 and include lazy initialization/imports. Fixtures
already initialized the schema, so they are **not full process/schema cold starts**.
Browser timings include HTTP/Chrome and concurrent test workload; some operations
took hundreds of milliseconds to over a second. They are retained verbatim and
are not substituted for the controlled endpoint table or a production benchmark.

AI latency is measured separately: direct SDK baseline n=8 median 2,520.1 ms;
final prompt subset n=3 median 2,613.3 ms; live API journey n=1 3,677.0 ms. Different
cases/prompts prevent a speed comparison; these sample sizes do not support a
useful provider p95. CRUD/login never call Gemini. No background-thread job system
was introduced: synchronous Gemini remains bounded, with one provider attempt,
database leases and safe explicit retry rather than assumptions about worker life.

## Live production evidence and blockers

Six anonymous, non-destructive production requests were made. `/api/auth/me` was
200 at 3,255.32, 742.18 and 503.62 ms; `/api/dashboard` correctly returned 401 at
441.30, 459.22 and 444.38 ms. Server-Timing reported just 0.2–0.4 ms, all no-store.
Most elapsed time is outside the measured Flask handler for these anonymous
paths. DNS/TLS/network/platform startup cannot be separated from this evidence;
the first request is **not a verified cold instance**, and later requests are not
proven same-instance warm requests. No production p95 is claimed (n=3 per path).

The configured PostgreSQL pooled hostname resolved to three addresses. Every TCP
probe timed out at about 3,002 ms, before TLS, authentication or SQL. A separate
read-only driver connection failed after 9,065 ms with ConnectionTimeout. This
confirms a connectivity problem from this workstation, not a bad password or an
application-query diagnosis, and does not establish connectivity from Vercel.
Evidence: `public-production.json`, `postgres-probe.json`.

There are no production application login/admin credentials in backend/.env;
SMTP credentials are not application credentials. The earlier implementation's
Vercel log inspection was denied for the available account/team scope. Therefore
production authenticated login/session/dashboard/detail/save/report latency,
production PostgreSQL query plans/concurrency/migrations, deployment cold starts,
and live runtime logs remain unverified. No production writes or load tests were
used to fill these gaps.

## AI quality and supported workflow limits

The explicit rubric, manually inspected outputs, repetitions, improvements and
remaining concerns are in
[AI_BENCHMARK.md](audit/reliability-followup/AI_BENCHMARK.md). Fifteen calls used the
already configured, successfully responding model. No accuracy percentage or
calibrated risk probability is claimed. Conflict handling improved; unsupported
UI/design suggestions and overstatement of missing implementation details still
occur. All results remain unconfirmed suggestions requiring human judgment.

Permissions/lifecycle remain Draft → Ready for Review → In Review → Approved /
Needs Revision; revisions must be resubmitted. Analysts create/edit/analyze/accept
and submit within the authorized shared project; SQE reviews others and revises
linked scenarios; Admin manages accounts, roles, permissions and project access.
Self-review is denied even after an author's role changes. Significant transitions
record actor/time/snapshot and reject stale revisions. Material edits require
another review and clear stale risk assessments and scenario links.

Missing rather than passed: multiple independent projects/tenants; structured
per-question resolution (answers are a text field); actual execution of generated
tests; exhaustive semantic correctness; a durable background AI queue. Unsaved
draft text is preserved during errors but is not autosaved across deliberate
refresh/navigation; save the draft first. Provider timeouts can leave the provider
uncertain about completion/charging: leases prevent overlapping requests and short
retries reuse successful results, but provider billing cannot be guaranteed exactly
once after an ambiguous network failure or a failed result-cache database write.

## Deployment/configuration steps still required

1. No new dependency, environment variable, or database schema change is introduced
   by this follow-up. Keep existing persistent JWT_SECRET_KEY and
   REQQUALITY_SECRET_KEY. The receipt uses JWT_SECRET_KEY; rotation invalidates
   outstanding unsaved receipts, requiring fresh analysis, not stored history.
2. The earlier prepared changes in this same checkout still have their additive
   migration requirements: see IMPLEMENTATION_REPORT.md. Validate on a disposable
   PostgreSQL staging clone and back up before the approved production rollout.
   Do not pre-mark an unmigrated database as current or run the SQLite importer as
   a routine deployment step.
3. Deploy frontend/backend together only after approval. New acceptance requires a
   signed v3 response; unsaved pre-upgrade browser results must be reanalyzed.
   Historical stored results need no rewriting. Old analysis-cache entries are
   separated by the new contract version and expire normally.
4. Retain the configured Gemini model/key; availability was verified by successful
   live calls, not guessed. Optional GEMINI_TIMEOUT_MS remains 20,000 ms by default,
   clamped at 25,000; SDK attempts=1. Keep HTTPS and production Secure cookies.
5. Confirm the actual Vercel function budget accommodates bounded AI plus database
   setup (the previously documented 60-second setting is still only prepared).
   Verify API/database region, pooled endpoint availability and connection limits
   from the deployed runtime before changing pool settings or architecture.
6. With authorized production account/log access, run the same separated journeys
   and timings after approved rollout; identify cold/warm instances using platform
   evidence, and verify PostgreSQL locking, query plans and additive migrations.

No evidence supports calling the application bug-free or the AI perfectly accurate.
