# ReqQuality AI — WBS 3.5.4 Controlled Evaluation Report

- **Generated (UTC)**: `2026-11-23T15:06:01+00:00`
- **Evaluation Mode**: `--mode fixture` (deterministic offline Gemini payloads + real Flask/SQLite workflow, RBAC, value_safety, and ReportLab/CSV pipelines)
- **Benchmark Dataset**: [`fyp_benchmark_cases.json`](../../backend/evaluation/fyp_benchmark_cases.json) (`12` requirements across `5` categories)
- **Model Configuration**: provider=`gemini`, model=`gemini-3.5-flash-lite`, temperature=`0.2`

> [!NOTE]
> Per our FYP proposal governance rules, `--mode fixture` validates schema enforcement, `value_safety.py` introduced-value detection, RBAC separation of duties, and export pipeline timings deterministically offline. Live semantic accuracy claims require running `--mode live` with `GEMINI_API_KEY` alongside human rubric review and the SUS user study (`USER_STUDY_PROTOCOL.md`).

## 1. Executive Summary

| Metric | Measured Result |
| --- | --- |
| Schema Validity Pass Rate (12 Cases) | **100.0%** (12/12) |
| Negative Schema Guard Probes Rejected | **5/5** |
| `value_safety.py` Introduced-Value Catches | **23** across **5** cases (0 false positives on boundary/well-formed) |
| Unconfirmed Flag Coverage (`needs_confirmation=True`) | **100% Enforced** |
| AI Analysis Pipeline Latency (Mean / p95) | **1.65 ms** / **2.64 ms** (`n=12`) |
| Requirement PDF Export Mean / p95 (3 samples) | **410.94 ms** / **845.85 ms** (46471 bytes) |
| Project Summary PDF Mean / p95 (3 samples) | **492.25 ms** / **570.49 ms** (87730 bytes) |
| Requirements CSV Export Mean / p95 (3 samples) | **59.55 ms** / **64.0 ms** (137479 bytes) |
| RBAC Permission Enforcement Checks | **13/13 passed** (Analyst self-approval blocked: **HTTP 403**) |

## 2. Benchmark Dataset & Per-Requirement Results

| ID | Category | Type | Status | Schema Valid | Criteria | Scenarios | `value_safety` Catches | Latency (ms) |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `REQ-EVAL-01` | `ambiguous` | Non-Functional | `completed` | Pass | 2 | 1 | 4 (2 seconds) | 2.45 |
| `REQ-EVAL-02` | `ambiguous` | Functional | `completed` | Pass | 1 | 1 | 7 (500 ms, GDPR) | 1.47 |
| `REQ-EVAL-03` | `ambiguous` | Non-Functional | `completed` | Pass | 1 | 1 | 7 (30 minutes, TLS 1.3) | 1.71 |
| `REQ-EVAL-04` | `incomplete` | Non-Functional | `completed` | Pass | 2 | 2 | 4 (1000 users, 200 ms) | 1.67 |
| `REQ-EVAL-05` | `incomplete` | Functional | `completed` | Pass | 1 | 1 | 0 (None) | 1.28 |
| `REQ-EVAL-06` | `incomplete` | Non-Functional | `completed` | Pass | 1 | 1 | 1 (HTTP 429) | 1.28 |
| `REQ-EVAL-07` | `conflicting` | Functional | `completed` | Pass | 1 | 1 | 0 (None) | 1.1 |
| `REQ-EVAL-08` | `conflicting` | Business | `completed` | Pass | 1 | 1 | 0 (None) | 1.22 |
| `REQ-EVAL-09` | `boundary_heavy` | Functional | `completed` | Pass | 2 | 2 | 0 (None) | 2.64 |
| `REQ-EVAL-10` | `boundary_heavy` | Non-Functional | `completed` | Pass | 2 | 1 | 0 (None) | 2.29 |
| `REQ-EVAL-11` | `well_formed` | Functional | `completed` | Pass | 2 | 2 | 0 (None) | 1.17 |
| `REQ-EVAL-12` | `well_formed` | Non-Functional | `completed` | Pass | 2 | 2 | 0 (None) | 1.55 |

### Category Coverage Summary

