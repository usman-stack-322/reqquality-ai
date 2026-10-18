# ReqQuality AI implementation and verification - 2026-10-17

Changes are prepared locally. Nothing was deployed, and no production schema or
application records were changed. Secrets were not printed or modified. The initial
working tree was clean; no AGENTS.md was found in the accessible repository.

## AI-only analysis

One Gemini call now covers ambiguity, missing-information questions, testability,
type with explanation, refinement, acceptance criteria, qualitative risk/priority
with explanations, and criteria-linked scenarios. Executable quality rules, numeric
risk calculation, separate scenario generation and generated fallback paths were
removed. Input validation, auth, authorization, sanitization and AI-schema validation
remain. The numeric-value provenance checker only flags introduced values for review;
it does not generate requirement-quality findings or business rules.

Prompts prohibit invented facts, business rules and numerical thresholds. Missing
facts must be questions or unconfirmed suggestions. All AI artifacts are unconfirmed;
SQE approval never silently confirms assumptions. Human judgment remains necessary.
New analysis records ai_only, version 2 and model provenance. Historical scores,
findings, artifacts and review metadata are retained and labelled Historical analysis.

Gemini ListModels confirmed the configured gemini-3.5-flash-lite supports generation
for this account. A live synthetic SDK call passed the complete new schema in
6,495 ms, returning two criteria and two scenarios. This was a local direct-provider
check, not a production/browser live-provider test. See audit/2026-10-17/live-gemini.json.
Run backend/verify_gemini.py to recheck; --smoke performs a quota-consuming generation.

There is one SDK attempt, default deadline 20 seconds (configurable within 1-25).
Timeout, quota/rate limit and invalid output return retryable 503 failures with safe
categories; no partial success or substitute analysis is returned. Input is retained.
Draft saving and login remain independent of Gemini. Incomplete analysis cannot be
saved as a completed result.

A committed database lease prevents duplicate user/input AI calls across workers.
Only that user's successful result is reusable for 120 seconds; failures release the
lease. If a host terminates the request, its lease expires after 90 seconds. No private
results cross users and no background thread is responsible for finishing AI work.

## Roles, project access and lifecycle

This remains the existing one-project application: current (ReqQuality AI). It does
not claim multi-project tenancy. Existing users retain access by default. Admin can
grant/revoke project_access in Team Management or PATCH
/api/admin/users/<id>/project-access with an enabled boolean. Unknown project IDs are
rejected. Revocation blocks ordinary requirement, analysis, dashboard, PDF and CSV
endpoints. Scenario IDs and criterion codes are checked against their requirement.
Admin/Manager organization management retains its existing scope. Project grant/revoke
controls apply to Analyst/SQA members; organization managers retain workspace access
through their management role. Only Admin changes these project grants.

| Role | Workflow permissions |
|---|---|
| Analyst + create permission + project access | Create/edit project requirements, explicitly accept suggestions, answer clarifications, prepare criteria, submit/resubmit. |
| SQA Engineer + review permission + project access | Start reviews, write notes, revise scenarios and criterion links, request changes, approve another author's requirement. |
| Admin | Existing user/project access, invitations, role configuration and assignment; no requirement creation or approval. |
| Manager | Existing delegated organization management; cannot perform Analyst/SQE actions by toggling cross-role feature permissions. |

Draft -> Ready for Review -> In Review -> Approved / Needs Revision.
Historical Pending records remain intact and may enter review. Revisions must be
resubmitted by an Analyst. Authors cannot review their own requirements even after
changing roles. Mutations require the latest integer revision; stale writes return
409. PostgreSQL row locks and SQLite write transactions serialize edits.

Material edits preserve before/after snapshots with actor/time, return to Draft,
clear stale risk/priority and invalidate criterion links for renewed review. No-op
saves preserve status. Reviews, scenario edits and explicit analysis acceptance also
preserve history. Existing review metadata is retained; past events are not invented.
The detail page lists the latest 100 events; authorized full snapshots are available
at /api/requirements/<id>/history/<history-id>.

Queue filters: status, risk, user priority, type. SQL pagination defaults to 50 records
(maximum 100), with total/page metadata. Detailed traceability shows criteria without
scenarios, unlinked scenarios and invalid links. Older overview coverage still means
artifact presence, not complete criteria coverage or executed tests. PDF and CSV
work; PDFs include provenance, explanations and criterion links.

## Measured local before/after performance

