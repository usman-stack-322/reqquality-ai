# QA Manager dashboard

The existing `admin` role now opens the QA Manager workspace at `/#admin` after
login. QA Manager is the organization administrator; there is no separate Super
Admin role or interface. Analysts and SQA Engineers retain their existing pages.
Guests can still visit Home, while authenticated users are redirected to their
workspace.

## Files delivered

Created for this dashboard:

- `backend/admin_dashboard.py`: schema additions, projections, filters, management endpoints and audit writer.
- `backend/test_admin_dashboard.py`: isolated backend integration tests.
- `frontend/src/pages/ManagerDashboard.jsx`: workspace navigation, dashboard and management views.
- `frontend/src/components/ManagerUI.jsx`: shared icons, badges, charts, tables and activity list.
- `frontend/src/manager.css`: scoped responsive dashboard styling.
- `QA_MANAGER_DASHBOARD.md`: architecture, calculations and verification notes.

Modified for this dashboard:

- `backend/app.py`: migration registration, active-account/session-version checks,
  management routes, creation/review activity and assigned-reviewer detail.
- `backend/invitations.py`: invitation delivery, revocation and acceptance activity;
  the existing invitation workflow remains in use.
- `backend/migrate_sqlite_to_postgres.py`: retain management fields, activity and
  organization settings when importing; support older SQLite sources.
- `frontend/src/App.jsx`: protect nested manager routes and render the workspace.
- `frontend/src/pages/Admin.jsx`: allow dashboard buttons to open the existing
  invitation form and refresh manager data after invitation actions.
- `frontend/src/pages/RequirementDetails.jsx`: manager navigation, assignment,
  review-section links and assigned-reviewer information.
- `README.md`: link to this guide.

Other existing uncommitted invitation/authentication changes are not replaced.
Local preview scripts/screenshots under the ignored `backend/instance/` directory
are verification artifacts, not application routes or production fixtures.

## Architecture and schema

The feature uses the existing React/Vite hash router, Flask sessions and CSRF
decorators, SQLite/PostgreSQL connection adapter, requirement analysis JSON,
acceptance-criteria/test-scenario child tables, and invitation system. No new
frontend or backend dependencies are required.

New fields are limited to information absent from the previous schema:

| Change | Purpose |
| --- | --- |
| `requirements.assigned_reviewer_user_id` | Nullable FK to users; assignment is separate from the existing actual reviewer and review timestamp. |
| `users.is_active` | Integer, defaults to 1; supports disabled accounts without deleting requirement history. |
| `users.auth_version` | Integer, defaults to 0; changing access or password invalidates old sessions. |
| `activity_events` | Actor ID/name, action, entity type/ID, summary and UTC timestamp; no credentials or invitation tokens. |
| `organization_settings` | Singleton name and overdue-review threshold, default 7 days. |
| Indexes | Assigned reviewer and activity creation timestamp. |

Idempotent initialization applies these additions on the first database connection
after restarting the backend. Existing requirements, users, review statuses and
invitation columns are retained. Take the usual database backup before deploying
schema changes. The importer keeps its existing conflict checks rather than
overwriting different destination records.

There is currently one shared project and one workspace in the existing schema.
The Projects view presents that real shared project. The organization name is
configurable branding, not a new tenant boundary. No multi-project or multi-tenant
security model has been invented.

## API endpoints

| Method and path | Purpose / access |
| --- | --- |
| `GET /api/admin/dashboard` | Consolidated dashboard data; admin only. |
| `GET /api/admin/requirements` | Filtered, paginated requirement rows; admin only. |
| `PATCH /api/admin/requirements/<id>/reviewer` | Assign, reassign or clear an active SQA Engineer; admin + CSRF. Body: `{"reviewer_id": 3}` or `null`. |
| `PATCH /api/admin/users/<id>` | Change Analyst/SQA Engineer role or `is_active` boolean; admin + CSRF. QA Manager accounts cannot be edited here. |
| `PATCH /api/admin/settings` | Set `name` and `overdue_days` (1–90); admin + CSRF. |
| `POST /api/auth/change-password` | Current/new password; authenticated user + CSRF. Invalidates all existing sessions after success. |

The existing `/api/dashboard`, requirement detail/review APIs, report downloads
and invitation endpoints remain available with their original permissions.
Managers inspect and assign reviews; only SQA Engineers record SQA decisions.

