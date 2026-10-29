# AI Review Assistant

Implemented 28 October 2026 using the existing Flask, React, Gemini, project access,
cookie authentication, CSRF, case versions, requirement history and review permissions.

## Use

- Open requirement details. Use **Request AI Revision** on an active current case,
  or select up to 30 cases for shared feedback. **Discuss requirement coverage**
  opens requirement context with up to 100 active cases as read-only coverage context.
- The side panel identifies the requirement and selected cases. Each user/requirement/
  selection has a separate durable conversation; reopening resumes it. Switching
  requirement or selection remounts the panel and ignores responses from the old panel.
- Describe the requested improvement. The assistant can return a clarification,
  coverage discussion, or validated proposal with existing revisions, new cases, and
  duplicate archival. Saved and proposed fields appear together; changed fields are marked.
- Follow-up feedback uses server-loaded source, saved case snapshots, relevant history
  and the latest unaccepted proposal. Older proposals become non-actionable when a
  successful follow-up arrives. Failed generation preserves feedback and the prior proposal.
- **Accept Changes** atomically creates case versions with **Pending Review** status.
  Existing IDs and scenario codes stay stable. New cases link to the same requirement.
  Duplicate removal archives the record and preserves its versions and executions.
  **Reject** changes no saved case. Retrying acceptance cannot create duplicate cases.
- Start case review and approve through the existing SQA review controls. Acceptance
  is separate from approval, including revisions of previously approved cases.

## Permissions and integrity

Analysts with `create_requirements` and SQA Engineers with `review_requirements` may
use their own review conversations. Acceptance requires an SQA Engineer with the
existing review permission who is not the requirement author. Analysts cannot accept
or approve cases. Admin/Manager accounts do not acquire test preparation rights.
Every endpoint enforces authentication, project access, conversation ownership and CSRF.
The application currently supports its existing single project, `current`.

Client requests contain case IDs, feedback and an idempotency key; they cannot supply
trusted requirement/case content, actor identity, timestamps or an acceptance payload.
The server retrieves context and validates proposal shape, field bounds, enums,
selected IDs and criterion links. Instructions require clarification for ambiguity or
unsupported behavior. Human review remains necessary to judge semantic correctness.
Requirement revision, project context and complete selected case snapshots must still
match at acceptance, otherwise the reviewer must regenerate. Existing version snapshots
and approval events are preserved; conversation turns retain feedback, proposed content,
summaries, original snapshots, actor/time and acceptance/rejection identity/time.

Generation releases the database connection before calling Gemini. One request per
conversation can run at a time; request keys deduplicate retries. Failed or interrupted
requests can retry, with a 60-second recovery lease and bounded 25-second provider call.
No raw provider exception, credential, or prompt is logged by the assistant adapter.

## Setup

No new packages or frontend credentials are needed. Configure the existing backend
`GEMINI_API_KEY` and `GEMINI_MODEL`. The same Gemini SDK is used with a JSON response
schema. AI failures remain visible with retry; there is no fabricated fallback.

Schema version **20261028** adds `ai_review_conversations` and `ai_review_turns` and
their indexes through the existing SQLite/PostgreSQL initializer. No destructive table
changes are required. Restart the backend after updating; its normal initialization
applies the additive schema to its configured database. Build frontend with
`npm.cmd run build` from `frontend`.

The production PostgreSQL schema was **not migrated or mutated during this work**.
Verification used disposable SQLite. PostgreSQL DDL uses the existing adapter patterns
but this new migration has not been executed against live PostgreSQL.
Nothing was pushed or deployed.

## Verification evidence

- `audit/ai-review-regression.txt`: 44 passing backend tests covering the assistant,
  detailed cases, integrated reporting, existing AI workflow and project migrations.
  Assistant coverage includes backend role/permission/project/CSRF/ownership checks,
  atomic acceptance, approval reset, immutable history, stale requirement/case/project
  rejection, multi-case archival, clarification/discussion, schema rejection, failed
  feedback persistence, retry idempotency and interrupted-generation recovery.
- `audit/ai-review-frontend.txt`: 21 passing frontend tests, including escaped provider
  text, unchanged saved content, field highlighting and separately labeled new cases.
- `audit/ai-review-build.txt`: production build passed.
- `audit/ai-review-browser/result.json`: real Chrome + Flask/auth/SQLite journey with a
  mocked provider: failure, retry, duplicate submit protection, follow-up, preview,
  Pending Review acceptance and context isolation; zero uncaught browser exceptions.
  Light/dark/mobile screenshots are in the same folder.
- `audit/ai-review-live.json`: one **real Gemini** request with synthetic context,
  HTTP 200, validated revision proposal, saved case unchanged. This verifies provider
  integration; it is not evidence of production PostgreSQL workflow verification.

Reproduce backend checks from `backend` with the local virtualenv:

```powershell
./.venv/Scripts/python.exe -m unittest test_review_assistant test_test_cases test_integrated_reporting test_ai_workflow test_project_migration -q
```

Run `npm.cmd test` and `npm.cmd run build` from `frontend`. The optional browser script
`audit/verify_ai_review_browser.py` requires installed Chrome and the existing virtualenv.
`audit/verify_ai_review_live.py` uses provider quota and only synthetic isolated data.