backend/compare_workflow.py reconstructs tracked HEAD Python source in a temporary
directory and runs the same benchmark against HEAD and the working tree. No .env,
credentials or real data is copied. Each uses temporary SQLite, synthetic users and
100 requirements with criteria/scenarios. perf_counter measures Flask test-client
requests: one first-use request and five warm requests per endpoint. First-use
requests occur AFTER fixture/schema setup and are not hosting cold starts. These
numbers exclude HTTP transit and real provider latency.

| Operation | Before first / warm median ms | After first / warm median ms |
|---|---:|---:|
| login | 220.46 / 242.70 | 228.99 / 227.04 |
| session | 5.47 / 5.36 | 4.19 / 3.20 |
| dashboard | 8.70 / 10.08 | 5.74 / 5.49 |
| list_summary | 14.37 / 9.43 | 4.86 / 5.09 |
| details | 11.54 / 10.44 | 5.80 / 5.17 |
| save | 38.66 / 35.92 | 30.94 / 30.91 |
| requirement_report | 41.65 / 35.34 | 210.39 / 30.38 |
| project_report | 28.20 / 23.83 | 19.93 / 23.11 |
| csv | 12.79 / 10.43 | 8.27 / 6.79 |

Fresh-interpreter import samples (without DB/network): before [3014.39, 2810.49, 3261.09] ms; after [1114.36, 1136.74, 1097.76] ms. Medians: 3014.39 -> 1114.36 ms. These are local process starts, not Vercel cold-start measurements.

Summary response: 34,301 -> 17,206 bytes, because the new default page returns 50 of
100 records plus metadata. History adds useful detail/save fields. Warm report timing
did not materially improve; the first requirement PDF is slower because PDF imports
now occur on first report use rather than during login startup. Hashing remains real
scrypt with unchanged parameters; modest login changes and noisy samples should not
be attributed entirely to this patch. Raw samples and Server-Timing are retained in
audit/2026-10-17/local-timings.jsonl.

Confirmed causes and fixes:

- SQLite repeated schema initialization/inspection and commits on ordinary connections.
  It now initializes once per file identity/process and retries failed initialization.
- Eager Gemini/PDF imports inflated auth startup. Both load on feature use; login and
  ordinary DB actions never call Gemini.
- The register was unbounded. It now uses SQL paging/filtering and a queue index;
  dashboard attention is capped at 20. Existing bounded PostgreSQL pooling remains.
- PostgreSQL initialization previously ran once per new worker. A persistent version
  marker permits two small checks instead of repeated DDL after installation. A
  nonblocking advisory lock coordinates migration ownership; competing workers receive
  retryable 503. These PostgreSQL paths are mock-tested, not live-database verified.
- Analysis could call Gemini for findings and scenarios separately. It now uses one
  complete response, button locks and a cross-worker duplicate guard.
- Dashboard/list requests and session bootstrap already included parallelism and
  deduplication; these were retained. Queue filter/page changes reuse the same
user/component dashboard snapshot instead of refetching statistics. Request deadlines now cover ordinary actions,
  auth/bootstrap/refresh and AI. No private caching or security weakening was added.

## Hosted evidence and remaining limits

These probes measured the CURRENT deployment, not this patch deployed. Proxied
anonymous /api/auth/me took 3,374.9 ms first, then 608.0 and 574.7 ms; Flask reported
0.5, 0.3 and 0.2 ms. Proxied health took 553.5, 602.1 and 600.3 ms. Direct API session
requests took 587.6, 526.7 and 535.4 ms; direct health 506.2, 527.0 and 507.0 ms.
An earlier proxied session took 4,064.6 ms with only 0.5 ms inside Flask.

This establishes substantial delay outside the instrumented handler. It cannot
separate TLS/network, proxy, queueing and hosting cold start. Instance identity is
unavailable: first/subsequent samples are not claimed as confirmed cold/warm instances.
urllib used fresh HTTPS connections, unlike browser keep-alive. Evidence:
audit/2026-10-17/hosted-anonymous.jsonl.

The configured Neon pooled endpoint resolves to three addresses with SSL required.
All three TCP/TLS probes timed out at about 3 seconds. A read-only psycopg attempt
timed out at 9,042 ms; pooled checkout exhausted its 10-second wait. No credential
rejection was observed. This confirms connectivity failure FROM THIS WORKSTATION,
not necessarily from Vercel. No production initializer was invoked. Evidence:
audit/2026-10-17/postgres-readonly.jsonl.

Vercel metadata identifies Flask and reports the latest production-targeted deployment
as ERROR. Runtime logs/deployment listing returned 403 for scope usman-dae3; no CLI
fallback is installed. The public API responds, so that metadata does not establish
which older deployment serves the domain.

