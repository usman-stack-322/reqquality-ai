> Historical reference. See the [2026-10-17 implementation and verification report](IMPLEMENTATION_REPORT.md) for current analysis, permissions, lifecycle and performance evidence.

# ReqQuality AI audit - 2026-10-10

Changes are local and have not been deployed. Existing production data, accounts,
role assignments, permissions and credentials were not modified. Tests use
temporary SQLite databases with mocked AI and email. The only new persistent
schema is an additive `request_limits` table and index, initialized when this
version starts using a database. No migration was run against the hosted database.

## Confirmed issues and fixes

| Finding | Resolution |
| --- | --- |
| Public home/login waited for session recovery | Render public pages immediately; keep a skeleton and authentication gate for protected routes. |
| StrictMode could repeat session bootstrap | Share the in-flight bootstrap; discard late responses after login/reset/registration. |
| Anonymous bootstrap always attempted refresh discovery | `/me` reports absence of a refresh cookie; client skips the unnecessary CSRF request. Existing expired sessions still refresh. |
| Every page shipped in the initial bundle | Lazy-load protected/recovery/invitation pages and Admin CSS; retain eager home/login. Add a recoverable page-load error boundary. |
| Non-Admin session lookup opened another connection for permissions | Read fresh permissions using the same connection as the user lookup. No cross-request authorization cache. |
| Dashboard/input lists downloaded full analysis text | Add opt-in `?view=summary`, used by those pages. The existing full list and detail APIs remain compatible. |
| Superseded effects could update an old requirement/page | Abort obsolete list/detail loads and ignore canceled results. Remove Admin dashboard refetches when the section changes without changing the requested data. |
| Direct CSV/Admin report links could fail after access expiry | Download PDF/CSV through the cookie-auth API wrapper, with refresh, content-type checks, busy state and errors. |
| Login had no general throttle; reset/invitation limits were incomplete | Add atomic database-backed limits shared across workers; preserve invitation mismatch lockouts. |
| Unknown/disabled users skipped costly password verification | Use a dummy scrypt check with the same generic credential error. No password/hash caching or weakened hashing. |
| Malformed analysis enum values could produce HTTP 500 | Validate types before set membership, scenario IDs/sources and analysis text/list fields; return HTTP 400. |
| Inputs had no general request or text-size bounds | Cap JSON bodies at 1 MB, new titles at 200 characters, new descriptions/reviewer notes at 20,000; match form limits. Stored content is not truncated. |
| Generic exception handling swallowed HTTP 413 | Preserve HTTP exceptions so oversized requests return a JSON 413 response. |
| Configuration could generate different secrets per worker | PostgreSQL startup requires explicit persistent session/JWT secrets of at least 32 bytes. Existing local secrets satisfy these checks; no secrets were changed. |
| Homepage overstated testing/verification, omitted Admin, and had an incomplete workflow | Rewrite against code and tested endpoints; explain human review, quality risk, generated scenarios, fallback analysis and actual responsibilities. |
| Admin permission metadata implied actions its routes reject | Keep server rules and metadata contract; hide creation/review controls for `admin` and describe Admin as management/inspection. No access expansion. |

Navigation uses navy `#0F172A`, primary actions teal `#0F766E`, backgrounds
`#F8FAFC`, white cards and primary text `#1E293B`. Updated responsive workflow
cards, readable Admin typography, form controls, table surfaces and skeletons.
Primary text/action palette pairs pass WCAG AA contrast checks. This is a palette
check, not a complete browser accessibility certification.

The homepage and input review path now use:

Requirement Input -> Hybrid Analysis -> Refinement -> Acceptance Criteria ->
Risk / Priority -> Test Scenarios -> Traceability -> SQA Review -> Dashboard / Reports.

Analysis returns refinement/criteria/risk/scenarios together, rather than exposing
nine independent transactional stages. Refinement is a **suggested improved
requirement**, not an implemented edit/version history feature. Traceability links
criteria and generated scenarios to a requirement; it is not executed-test
coverage. Project Context input, test execution and multi-project isolation are
explicitly separated from implemented features. There is no claimed roadmap or
guarantee of software correctness.

## Measurements

