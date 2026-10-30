# ReqQuality AI: AI-Powered Requirements & Software Quality Engineering Platform

FYP proposal presentation: **4 November 2026**<br>
Prepared: **30 October 2026**<br>
Supervisor: **Maam Amina Ghulam Rasool**

| Team member | Roll number |
| --- | --- |
| Muhammad Usman | 28104 |
| Hassaan Majid | 27916 |
| Hassan Shabbir | 27915 |

Title, supervisor and team details were confirmed by the team in this chat.
This identifies the project; it does not assert supervisor, committee or university
approval. This three-member document supersedes the outdated solo-project description
and unconfirmed supervisor field in the 5 October working document. That source file
has been preserved, not overwritten.

## Abstract and problem

Natural-language requirements can be ambiguous, incomplete, or difficult to test.
Analysts and SQA Engineers need a clear path from an original requirement to reviewable
criteria and test cases, with evidence of what changed and who reviewed it. Manual
drafting and disconnected documents can make this process repetitive and hard to trace.

ReqQuality AI is a human-reviewed prototype that uses a server-side language model to
suggest requirement improvements, acceptance criteria, risk/priority explanations and
test scenarios. A context-aware AI Review Assistant supports feedback-based test case
revision. Suggestions are proposals: accepting them and approving them are separate
actions. Version history connects saved requirements, cases, manual execution records,
defects, reviews and reports.

The proposal is to develop and evaluate this workflow. A working prototype already
exists; successful rehearsals demonstrate particular flows, not general model accuracy,
complete test coverage, production readiness, or an approved academic outcome.

## Objectives

1. Capture and preserve original requirements and relevant project context.
2. Produce structured, reviewable AI suggestions and explain quality risks.
3. Generate linked positive, negative and boundary/edge scenarios when supported by
   source behavior; ask for clarification when expected behavior is unspecified.
4. Support conversational revision, saved/proposed comparison, rejection and explicit
   acceptance without silently changing active cases.
5. Enforce Analyst/SQA permissions, independent approval and version traceability.
6. Export saved evidence in readable PDF and CSV reports.
7. Evaluate usefulness, correctness, failure recovery and usability using an explicit
   evaluation protocol rather than claiming unmeasured accuracy or time savings.

## Current scope versus proposed evaluation

| Area | Current prototype | Limits / work still requiring evidence |
| --- | --- | --- |
| Accounts | Cookie-token login, CSRF, admin invitations, role permissions | Hosted PostgreSQL login currently blocked by network/access conditions; email delivery needs configured SMTP |
| Requirements | Draft, AI proposal, explicit acceptance, submission, review | Source quality still depends on stakeholder clarification |
| AI analysis | Gemini structured response, schema validation, explicit error/retry | Provider/network/quota dependency; no guarantee against unsupported semantics |
| Review Assistant | Per-case and shared feedback, saved context/history, revision/new-case/duplicate-archive proposals | Conversations are user/selection scoped; Analysts cannot accept cases on behalf of SQA |
| Approval | Accepted revisions become Pending Review; separate SQA case approval; separate requirement review | Approval records a human review, not proof of external software correctness |
| Traceability | Requirement/case versions, review events, manual execution and bug links | Linked coverage measures mappings, not exhaustive behavioral adequacy |
| Reports | Saved-data PDF/CSV, version/evidence links, progress/error feedback | Very large histories and hosted cold starts are not capacity-tested |
| Project model | Existing shared `current` project and project-access grant | No multi-tenant hosting claim |
| UI | Role-specific workspace, light/dark/system, responsive forms | Compared with the supplied 29 October login screenshot and AI Shorts reference; local checks do not establish hosted reliability |

## Architecture and AI method

React/Vite renders the role-specific interface. Flask routes delegate to services for
authentication, requirements, cases, AI conversations, review, traceability and reports.
PostgreSQL is supported through the existing pooled adapter; an explicit SQLite target
provides isolated local demonstrations. PostgreSQL failures do not silently select SQLite.

Gemini credentials remain on the server. Requirement analysis and conversational case
revision use validated structured model responses. Current generation does **not** use
rule-based analysis or an automatic fallback engine. Historical `rule_based` provenance
can still be read for old records; input validation, state transitions and schema checks
are ordinary application controls, not a rule-based quality-scoring methodology.

Revision generation retrieves the original requirement, selected saved cases, project
context and conversation history from the backend. It does not trust browser-provided
content as the saved source. Acceptance verifies the source/case context is unchanged,
preserves stable identifiers, records versions, and requires approval again. Rejection
does not modify saved cases. Only a permitted SQA Engineer can approve cases; authors
cannot prepare/approve their own verification cases through the SQA workflow.

## Evaluation plan (proposed, not completed results)

- Assemble a documented set of clear, ambiguous, incomplete and boundary-focused
  requirements with human reference judgments. Record who reviewed each example.
- Measure schema validity, unsupported assumptions, criterion linkage correctness,
  useful versus rejected suggestions and clarification quality.
- Ask Analysts and SQA reviewers to complete representative tasks; record task success,
  observed confusion and completion time with a defined comparison procedure.
- Evaluate unauthorized access, duplicate submission, stale proposals, provider failure,
  approval invalidation and history preservation using isolated integration tests.
- Record timing stages separately: database connection, password verification, report
  data access, rendering and response. Small local measurements cannot establish hosted
  reliability or a statistically significant productivity improvement.

Do not present model precision/recall, percentage time savings, user-study results,
supervisor approval or completed deployment unless supported by separately collected evidence.

## Delivery plan before the presentation

| Date | Planned activity |
| --- | --- |
| 30 October | Current-code review, isolated checks and documentation alignment |
| 31 October–2 November | Team review of scope, terminology, slides and known limitations |
| 3 November | Rehearse the exact local flow; confirm demo credentials privately and AI availability; retain clearly labeled saved evidence |
| 4 November | Present problem, prototype, demonstration, evaluation plan and limitations |

Future dates describe plans, not completed work. Technical verification and current
blockers are recorded separately in `docs/FYP_READINESS_REPORT.md`.