Unverified: successful production login/session DB lookup; authenticated dashboard,
detail/save/review/report timings; production Gemini latency; DB query plans/timings;
actual PostgreSQL migration behavior; function region/duration/cold starts; provider
connection limits; performance after deploying this patch. No production speedup is
claimed. Server-Timing exposes DB connection/query, password, AI and application time
for authorized rollout measurements.

## Verification

- Backend: full 136-test run passed; final focused 13-test workflow run also passed, including AI timeout/quota/malformed output, safe retry,
  duplicate receipts, incomplete-save rejection, lifecycle, stale writes, self-review,
  project/object access, historical data, PDF parsing, CSV escaping, token rotation,
  revocation, CSRF, secure cookies, password hashing, invitations and password reset.
- Frontend: 13 tests passed; Vite production build passed (43 modules).
- Real Chrome tested the production bundle through local Vite preview, real Flask
  cookie auth/CSRF and temporary SQLite. Provider success/failure was mocked in this
  fixture. Passed timeout/input retention/retry, save, submission, SQE revision
  feedback, edit/resubmission, criterion linking, approval, and approved edit returning
  to Draft with history kept. No JavaScript exceptions; unconfirmed badges remained.
- Live provider verification is the separate direct SDK call above. Browser mocks are
  not evidence of production/live-provider workflow completion.
- Evidence: audit/2026-10-17/backend-final.txt, browser-results.jsonl,
  browser-events.json and browser-approved.png. Reproduction helpers:
  audit/2026-10-17/browser_check.py and backend/browser_fixture.py. A prior run encountered
  workstation suspension; that delay is excluded from performance conclusions.

## Important files

- backend/analyzers/ai_analyzer.py, llm_analyzer.py: contract/schema/provenance/deadlines.
- backend/services/analysis_requests.py: per-user cross-worker duplicate guard.
- backend/services/workflow_service.py, requirement_helpers.py, requirements_service.py,
  routes/requirements_routes.py: lifecycle, access, revisions and snapshots.
- backend/services/database_service.py: schema initialization/cache/versioning.
- backend/middlewares/auth.py and services/auth_service.py: fresh access and strict roles.
- backend/reporting.py, services/reports_service.py and management_service.py: exports
  and integration with existing management tools.
- frontend/src/components/WorkflowEditor.jsx, pages/RequirementDetails.jsx,
  RequirementInput.jsx, Dashboard.jsx, ManagerDashboard.jsx, api.js: explicit acceptance,
  editable workflow, access, filters, pagination, timeouts and feedback.
- backend/test_ai_workflow.py, adapted regressions, compare_workflow.py,
  benchmark_workflow.py and verify_gemini.py: tests and repeatable measurements.

## Rollout steps (prepared only; production requires approval)

1. Back up production. Validate with a disposable PostgreSQL DB/staging clone first;
   actual PostgreSQL execution could not be verified from this machine.
2. Install existing dependencies; retain persistent signing secrets and production
   HTTPS/proxy/Secure-cookie settings. No new mandatory secret. GEMINI_TIMEOUT_MS=20000
   is optional. The configured model is already verified. Process environment takes
   precedence over backend/.env and root .env.
3. The existing first-connection initializer adds users.project_access,
   requirements.revision, test_scenarios.criterion_codes, requirement_history,
   analysis_requests, requirement_submissions, reqquality_schema and indexes. The version marker is written
   after successful initialization. Do not pre-mark an unmigrated database. Existing
   requirements, statuses, scores and artifacts are not bulk rewritten. The explicit
   SQLite importer preserves new access/revision/link/history fields if needed;
   running that importer is NOT a normal deployment step.
4. Deploy frontend/backend together after approval because edit/review APIs now require
   revision. No production migration or deployment has been performed here.
5. Ensure actual API request duration accommodates connection setup and bounded AI
   (60 seconds is a practical configuration). For backend-rooted Vercel Flask app.py,
   documented config is {"functions":{"app.py":{"maxDuration":60}}} in
   backend/vercel.json. Match the real entrypoint/root if different; live settings
   were not changed. Source: [Vercel Flask duration configuration](https://vercel.com/docs/frameworks/backend/flask).
6. Verify API/DB region and connectivity from the runtime before adjusting pool size.
   The existing pool defaults to five connections per process; autoscaling, idle/cold
   instances and provider limits still affect production. Do not weaken hashing,
   session checks or private-response cache policy to pursue a latency target.
7. After approved deployment, measure authorized login, session, dashboard, details,
   save, AI and reports independently. Record first/established instance requests,
   Server-Timing and platform logs; verify access revocation, CSRF, re-review and
   exports with live services before claiming production completion.