Original source: commit `9c2d582`. `backend/compare_audit.py` copies tracked Python
source into a temporary directory and runs before/after sequentially. It never
copies environment files or data. Both versions use 100 synthetic requirements,
linked criteria/scenarios and about 4 KB of analysis text per record. Endpoint
figures are medians of seven Flask test-client requests; login figures use three
requests per role. These are local SQLite timings without network transit.
The retained comparison ran without the test/build workloads running in parallel.
Raw results: [audit/2026-10-10-timings.jsonl](audit/2026-10-10-timings.jsonl).

| Measurement | Before | After |
| --- | ---: | ---: |
| Initial JavaScript | 332.43 KB | 245.58 KB |
| Initial JavaScript, gzip | 94.59 KB | 76.12 KB |
| Initial CSS | 52.34 KB | 35.81 KB |
| Dashboard list response | 456,201 bytes | 34,301 bytes |
| SQA Admin `/auth/me` | 4.88 ms | 4.61 ms |
| Analyst `/auth/me` | 6.95 ms | 3.02 ms |
| SQA Engineer `/auth/me` | 6.62 ms | 3.64 ms |
| SQA Admin `/dashboard` | 5.71 ms | 5.90 ms |
| Analyst `/dashboard` | 6.23 ms | 5.64 ms |
| SQA Engineer `/dashboard` | 7.15 ms | 5.58 ms |
| Analyst list used by dashboard | 8.48 ms | 5.79 ms |
| SQA Engineer list used by dashboard | 8.30 ms | 5.93 ms |
| SQA Admin password login | 184.17 ms | 213.87 ms |
| Analyst password login | 186.12 ms | 210.67 ms |

The stable improvements are the **92.5% smaller list payload**, smaller initial
assets, removed public rendering dependency and one connection for session lookup.
Dashboard requests already ran in parallel; no sequential-fetch fix was needed.
The dashboard remained around 6 ms and no slow SQL query was established locally.
Small timing differences are subject to host variation; the raw login baseline
includes a 1,029.78 ms outlier. Login is modestly slower with durable rate-limit
writes, and password hashing remains costly by design. No successful-login speed
improvement or production before/after latency is claimed.

Read-only live HTTP observations of `https://www.reqqualityai.site`:

| Request | Status | Elapsed |
| --- | ---: | ---: |
| Homepage HTML | 200 | 635.0 ms |
| Anonymous `/api/auth/me` | 200 | 3,063.2 ms |
| Anonymous `/api/dashboard` | 401 | 574.1 ms |

These are single observations, including network/proxy/cold-start effects, not
medians or database timings. The session response had no `Server-Timing` header.
PostgreSQL connection attempts timed out after 10 seconds even with broader
network access. Consequently the audit cannot attribute live latency to database
queries, measure hosted authenticated dashboards, or provide deployed after-times.
Older hosted measurements in `backend/LOGIN_PERFORMANCE.md` are historical.

New API `Server-Timing` and logs expose request total, database acquisition and SQL
execution without SQL text, credentials or record contents. `db_connect` includes
cold initialization; `db_execute` excludes initialization, result fetch,
serialization, commit and close time. Login additionally reports password,
permissions, token and rate-limit stages. The overall request includes those
stages, but excludes browser/proxy transit.

## Authorization and security findings

| Default role | Server-side behavior preserved |
| --- | --- |
| SQA Admin (`admin`) | Management, invitations, role configuration, assignment, settings, shared record/dashboard/export reads; requirement creation and review mutations return 403. |
| Analyst | Analyze/create with fresh `create_requirements` permission; shared reads/exports; default review mutations return 403. |
| SQA Engineer | Review with fresh `review_requirements` permission; shared reads/exports; default creation/analysis returns 403. |

The existing configurable legacy `Manager` role is preserved. Granting configured
permissions to non-Admin roles continues to work as before. Users share **one
project**: creator and assignee IDs are provenance/workload fields, not tenant or
record isolation. Assignment to a different engineer does not block another
authorized engineer's review. Tests lock in this existing scope rather than
silently imposing owner-only access. Admin's broad static permission metadata
remains a compatibility inconsistency; the UI respects effective route rules.

Verified by code review and isolated tests:

- Scrypt passwords; Secure/HttpOnly/SameSite=Lax access and refresh cookies;
  signed HS256 access claims, refresh hash storage, rotation/reuse revocation,
  24-hour family deadline and account auth-version checks.
- Refresh/session persistence, tampered/expired token rejection, logout,
  disabled/changed-role/password revocation and fresh permission checks.
