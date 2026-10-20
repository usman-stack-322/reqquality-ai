# Requirement analysis evaluation set

Reviewed against supplied facts and the V1 contract by Codex on 20 October 2026.
These synthetic examples and review expectations are an initial engineering rubric,
not stakeholder approval or a statistically representative quality benchmark.

`requirement_cases.json` contains seven cases: clear behavior, vague usability,
contradictory policies, functional ownership scope, security authorization,
unspecified performance, and fully specified performance. Each records project
context separately from the requirement and identifies facts that must be preserved
and decisions that must not be invented. No numeric quality score or heuristic
fallback is computed from this rubric.

For every returned output, review:

1. Does the suggested type and explanation fit the supplied behavior/quality concern?
2. Are named actors, authorization boundaries and supplied numerical targets retained?
3. Are genuinely missing decisions identified, with direct clarification questions?
4. Does refinement preserve unresolved decisions rather than choose a policy?
5. Are dependent criteria/scenarios blocked or conditional where facts are absent?
6. Do qualitative risk/priority explanations describe uncertainty without fabricating
   business consequences, regulations, deadlines, limits or performance thresholds?
7. Are unsupported proposals clearly marked as unconfirmed?

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe evaluate_analysis.py --live --output ../audit/analysis-live-evaluation.jsonl
```

This is an explicit, quota-consuming real-provider run on synthetic text only. It
never opens the application database. A failed call has no quality assessment;
structural validity alone is insufficient to establish semantic quality.

## This run

The configured model was listed as available for generation, but no analysis output
was returned successfully. Six cases returned HTTP 504/deadline failures after
roughly 20–25 seconds; the functional case ended with a transport ReadError after
about 38 seconds. A separate minimal generation also returned HTTP 504 after 15.1
seconds. No case can be graded for semantic quality. See
`audit/analysis-live-evaluation.jsonl`, `audit/analysis-model-availability.json` and
`audit/analysis-minimal-provider.json`.

Integration tests in `test_analysis_v1.py`, `test_ai_workflow.py`, and the browser
journey explicitly mock Gemini. They verify schemas, errors, security, persistence,
cache scope and human-edit behavior; they do not demonstrate real model quality.