Read filters: `project=current`, `type`, `risk`, `review`, `reviewer`, `from`, `to`,
`q`, `quality`, `page`, `page_size`. Dates are inclusive UTC **creation** dates.
Search matches requirement ID/title, case-insensitively. Special values include
`risk=high-critical`, `risk=unscored`, `review=pending-reviews`, and
`reviewer=unassigned`. Unsupported fields/values return 400. Page size defaults
to 20 and is capped at 100.

Summary and list requests reuse the same filtering functions. Requirement
filters affect review, risk, quality, traceability, creation cohorts and reviewer
workload; team totals, invitations and activity remain workspace-wide.

## Frontend routes and behavior

`/#admin` is the overview. Sidebar routes are `/#admin/projects`,
`/#admin/requirements`, `/#admin/reviews`, `/#admin/team`,
`/#admin/invitations`, `/#admin/traceability`, `/#admin/reports`,
`/#admin/activity`, and `/#admin/settings`.

`/#admin/requirement/<id>` reuses Requirement Details; `?review=1` scrolls to its
review section. `/#admin/invitations?invite=1` opens the existing invite form.
Profile/password views use the settings `tab` query parameter. Legacy admin
visits to `/#dashboard` also open the manager overview.

KPI cards, distributions, quality findings, workload names and traceability
counts navigate to corresponding filtered lists. Fetches update the workspace
without a full application reload; superseded requests are aborted. Native
dialogs provide reviewer selection. Loading, errors with retry, no-data states,
text-labelled badges, keyboard focus indicators and a mobile navigation drawer
are included. The notification button summarizes the current attention queue;
it is not a push-notification/inbox service.

Reports reuse the existing PDF and CSV downloads. They explicitly export the
whole shared project, independent of dashboard filters.

## How statistics are calculated

All figures come from saved database records, without production seed data.
For filtered requirement sets, percentages use the number of matching
requirements as denominator; an empty set produces zero, never division errors.

| Metric | Calculation |
| --- | --- |
| Total requirements | Number of matching requirement records. |
| Analyzed | Non-null saved risk score or a non-empty valid analysis object. |
| Pending reviews | Current status `Pending` or `In Review`. |
| Approved | Current status `Approved`. |
| High / critical risk | Saved risk level `High` or `Critical`. |
| Review distribution | Counts by existing statuses; display `Pending` as **Not Reviewed**. |
| Risk distribution | Counts for Low/Medium/High/Critical; unknown/null levels are reported separately as unscored. |
| Unassigned reviews | Pending-review records with no assigned reviewer. |
| Overdue | Pending/In Review with creation time at least the configured number of days old, compared with server UTC time. |
| Ambiguity / missing information / testability | Requirement has a non-empty corresponding issue list in saved analysis JSON. Each requirement counts once per category. |
| Conflicts | Non-empty saved `conflict_issues` or `inconsistency_issues`, if present. Otherwise **Not assessed**. Current analysis does not produce these fields. |
| Missing criteria / scenarios | No rows in the corresponding existing child table. |
| Needs refinement | Needs Revision, or ambiguity/missing information/testability/conflict findings, or High/Critical risk. |
| Attention queue | High/Critical risk, overdue review, Needs Revision, missing criteria/scenarios, or analysis findings needing refinement. Ordered Critical then High, overdue first within priority, then oldest. Dashboard maximum 8. |
| Pending review table | Pending/In Review, unassigned first, then oldest. Dashboard maximum 8. |
| Traceability coverage | Requirements with at least one acceptance criterion **and** at least one test scenario / matching requirements × 100. This preserves the existing dashboard definition. |
| Reviewed by SQA | Non-null `reviewed_at`; independent of whether the current decision is Approved. |
| Team totals | Registered users, role counts, active users. Disabled users remain in registered totals; invitations are separate. |
| Assigned workload | Requirements whose assignment points to the engineer. |
| Pending workload | Assigned requirements in Pending, In Review or Needs Revision. Includes revision work, unlike the pending-review KPI. |
| Completed workload | Currently Approved requirements whose actual `reviewed_by_user_id` is the engineer. Historical review-event totals are not inferred. |
| High-risk workload | Open assigned requirements with High/Critical risk. |
| Invitation statistics | Stored invitation statuses; a pending invitation at/past expiry counts as expired immediately. Valid pending invitees are shown separately from registered users. |
| Quality trends | Last six creation months with data; current mean risk score among scored records, requirement count and current approved count. These are creation cohorts, not historical quality snapshots. |
| Project progress | Approved / matching requirements × 100. |
| Recent activity | Latest 50 recorded events (6 on overview), newest first; logging starts with this upgrade. |