| Category | Cases | Schema Valid |
| --- | ---: | ---: |
| `ambiguous` | 3 | 3/3 |
| `incomplete` | 3 | 3/3 |
| `conflicting` | 2 | 2/2 |
| `boundary_heavy` | 2 | 2/2 |
| `well_formed` | 2 | 2/2 |

### Negative Schema-Guard Probes (`analyzers/llm_analyzer.py`)

| Probe | Malformed Output Condition | Rejected (`None`) |
| --- | --- | --- |
| `non_dict_payload` | Top-level JSON is a list rather than an object | Yes |
| `invalid_risk_level_enum` | Unsupported `risk_level` value outside allowed enum | Yes |
| `empty_test_scenarios` | Empty `test_scenarios` list with zero scenarios | Yes |
| `missing_info_without_clarification_questions` | Non-empty `missing_information` paired with empty `clarification_questions` | Yes |
| `dangling_criterion_code_ac999` | Scenario references non-existent `AC-999` code | Yes |

## 3. `value_safety.py` Introduced-Value & Hallucination Audit

- **Total Introduced-Value Matches Flagged**: `23` across `5` requirements
- **Distinct Values Flagged**: `2 seconds, 500 ms, GDPR, 30 minutes, TLS 1.3, 1000 users, 200 ms, HTTP 429`
- **False Positives on Boundary-Heavy / Well-Formed Cases**: `0`

## 4. Export Pipeline Stage Timings (`Server-Timing`)

| Export Format | Bytes | Total Mean / p95 (ms) | `report_data` Mean / p95 (ms) | `report_render` Mean / p95 (ms) | `report_response` Mean / p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `requirement_pdf` | 46471 | 410.94 / 845.85 | 11.2 / 11.2 | 387.8 / 822.2 | 0.57 / 0.6 |
| `project_pdf` | 87730 | 492.25 / 570.49 | 22.63 / 24.9 | 459.33 / 537.5 | 0.3 / 0.4 |
| `requirements_csv` | 137479 | 59.55 / 64.0 | 24.6 / 28.4 | 23.47 / 31.1 | 0.63 / 0.7 |

## 5. Automated RBAC Permission Enforcement Matrix

| Verification Check | Actor | Expected HTTP | Actual HTTP | Result |
| --- | --- | ---: | ---: | --- |
| `guest_blocked_requirements_list` | Unauthenticated Guest | 401 | 401 | PASS |
| `guest_blocked_project_pdf_export` | Unauthenticated Guest | 401 | 401 | PASS |
| `analyst_cannot_self_approve_requirement_review` | Analyst (Requirement Author) | 403 | 403 | PASS |
| `analyst_cannot_self_approve_via_review_status` | Analyst (Requirement Author) | 403 | 403 | PASS |
| `analyst_cannot_create_sqa_test_case` | Analyst | 403 | 403 | PASS |
| `analyst_cannot_self_approve_test_case` | Analyst | 403 | 403 | PASS |
| `analyst_cannot_accept_ai_review_revision_proposal` | Analyst | 403 | 403 | PASS |
| `sqa_engineer_cannot_create_requirements` | SQA Engineer | 403 | 403 | PASS |
| `sqa_engineer_cannot_invoke_analyst_ai_endpoint` | SQA Engineer | 403 | 403 | PASS |
| `admin_cannot_approve_sqa_decisions` | Admin | 403 | 403 | PASS |
| `missing_csrf_token_rejected_on_write` | Analyst (No CSRF) | 403 | 403 | PASS |
| `independent_sqa_engineer_can_approve_requirement` | SQA Engineer (Non-Author) | 200 | 200 | PASS |
| `role_promoted_author_still_blocked_from_self_approval` | Author Promoted to SQA Engineer | 403 | 403 | PASS |

## 6. Reproducibility Commands

```powershell
# Offline deterministic CI/local verification (no API quota used)
.\backend\.venv\Scripts\python.exe backend/evaluation/run_fyp_evaluation.py --mode fixture

# Live Google Gemini empirical run (requires GEMINI_API_KEY and GEMINI_MODEL in environment or backend/.env)
.\backend\.venv\Scripts\python.exe backend/evaluation/run_fyp_evaluation.py --mode live
```