- Protected API mutations require CSRF. Explicit unapproved origins are rejected;
  credentialed CORS uses an explicit allowlist. API responses use no-store,
  nosniff and no-referrer. Non-browser clients without Origin still require the
  existing cookies/CSRF on protected mutations.
- Static SQL structure and bound user values; enum/scenario/input validation;
  React renders text without raw HTML insertion; PDF content is escaped; CSV
  formula prefixes are escaped. Literal HTML in requirement text remains stored
  as text, preserving content without executing it in the UI.
- Invitations expire after 24 hours and acceptance is transactional/single-use.
  Mismatch rejects and keeps the link pending; five mismatches create a temporary
  15-minute lock which recovers without extending expiry or revoking the link.
- Rate limits return 429/Retry-After and persist across client instances. See
  [TOKEN_AUTH.md](backend/TOKEN_AUTH.md) for limits and proxy configuration.
- Current tracked-source scan found no matching hard-coded Gemini/OpenAI keys or
  credential-bearing PostgreSQL URLs. `.env`, private certificate keys and local
  database files are ignored. This is not a Git-history or hosting-secret audit.

## Validation

- Final full backend discovery: **117 test executions passed**. Discovery also
  includes invitation fixtures imported by other suites.
- Focused audit, pooling and login regressions: **23 passed**.
- Frontend API, synchronous render and primary contrast checks: **11 passed**.
- Final `npm.cmd run build`: passed; protected page/CSS chunks emitted separately.
- `git diff --check`: passed.
- Requirement -> analysis -> saved refinement/criteria/scenarios -> traceability
  -> In Review -> Needs Revision -> Approved -> dashboard -> PDF/CSV exercised
  with temporary records. AI network failure was mocked and deterministic fallback
  still produced criteria and all four scenario categories.
- PDF and CSV exports exercised for all three roles; anonymous direct export/API
  requests return 401. PDF content/type, structure and attachment headers checked;
  `pypdf` parsed every generated PDF and found the requirement/review text.
- Existing tests cover invitation expiry, mismatch recovery, single use,
  concurrent acceptance, role tampering and refresh/revocation behavior.

Reproduce:

```powershell
# From frontend:
npm.cmd test
npm.cmd run build

# From backend, after installing requirements-dev.txt:
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe compare_audit.py
# Optional read-only hosted diagnostic (requires working network/DB access):
.\.venv\Scripts\python.exe benchmark_readonly.py
```

## Remaining limitations and release considerations

1. Live authenticated flows, hosted PostgreSQL query plans and real AI/SMTP
   integration were not verified. PostgreSQL connections timed out and no
   production test credentials were supplied. Production records were not created
   for testing.
2. No browser surface was available. Public-render tests validate synchronous
   output and protected gating, but do not replace desktop/mobile browser,
   keyboard, screen-reader or layout inspection. Poppler was unavailable; PDF
   structure/text were checked, but report pagination was not visually rendered.
3. Requirement lists and Admin Python aggregations remain unbounded at large
   project sizes. The summary option removes analysis text but is not server
   pagination. AI analysis/scenario requests can still take their configured
   provider timeout, with fallback on failure.
4. Shared-project visibility and legacy role/permission contracts remain. There
   is no multi-tenant boundary, Project Context editor, requirement version history
   or executed-test result store. Client-supplied analysis is saved as suggestions,
   not independent evidence of quality.
5. Before any release, verify persistent secrets and the frontend origin allowlist.
   `TRUST_PROXY_HOPS` now trusts client-IP and HTTPS forwarded headers only for the
   specified chain; the proxy must overwrite both and prevent untrusted direct
   connections. Shared NATs may encounter IP limits. Rate-limit counters and old
   refresh hashes need an operational retention policy outside request handling.
6. Password-reset email delivery remains synchronous, and its existing response
   timing can differ for known and unknown accounts despite a generic message.
   The reset cooldown and new limits reduce abuse but do not eliminate that timing
   side channel. Cross-tab simultaneous refresh can trigger existing token-reuse
   protection; the client deduplicates refresh within a tab only.
7. Hosting TLS/security headers, dependency advisories, Git history and actual
   deployed configuration were not exhaustively inspected. Code/test findings here
   are not a claim that the deployed service is free of vulnerabilities.

No deployment, permission edit, production data migration, credential rotation or
real invitation/reset email was performed.