There is no existing Rejected status or separate quality-score field. The
dashboard preserves Needs Revision and uses saved risk analysis rather than
inventing rejection counts or converting risk into a fabricated quality score.

The requirement query aggregates each child table before joining, so multiple
criteria and scenarios do not multiply counts. The dashboard uses a fixed set
of queries rather than per-card/per-user queries. Filtering/aggregation occurs
in Python after one requirement projection, which is straightforward at FYP
scale. Large deployments should move filtering/pagination/aggregations into SQL
and paginate team/invitation data as well.

## Security and configuration

- Server-side `admin` checks cover every management endpoint; unauthenticated
  callers receive 401 and other roles receive 403.
- Mutations require the existing session CSRF token and validated inputs.
- Assignment accepts only active SQA Engineers. Transactions and row locks on
  PostgreSQL / immediate transactions on SQLite coordinate assignment and role changes.
- Disabling users or changing their role invalidates previous sessions. Open
  assignments are cleared if that user can no longer review; completed history remains.
- Password changes verify the current hash, require 12–128 characters, use scrypt,
  and invalidate all previous sessions. No manager password reset/backdoor is added.
- Dashboard DTOs omit password hashes, token hashes, verification state and session secrets.
- Activity stores meaningful actions without raw invitation links/tokens or passwords.
- Existing invitation expiry, one-use acceptance, duplicate prevention and temporary
  verification lock behavior are unchanged; see [INVITATIONS.md](INVITATIONS.md).

No new environment variables or email provider are required. Continue using the
existing `DATABASE_URL` (or SQLite fallback), `REQQUALITY_SECRET_KEY`,
`SESSION_COOKIE_SECURE`, `FRONTEND_ORIGINS`, and invitation SMTP configuration.
Company name and overdue threshold are saved through Organization Settings.

## Run and verify

From the project root, start the backend:

```powershell
.\backend\.venv\Scripts\python.exe backend/app.py
```

In a second terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Sign in with an existing `admin` account. Open `/#admin` if necessary. No changes
to your existing password or admin email are required.

Automated verification from the project root:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
```

Frontend production verification:

```powershell
Set-Location frontend
npm.cmd run build
```

Tests use temporary SQLite databases and mocked invitation delivery. They never
seed the configured database or send real email. The dashboard tests cover
empty/no-user states, real aggregates without child-join duplication, nullable
analysis/risk, filtering and date boundaries, role authorization, CSRF,
assignment/reassignment, disabling/reenabling users, session revocation,
protected manager accounts, password changes, organization settings,
invitation status projection, safe response fields, and original requirement/review APIs.

Browser checks use an isolated local fixture to verify dashboard rendering,
KPI filtering, reviewer reassignment, existing detail/review navigation, team
controls, invitation form entry, profile/settings navigation, persistence and
mobile layout. Both Analyst and SQA Engineer browser sessions displayed Forbidden
on manager routes and received 403 from the manager API. A guest could visit Home
and received 401 from the manager API.

Executed results (2026-10-06):

- Full unittest discovery: **47 tests passed** (18 dashboard + 29 invitation).
- After tightening date/reviewer input validation: **18 dashboard tests passed again**.
- `npm.cmd run build`: passed (Vite production build).
- Python compilation and `git diff --check`: passed; Git emitted only line-ending notices.
- Isolated browser checks listed above: passed. At 390px viewport width the
  document width was also 390px, with no horizontal page overflow or Vite overlay.
  The browser reported no uncaught application errors.
- No live database changes or real invitation emails were used for these checks.

Remaining scope: real multi-project/tenant separation, historical score
snapshots, conflict analysis and a separate rejection workflow require product
and schema decisions. PostgreSQL migration/import execution must also be
validated against a disposable PostgreSQL database before production deployment;
the local integration suite exercises SQLite.
