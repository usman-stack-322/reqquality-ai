"""Reproducible WBS 3.5.4 evaluation runner for ReqQuality AI.

Evaluates schema validity, value_safety introduced-value detection, AI latency,
PDF/CSV export stage timings, and RBAC permission boundaries against a curated
12-requirement benchmark dataset in either deterministic `--mode fixture` or
live Gemini `--mode live`.
"""

import argparse
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from io import BytesIO, StringIO
import json
import logging
import math
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_DATASET = Path(__file__).resolve().parent / 'fyp_benchmark_cases.json'
DEFAULT_JSON_OUTPUT = REPO_ROOT / 'docs' / 'evaluation' / 'latest_evaluation_results.json'
DEFAULT_REPORT_OUTPUT = REPO_ROOT / 'docs' / 'evaluation' / 'EVALUATION_REPORT.md'
EVAL_PASSWORD = 'eval-only-password-123'


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil((pct / 100.0) * len(ordered)))
    return round(ordered[rank - 1], 2)


def _timing_summary(values):
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return {'count': 0, 'min_ms': None, 'mean_ms': None, 'median_ms': None, 'p95_ms': None, 'max_ms': None}
    ordered = sorted(cleaned)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    return {
        'count': len(cleaned),
        'min_ms': round(ordered[0], 2),
        'mean_ms': round(sum(cleaned) / len(cleaned), 2),
        'median_ms': round(median, 2),
        'p95_ms': _percentile(cleaned, 95),
        'max_ms': round(ordered[-1], 2),
    }


def _parse_server_timing(header):
    metrics = {}
    for entry in (header or '').split(','):
        parts = [part.strip() for part in entry.split(';') if part.strip()]
        if not parts:
            continue
        name = parts[0]
        for attr in parts[1:]:
            if attr.startswith('dur='):
                try:
                    metrics[name] = float(attr.split('=', 1)[1])
                except ValueError:
                    pass
    return metrics


def _build_fixture_payload(case):
    """Build deterministic schema-valid raw LLM outputs for `--mode fixture`.

    Select ambiguous/incomplete cases intentionally include concrete unconfirmed
    values so `analyzers.value_safety` detects and labels them cleanly.
    """
    cid = case['id']
    category = case['category']

    if cid == 'REQ-EVAL-01':
        return {
            'ambiguity_issues': ['"fast", "intuitive", and "easy" lack measurable acceptance thresholds.', '"across devices" does not list target viewport widths or browsers.'],
            'conflict_issues': [],
            'missing_information': ['What p95 checkout step latency is required?', 'Which mobile and desktop browsers are in scope?'],
            'clarification_questions': ['What maximum checkout response time in seconds is acceptable?', 'Which device viewports and assistive-tech baselines must pass?'],
            'testability_issues': ['Subjective terms ("fast", "easy") cannot produce deterministic pass/fail checks.'],
            'assumptions': ['UNCONFIRMED SUGGESTION: Checkout API confirmation renders within 2 seconds on broadband connections.'],
            'edge_cases': ['Payment gateway timeout after checkout submission.'],
            'acceptance_criteria': [
                'UNCONFIRMED SUGGESTION: Checkout step transitions complete within 2 seconds for authenticated shoppers.',
                'Cart summary and order confirmation render without horizontal overflow on mobile and desktop viewports.',
            ],
            'risk_reasons': ['Unmeasured speed/usability targets increase rework and stakeholder disagreement during SQA sign-off.'],
            'priority_reasons': ['High business impact on checkout conversion requires stakeholder confirmation of measurable SLA bounds.'],
            'improved_requirement': 'The retail checkout workflow shall complete each step [TO BE CONFIRMED: within 2 seconds target response time] and remain navigable on agreed desktop and mobile viewports.',
            'suggested_requirement_type': 'Non-Functional',
            'type_explanation': 'Focuses on responsiveness and usability quality attributes across devices.',
            'risk_level': 'High',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Positive',
                    'title': 'BLOCKED pending clarification: Checkout transition speed',
                    'preconditions': ['Shopper holds items in an active cart.'],
                    'test_steps': ['Proceed from cart review to payment confirmation.', 'Measure transition latency against stakeholder-confirmed SLA.'],
                    'expected_result': 'BLOCKED pending clarification: Confirm whether checkout must respond within 2 seconds before Pass/Fail sign-off.',
                    'criterion_codes': ['AC-001', 'AC-002'],
                },
            ],
        }

    if cid == 'REQ-EVAL-02':
        return {
            'ambiguity_issues': ['"timely" and "important workspace events" are undefined.'],
            'conflict_issues': [],
            'missing_information': ['Which workspace events trigger notifications?', 'Which delivery channels (in-app vs email) and latency bounds apply?'],
            'clarification_questions': ['Which exact requirement/review events require notifications?', 'What delivery latency and opt-out rules apply under GDPR?'],
            'testability_issues': ['No event enumeration or timing window is supplied.'],
            'assumptions': ['UNCONFIRMED SUGGESTION: Notifications deliver within 500 ms for in-app alerts and respect GDPR consent.'],
            'edge_cases': ['Recipient disables notification channel mid-review.'],
            'acceptance_criteria': [
                'UNCONFIRMED SUGGESTION: Triggered notifications dispatch within 500 ms while honoring GDPR recipient preferences.',
            ],
            'risk_reasons': ['Undefined trigger events and privacy obligations risk alert fatigue or missed review handoffs.'],
            'priority_reasons': ['Medium workflow priority pending event catalog confirmation.'],
            'improved_requirement': 'The workspace shall dispatch notifications for [TO BE CONFIRMED: list of review/defect events] [TO BE CONFIRMED: within 500 ms in-app under GDPR policy].',
            'suggested_requirement_type': 'Functional',
            'type_explanation': 'Defines event-driven notification behavior for workspace stakeholders.',
            'risk_level': 'Medium',
            'suggested_priority': 'Medium',
            'test_scenarios': [
                {
                    'category': 'Positive',
                    'title': 'BLOCKED pending clarification: Notification trigger dispatch',
                    'preconditions': ['Stakeholder participates in an active workspace project.'],
                    'test_steps': ['Trigger a stakeholder-agreed workspace event.', 'Inspect delivery channel log.'],
                    'expected_result': 'BLOCKED pending clarification: Confirm event list and timing window before executing test.',
                    'criterion_codes': ['AC-001'],
                },
            ],
        }

    if cid == 'REQ-EVAL-03':
        return {
            'ambiguity_issues': ['"reasonable period" and "safely" do not define an inactivity window or cookie clearing contract.'],
            'conflict_issues': [],
            'missing_information': ['What idle timeout duration ends a user session?', 'Are TLS versions and warning prompts required?'],
            'clarification_questions': ['How many minutes of inactivity trigger automatic sign-out?', 'Must inactive sessions end with TLS 1.3 cookie revocation?'],
            'testability_issues': ['Untestable idle expiration interval without a numeric duration.'],
            'assumptions': ['UNCONFIRMED SUGGESTION: Idle sessions lock after 30 minutes over TLS 1.3 transport.'],
            'edge_cases': ['User submits a form at the exact session expiry boundary.'],
            'acceptance_criteria': [
                'UNCONFIRMED SUGGESTION: Idle sessions terminate after 30 minutes and clear auth cookies over TLS 1.3.',
            ],
            'risk_reasons': ['Session lifetime ambiguity directly affects credential exposure vs unsaved form loss.'],
            'priority_reasons': ['High security impact; stakeholders must confirm idle timeout rules.'],
            'improved_requirement': 'Idle sessions shall expire after [TO BE CONFIRMED: 30 minutes of inactivity] and revoke authentication cookies safely.',
            'suggested_requirement_type': 'Non-Functional',
            'type_explanation': 'Specifies security/session lifecycle behavior during inactivity.',
            'risk_level': 'High',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Boundary',
                    'title': 'BLOCKED pending clarification: Idle session expiration',
                    'preconditions': ['Authenticated user leaves workspace idle.'],
                    'test_steps': ['Wait until confirmed idle timeout elapses.', 'Attempt protected API request.'],
                    'expected_result': 'BLOCKED pending clarification: Confirm 30 minutes or approved timeout value before marking Pass/Fail.',
                    'criterion_codes': ['AC-001'],
                },
            ],
        }

    if cid == 'REQ-EVAL-04':
        return {
            'ambiguity_issues': ['"handle concurrent usage gracefully" lacks load and latency figures.'],
            'conflict_issues': [],
            'missing_information': ['What concurrent user count and response-time target must search meet?', 'What should happen on empty search strings or zero matches?'],
            'clarification_questions': ['How many concurrent users and milliseconds of latency define acceptable search load?', 'How should invalid/empty queries behave?'],
            'testability_issues': ['Concurrency load and degradation behavior are untestable as written.'],
            'assumptions': ['UNCONFIRMED SUGGESTION: Search supports 1000 users at 200 ms median latency.'],
            'edge_cases': ['Special regex characters or empty query submitted under load.'],
            'acceptance_criteria': [
                'Keyword search filters project requirements and returns matching summaries for valid queries.',
                'UNCONFIRMED SUGGESTION: Search completes within 200 ms under 1000 users concurrent load.',
            ],
            'risk_reasons': ['Missing workload parameters may cause underestimated indexing or timeout limits.'],
            'priority_reasons': ['High visibility search capability needs confirmed concurrency bounds.'],
            'improved_requirement': 'Authenticated users can search stored project requirements by keyword, returning paginated matches under [TO BE CONFIRMED: target concurrent load and latency threshold].',
            'suggested_requirement_type': 'Non-Functional',
            'type_explanation': 'Primary uncertainty concerns load capacity and latency under concurrent access.',
            'risk_level': 'High',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Positive',
                    'title': 'Keyword search returns matching requirement summaries',
                    'preconditions': ['Project contains saved requirements matching the keyword.'],
                    'test_steps': ['Submit a valid keyword query.', 'Inspect returned matches.'],
                    'expected_result': 'Matching requirements display cleanly without unmatched records.',
                    'criterion_codes': ['AC-001'],
                },
                {
                    'category': 'Boundary',
                    'title': 'BLOCKED pending clarification: Search load throughput',
                    'preconditions': ['Load harness configured for agreed concurrent users.'],
                    'test_steps': ['Run search requests at agreed concurrency.', 'Record latency percentile.'],
                    'expected_result': 'BLOCKED pending clarification: Confirm target concurrency and latency budget.',
                    'criterion_codes': ['AC-002'],
                },
            ],
        }

    if cid == 'REQ-EVAL-05':
        return {
            'ambiguity_issues': ['"filtered workspace activity logs" omits filter attributes and output file format.'],
            'conflict_issues': [],
            'missing_information': ['Which export format (CSV/JSON/PDF) is required?', 'What date-range, actor filter fields, timezone, and row limits apply?'],
            'clarification_questions': ['Which file format(s) must the export produce?', 'What filter fields and maximum row limits should be enforced?'],
            'testability_issues': ['Output format and empty-filter outcomes are missing.'],
            'assumptions': ['UNCONFIRMED SUGGESTION: Export returns CSV/JSON filtered by actor and UTC date range.'],
            'edge_cases': ['Filter matches zero audit events.'],
            'acceptance_criteria': [
                'Administrators can request an audit log export scoped by agreed filters ([TO BE CONFIRMED: format and maximum row window]).',
            ],
            'risk_reasons': ['Unspecified format and upper bounds can lead to slow or unbounded exports.'],
            'priority_reasons': ['Medium compliance reporting priority pending schema confirmation.'],
            'improved_requirement': 'Administrators can export workspace activity logs filtered by [TO BE CONFIRMED: actor, event type, date range] in [TO BE CONFIRMED: approved format].',
            'suggested_requirement_type': 'Functional',
            'type_explanation': 'Describes an administrative filtering and data-export feature.',
            'risk_level': 'Medium',
            'suggested_priority': 'Medium',
            'test_scenarios': [
                {
                    'category': 'Edge-case',
                    'title': 'BLOCKED pending clarification: Filtered audit export format and empty results',
                    'preconditions': ['Administrator is signed in with audit access.'],
                    'test_steps': ['Apply filter criteria.', 'Trigger export download.'],
                    'expected_result': 'BLOCKED pending clarification: Confirm file format and empty-result behavior.',
                    'criterion_codes': ['AC-001'],
                },
            ],
        }

    if cid == 'REQ-EVAL-06':
        return {
            'ambiguity_issues': ['"protect user accounts" and "repeated" lack lockout thresholds and HTTP responses.'],
            'conflict_issues': [],
            'missing_information': ['How many failed attempts trigger throttling or lockout?', 'How long is the cooldown window and how are locked accounts recovered?'],
            'clarification_questions': ['What failed-attempt count triggers throttling?', 'Does protection return HTTP 429 rate limits, temporary lock, or CAPTCHA?'],
            'testability_issues': ['Threshold and cooldown behavior must be specified before boundary testing.'],
            'assumptions': [],
            'edge_cases': ['Legitimate user enters typo repeatedly behind a shared NAT IP.'],
            'acceptance_criteria': [
                'Failed sign-in attempts are tracked per [TO BE CONFIRMED: identity/IP window] and throttled after [TO BE CONFIRMED: retry limit].',
            ],
            'risk_reasons': ['Security control thresholds cannot be verified without exact retry/window definitions.'],
            'priority_reasons': ['High account-security impact requires prompt stakeholder alignment.'],
            'improved_requirement': 'The authentication service shall rate-limit failed sign-in attempts beyond [TO BE CONFIRMED: N attempts within W window] and return an explicit cooldown notice.',
            'suggested_requirement_type': 'Non-Functional',
            'type_explanation': 'Focuses on authentication abuse resistance and security protection.',
            'risk_level': 'High',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Negative',
                    'title': 'BLOCKED pending clarification: Exceeding failed sign-in threshold',
                    'preconditions': ['Account exists and rate-limit threshold is defined.'],
                    'test_steps': ['Submit failed credentials up to threshold + 1.'],
                    'expected_result': 'BLOCKED pending clarification: Confirm retry count and cooldown HTTP status.',
                    'criterion_codes': ['AC-001'],
                },
            ],
        }

    if category == 'conflicting':
        is_transfer = cid == 'REQ-EVAL-07'
        return {
            'ambiguity_issues': [],
            'conflict_issues': [
                'Direct policy contradiction: requires both always sending and never sending transfer confirmation emails.'
                if is_transfer else
                'Direct lifecycle contradiction: requires both permanent deletion by managers and non-deletable immutable audit retention.',
            ],
            'missing_information': ['Authoritative business rule deciding which conflicting policy takes precedence.'],
            'clarification_questions': [
                'Which rule takes precedence: sending confirmation emails for approved transfers or suppressing them?'
                if is_transfer else
                'Can managers delete historical review reports, or must all reports remain strictly immutable?',
            ],
            'testability_issues': ['Mutually exclusive expected results prevent deterministic verification.'],
            'assumptions': [],
            'edge_cases': ['Approval recorded while notification/retention policy remains undecided.'],
            'acceptance_criteria': [
                'BLOCKED pending clarification: Confirm whether approved transfers trigger confirmation emails or suppress them.'
                if is_transfer else
                'BLOCKED pending clarification: Confirm whether historical review reports allow deletion or require immutable retention.',
            ],
            'risk_reasons': ['Conflicting requirements of equal authority cannot be implemented safely without formal resolution.'],
            'priority_reasons': ['High priority blocker because implementation requires a binary policy decision.'],
            'improved_requirement': (
                '[TO BE CONFIRMED: Resolve conflict between sending vs. never sending confirmation email] when a transfer is approved.'
                if is_transfer else
                '[TO BE CONFIRMED: Resolve conflict between manager permanent report deletion vs. non-deletable immutable retention] for historical review reports.'
            ),
            'suggested_requirement_type': 'Functional' if is_transfer else 'Business',
            'type_explanation': 'Preserves original domain classification while flagging the policy conflict.',
            'risk_level': 'Critical',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Negative',
                    'title': 'BLOCKED pending clarification: Conflicting policy behavior',
                    'preconditions': ['Record is prepared for the contested transition.'],
                    'test_steps': ['Execute the transition under stakeholder-resolved policy.'],
                    'expected_result': 'BLOCKED pending clarification: Cannot assert expected behavior until conflict is resolved.',
                    'criterion_codes': ['AC-001'],
                },
            ],
        }

    if cid == 'REQ-EVAL-09':
        return {
            'ambiguity_issues': [],
            'conflict_issues': [],
            'missing_information': [],
            'clarification_questions': [],
            'testability_issues': [],
            'assumptions': [],
            'edge_cases': ['Expired token submitted after 24 hours vs valid token before expiry.'],
            'acceptance_criteria': [
                'Accepted passwords enforce minimum 12 and maximum 128 characters; shorter or longer passwords fail validation.',
                'Invitations remain valid for 24 hours, lock temporarily for 15 minutes after at most 5 failed verification attempts, and reset tokens expire after 1 hour.',
            ],
            'risk_reasons': ['Boundary-heavy authentication rules require exact off-by-one verification across limits.'],
            'priority_reasons': ['High security impact on onboarding and credential recovery.'],
            'improved_requirement': case['description'],
            'suggested_requirement_type': 'Functional',
            'type_explanation': 'Defines exact validation bounds and lifecycle expiry rules for onboarding and recovery.',
            'risk_level': 'Medium',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Boundary',
                    'title': 'Verify password lengths minimum 12 and maximum 128 characters',
                    'preconditions': ['Valid non-expired onboarding or reset token.'],
                    'test_steps': ['Test password lengths 11, 12, 128, and 129 characters.'],
                    'expected_result': 'Lengths minimum 12 and maximum 128 succeed; lengths 11 and 129 fail validation.',
                    'criterion_codes': ['AC-001'],
                },
                {
                    'category': 'Negative',
                    'title': 'Verify invitation expiry at 24 hours, 15 minutes lock after at most 5 attempts, and 1 hour reset TTL',
                    'preconditions': ['Active invitation and password reset tokens exist.'],
                    'test_steps': ['Exceed at most 5 mismatched email attempts.', 'Submit expired tokens after 24 hours and 1 hour.'],
                    'expected_result': 'Temporary 15 minutes lock activates; tokens older than 24 hours (invite) or 1 hour (reset) reject.',
                    'criterion_codes': ['AC-002'],
                },
            ],
        }

    if cid == 'REQ-EVAL-10':
        return {
            'ambiguity_issues': [],
            'conflict_issues': [],
            'missing_information': [],
            'clarification_questions': [],
            'testability_issues': [],
            'assumptions': [],
            'edge_cases': ['Response payload approaches 500 kb under peak 200 users load.'],
            'acceptance_criteria': [
                'Under 200 users simultaneously authenticated during a 30 minutes load test, 95% of shipment-status API requests complete within 2 seconds.',
                'Returned shipment-status response payloads remain at most 500 kb.',
            ],
            'risk_reasons': ['Sustained concurrent load SLA needs percentile telemetry verification under worst-case payload size.'],
            'priority_reasons': ['High production SLA priority directly affecting logistics clients.'],
            'improved_requirement': case['description'],
            'suggested_requirement_type': 'Non-Functional',
            'type_explanation': 'Quantitative load, latency percentile, duration, and payload-size SLA.',
            'risk_level': 'Medium',
            'suggested_priority': 'High',
            'test_scenarios': [
                {
                    'category': 'Positive',
                    'title': 'Verify p95 latency under 200 users over 30 minutes load test',
                    'preconditions': ['Load generator configured with 200 users authenticated credentials.'],
                    'test_steps': ['Execute sustained queries for 30 minutes.', 'Measure p95 latency and payload size.'],
                    'expected_result': '95% of requests complete within 2 seconds with payloads at most 500 kb.',
                    'criterion_codes': ['AC-001', 'AC-002'],
                },
            ],
        }

    if cid == 'REQ-EVAL-11':
        return {
            'ambiguity_issues': [],
            'conflict_issues': [],
            'missing_information': [],
            'clarification_questions': [],
            'testability_issues': [],
            'assumptions': [],
            'edge_cases': ['Book already archived is requested from public reader search.'],
            'acceptance_criteria': [
                'Authenticated librarians can archive an active book catalog record.',
                'Archived book records remain visible to authenticated librarians and never appear in public reader search results.',
            ],
            'risk_reasons': ['Well-specified behavior; primary check is visibility filtering across reader vs librarian endpoints.'],
            'priority_reasons': ['Medium catalog maintenance priority matching stakeholder input.'],
            'improved_requirement': case['description'],
            'suggested_requirement_type': 'Functional',
            'type_explanation': 'Clearly defines actor, state change, and read-visibility behavior.',
            'risk_level': 'Low',
            'suggested_priority': 'Medium',
            'test_scenarios': [
                {
                    'category': 'Positive',
                    'title': 'Librarian archives active book record and retains staff visibility',
                    'preconditions': ['Authenticated librarian and active book record exist.'],
                    'test_steps': ['Archive the book record as librarian.', 'Query librarian catalogue view.'],
                    'expected_result': 'Archived book appears in librarian catalogue view with archived status.',
                    'criterion_codes': ['AC-001', 'AC-002'],
                },
                {
                    'category': 'Negative',
                    'title': 'Public reader search excludes archived book record',
                    'preconditions': ['Book record has been archived by a librarian.'],
                    'test_steps': ['Search the public reader catalogue by archived book title.'],
                    'expected_result': 'Archived book is omitted from public reader search results.',
                    'criterion_codes': ['AC-002'],
                },
            ],
        }

    # REQ-EVAL-12: well_formed RBAC authorization
    return {
        'ambiguity_issues': [],
        'conflict_issues': [],
        'missing_information': [],
        'clarification_questions': [],
        'testability_issues': [],
        'assumptions': [],
        'edge_cases': ['SQA Engineer with revoked project access attempts export download.'],
        'acceptance_criteria': [
            'Authenticated SQA Engineers with active project access download PDF and CSV requirement exports successfully.',
            'Authenticated Analysts receive HTTP 403 and unauthenticated guests receive HTTP 401 when requesting exports.',
        ],
        'risk_reasons': ['Authorization boundary requirement is well-formed and security-critical.'],
        'priority_reasons': ['High security priority ensuring export RBAC controls cannot be bypassed.'],
        'improved_requirement': case['description'],
        'suggested_requirement_type': 'Non-Functional',
        'type_explanation': 'Access-control requirement governing role-based export authorization.',
        'risk_level': 'Low',
        'suggested_priority': 'High',
        'test_scenarios': [
            {
                'category': 'Positive',
                'title': 'SQA Engineer with active project access downloads PDF and CSV exports',
                'preconditions': ['Authenticated SQA Engineer with active project access.'],
                'test_steps': ['Request requirement PDF and CSV export endpoints.'],
                'expected_result': 'Both export endpoints return valid downloadable documents.',
                'criterion_codes': ['AC-001'],
            },
            {
                'category': 'Negative',
                'title': 'Analyst (HTTP 403) and unauthenticated guest (HTTP 401) are denied export downloads',
                'preconditions': ['Authenticated Analyst session and unauthenticated guest client.'],
                'test_steps': ['Request export endpoints as Analyst.', 'Request export endpoints without cookies.'],
                'expected_result': 'Analyst receives HTTP 403 and guest receives HTTP 401.',
                'criterion_codes': ['AC-002'],
            },
        ],
    }


def _run_schema_negative_probes():
    from analyzers.llm_analyzer import _validate_analysis
    baseline = _build_fixture_payload({
        'id': 'REQ-EVAL-11',
        'category': 'well_formed',
        'title': 'Baseline',
        'description': 'A librarian can archive an active book catalog record.',
        'requirement_type': 'Functional',
        'priority': 'Medium',
        'project_context': '',
    })
    probes = [
        ('non_dict_payload', ['not-a-dict']),
        ('invalid_risk_level_enum', {**baseline, 'risk_level': 'Extreme'}),
        ('empty_test_scenarios', {**baseline, 'test_scenarios': []}),
        ('missing_info_without_clarification_questions', {**baseline, 'missing_information': ['Unspecified latency.'], 'clarification_questions': []}),
        ('dangling_criterion_code_ac999', {
            **baseline,
            'test_scenarios': [{**baseline['test_scenarios'][0], 'criterion_codes': ['AC-999']}],
        }),
    ]
    results = []
    for name, candidate in probes:
        rejected = _validate_analysis(candidate) is None
        results.append({'probe': name, 'rejected': rejected})
    return {
        'total_probes': len(results),
        'rejected_count': sum(1 for item in results if item['rejected']),
        'all_rejected': all(item['rejected'] for item in results),
        'details': results,
    }


def _collect_introduced_values(result):
    values = []
    unconfirmed_flags = []
    labeled = result.get('labeled_analysis') or {}
    improved = labeled.get('improved_requirement')
    if isinstance(improved, dict):
        values.extend(improved.get('introduced_values') or [])
        unconfirmed_flags.append(bool(improved.get('needs_confirmation')))
    for field_items in labeled.values():
        if isinstance(field_items, list):
            for entry in field_items:
                if isinstance(entry, dict):
                    values.extend(entry.get('introduced_values') or [])
                    unconfirmed_flags.append(bool(entry.get('needs_confirmation')))
    for scenario in result.get('test_scenarios') or []:
        if isinstance(scenario, dict):
            values.extend(scenario.get('introduced_values') or [])
            unconfirmed_flags.append(bool(scenario.get('needs_confirmation')))
    distinct = list(dict.fromkeys(values))
    return values, distinct, (all(unconfirmed_flags) if unconfirmed_flags else False)


def _evaluate_ai_benchmark(cases, mode):
    from analyzers.ai_analyzer import analyze_ai
    from analyzers.llm_analyzer import _validate_analysis, generation_configuration

    fixture_map = {case['id']: _build_fixture_payload(case) for case in cases}
    per_case = []
    raw_results = {}
    halted_reason = None

    for case in cases:
        cid = case['id']
        if halted_reason is not None:
            per_case.append({
                'id': cid,
                'category': case['category'],
                'title': case['title'],
                'requirement_type': case['requirement_type'],
                'status': 'failed',
                'code': halted_reason,
                'schema_valid': False,
                'elapsed_ms': None,
                'criteria_count': 0,
                'scenarios_count': 0,
                'introduced_values_count': 0,
                'distinct_introduced_values': [],
                'all_items_marked_unconfirmed': False,
            })
            continue

        started = perf_counter()
        if mode == 'fixture':
            raw_fixture = fixture_map[cid]
            prevalidated = _validate_analysis(raw_fixture)
            schema_valid = prevalidated is not None
            with patch(
                'analyzers.ai_analyzer.analyze_with_llm',
                return_value={'status': 'success' if schema_valid else 'malformed_json', 'analysis': prevalidated},
            ):
                analyzed = analyze_ai(
                    case['title'],
                    case['description'],
                    case['requirement_type'],
                    case['priority'],
                    project_context=case.get('project_context', ''),
                )
        else:
            analyzed = analyze_ai(
                case['title'],
                case['description'],
                case['requirement_type'],
                case['priority'],
                project_context=case.get('project_context', ''),
            )
            schema_valid = analyzed.get('status') == 'completed'
        elapsed_ms = round((perf_counter() - started) * 1000, 2)

        raw_results[cid] = analyzed
        status = analyzed.get('status', 'failed')
        code = analyzed.get('code') or ('completed' if status == 'completed' else 'api_error')
        values, distinct_values, all_unconfirmed = _collect_introduced_values(analyzed) if status == 'completed' else ([], [], False)
        per_case.append({
            'id': cid,
            'category': case['category'],
            'title': case['title'],
            'requirement_type': case['requirement_type'],
            'status': status,
            'code': code,
            'schema_valid': bool(schema_valid and status == 'completed'),
            'elapsed_ms': elapsed_ms,
            'criteria_count': len(analyzed.get('acceptance_criteria') or []),
            'scenarios_count': len(analyzed.get('test_scenarios') or []),
            'introduced_values_count': len(values),
            'distinct_introduced_values': distinct_values,
            'all_items_marked_unconfirmed': all_unconfirmed,
        })
        if mode == 'live' and code in ('missing_api_key', 'missing_model', 'authentication_error', 'quota_exceeded', 'model_unavailable'):
            halted_reason = code

    total = len(per_case)
    valid = sum(1 for row in per_case if row['schema_valid'])
    by_category = {}
    for row in per_case:
        bucket = by_category.setdefault(row['category'], {'total': 0, 'schema_valid': 0})
        bucket['total'] += 1
        if row['schema_valid']:
            bucket['schema_valid'] += 1

    well_formed_and_boundary_catches = sum(
        row['introduced_values_count']
        for row in per_case
        if row['category'] in ('well_formed', 'boundary_heavy')
    )
    all_distinct = list(dict.fromkeys(v for row in per_case for v in row['distinct_introduced_values']))
    completed_rows = [row for row in per_case if row['status'] == 'completed']

    return {
        'generation_config': {k: v for k, v in generation_configuration().items() if k in ('provider', 'model', 'analysis_version', 'temperature', 'max_output_tokens')},
        'cases': per_case,
        'raw_results': raw_results,
        'schema_validity': {
            'valid_cases': valid,
            'total_cases': total,
            'pass_rate_percent': round((valid / total) * 100, 1) if total else 0.0,
            'by_category': by_category,
            'negative_guard_probes': _run_schema_negative_probes(),
        },
        'value_safety': {
            'total_introduced_value_catches': sum(row['introduced_values_count'] for row in per_case),
            'cases_with_introduced_values': sum(1 for row in per_case if row['introduced_values_count'] > 0),
            'distinct_introduced_values': all_distinct,
            'false_positives_on_well_formed_and_boundary': well_formed_and_boundary_catches,
            'all_completed_outputs_require_confirmation': bool(completed_rows) and all(row['all_items_marked_unconfirmed'] for row in completed_rows),
        },
        'ai_latency_ms': _timing_summary([row['elapsed_ms'] for row in per_case if row['elapsed_ms'] is not None]),
    }


def _login_https(client, email, password=EVAL_PASSWORD):
    response = client.post('/api/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, f'Login failed for {email}: {response.status_code}'
    return response.json['csrf_token']


def _run_workflow_rbac_and_exports(cases, raw_results, mode, export_samples):
    from flask.testing import FlaskClient
    from werkzeug.security import generate_password_hash
    import app as application
    from services import database_service as db_service

    class _HttpsClient(FlaskClient):
        def open(self, *args, **kwargs):
            kwargs.setdefault('base_url', 'https://localhost')
            return super().open(*args, **kwargs)

    prev_db_url = application.DATABASE_URL
    prev_db_path = application.DATABASE
    prev_pg_url = application._POSTGRES_SCHEMA_URL
    prev_test_client = application.app.test_client_class
    prev_ready = set(db_service._SQLITE_READY)
    prev_config = {
        k: application.app.config.get(k)
        for k in ('TESTING', 'SECRET_KEY', 'JWT_SECRET_KEY', 'SESSION_COOKIE_SECURE', 'LOCAL_HTTP_DEVELOPMENT')
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        eval_db = Path(tmpdir) / 'evaluation.db'
        try:
            application.DATABASE_URL = None
            application.DATABASE = eval_db
            application._POSTGRES_SCHEMA_URL = None
            application.app.config.update(
                TESTING=True,
                SECRET_KEY='evaluation-only-flask-secret-key-32-bytes',
                JWT_SECRET_KEY='evaluation-only-jwt-secret-key-32-bytes-long',
                SESSION_COOKIE_SECURE=True,
                LOCAL_HTTP_DEVELOPMENT=False,
            )
            application.app.test_client_class = _HttpsClient

            pw_hash = generate_password_hash(EVAL_PASSWORD, method='scrypt')
            conn = application.get_connection()
            try:
                with conn:
                    for name, role in [
                        ('Eval Admin', 'admin'),
                        ('Eval Analyst', 'Analyst'),
                        ('Eval SQA Reviewer', 'SQA Engineer'),
                    ]:
                        email = name.lower().replace(' ', '.') + '@example.com'
                        conn.execute(
                            'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
                            (name, email, pw_hash, role),
                        )
            finally:
                conn.close()

            guest = application.app.test_client()
            admin = application.app.test_client()
            analyst = application.app.test_client()
            engineer = application.app.test_client()

            admin_csrf = _login_https(admin, 'eval.admin@example.com')
            analyst_csrf = _login_https(analyst, 'eval.analyst@example.com')
            engineer_csrf = _login_https(engineer, 'eval.sqa.reviewer@example.com')

            saved_ids = []
            for case in cases:
                cid = case['id']
                raw = raw_results.get(cid) or {}
                payload = {
                    'title': case['title'],
                    'description': case['description'],
                    'requirement_type': case['requirement_type'],
                    'priority': case['priority'],
                }
                if raw.get('status') == 'completed':
                    with patch('analyzers.ai_analyzer.analyze_with_llm', return_value={'status': 'success', 'analysis': {
                        field: raw[field] for field in (
                            'ambiguity_issues', 'conflict_issues', 'missing_information',
                            'clarification_questions', 'testability_issues', 'assumptions',
                            'edge_cases', 'acceptance_criteria', 'risk_reasons', 'priority_reasons',
                            'improved_requirement', 'suggested_requirement_type', 'type_explanation',
                            'risk_level', 'suggested_priority', 'test_scenarios',
                        )
                    }}):
                        analyzed = analyst.post(
                            '/api/analyze-requirement',
                            json=payload,
                            headers={'X-CSRF-Token': analyst_csrf},
                        )
                        assert analyzed.status_code == 200, analyzed.json
                        payload['analysis'] = analyzed.json
                created = analyst.post(
                    '/api/requirements',
                    json=payload,
                    headers={'X-CSRF-Token': analyst_csrf},
                )
                assert created.status_code == 201, created.json
                saved_ids.append(created.json['requirement']['id'])

            # Ensure target requirement for RBAC/export has acceptance criteria & an SQA test case
            target_id = next((saved_ids[i] for i, c in enumerate(cases) if c['id'] == 'REQ-EVAL-11'), saved_ids[-1])
            target_req = analyst.get(f'/api/requirements/{target_id}').json['requirement']
            if not target_req.get('acceptance_criteria'):
                patched = analyst.patch(
                    f'/api/requirements/{target_id}',
                    json={
                        'title': target_req['title'],
                        'description': target_req['description'],
                        'requirement_type': target_req['requirement_type'],
                        'priority': target_req['user_priority'],
                        'revision': target_req['revision'],
                        'acceptance_criteria': ['Archived records are hidden from public search.'],
                    },
                    headers={'X-CSRF-Token': analyst_csrf},
                )
                assert patched.status_code == 200, patched.json
                target_req = patched.json['requirement']

            cases_resp = engineer.get(f'/api/requirements/{target_id}/test-cases').json['test_cases']
            if not cases_resp:
                created_case = engineer.post(
                    f'/api/requirements/{target_id}/test-cases',
                    json={
                        'title': 'Verify archived catalogue visibility',
                        'category': 'Negative',
                        'preconditions': ['Book record is archived.'],
                        'test_data': 'Public reader query',
                        'test_steps': ['Search public reader index.'],
                        'expected_result': 'Archived book is excluded.',
                        'test_type': 'Functional',
                        'priority': 'Medium',
                        'criterion_codes': [target_req['acceptance_criteria'][0]['criterion_code']],
                        'clarification_notes': '',
                        'revision': target_req['revision'],
                    },
                    headers={'X-CSRF-Token': engineer_csrf},
                )
                assert created_case.status_code == 201, created_case.json
                target_req = created_case.json['requirement']
                cases_resp = engineer.get(f'/api/requirements/{target_id}/test-cases').json['test_cases']
            target_case = cases_resp[0]

            # Analyst submits requirement for SQA review before RBAC approval matrix runs
            submitted = analyst.post(
                f'/api/requirements/{target_id}/submit',
                json={'revision': target_req['revision']},
                headers={'X-CSRF-Token': analyst_csrf},
            )
            assert submitted.status_code == 200, submitted.json
            target_req = submitted.json['requirement']

            # Open an Analyst coverage AI review discussion to verify accept is blocked (403)
            analyst_conv = analyst.post(
                f'/api/requirements/{target_id}/ai-review',
                json={'case_ids': []},
                headers={'X-CSRF-Token': analyst_csrf},
            )
            assert analyst_conv.status_code == 200, analyst_conv.json
            analyst_cid = analyst_conv.json['id']
            with patch('analyzers.review_assistant.generate_review', return_value={
                'kind': 'discussion',
                'message': 'Coverage summary generated for discussion.',
                'changes': [],
            }):
                analyst_turn = analyst.post(
                    f'/api/requirements/{target_id}/ai-review/{analyst_cid}/messages',
                    json={'feedback': 'Summarize current criterion coverage.', 'request_key': 'eval-rbac-check-1'},
                    headers={'X-CSRF-Token': analyst_csrf},
                )
                assert analyst_turn.status_code == 200, analyst_turn.json
                analyst_tid = analyst_turn.json['turn']['id']

            rbac_checks = []

            def record_check(name, actor, expected_status, response):
                rbac_checks.append({
                    'check': name,
                    'actor': actor,
                    'expected_status': expected_status,
                    'actual_status': response.status_code,
                    'passed': response.status_code == expected_status,
                })

            record_check('guest_blocked_requirements_list', 'Unauthenticated Guest', 401, guest.get('/api/requirements'))
            record_check('guest_blocked_project_pdf_export', 'Unauthenticated Guest', 401, guest.get('/api/reports/project.pdf'))
            record_check(
                'analyst_cannot_self_approve_requirement_review',
                'Analyst (Requirement Author)',
                403,
                analyst.patch(
                    f'/api/requirements/{target_id}/review',
                    json={'revision': target_req['revision'], 'review_status': 'Approved', 'reviewer_notes': 'Self approval attempt'},
                    headers={'X-CSRF-Token': analyst_csrf},
                ),
            )
            record_check(
                'analyst_cannot_self_approve_via_review_status',
                'Analyst (Requirement Author)',
                403,
                analyst.patch(
                    f'/api/requirements/{target_id}/review-status',
                    json={'revision': target_req['revision'], 'review_status': 'Approved'},
                    headers={'X-CSRF-Token': analyst_csrf},
                ),
            )
            record_check(
                'analyst_cannot_create_sqa_test_case',
                'Analyst',
                403,
                analyst.post(
                    f'/api/requirements/{target_id}/test-cases',
                    json={'title': 'Unauthorized', 'category': 'Positive', 'preconditions': [], 'test_steps': ['Step'], 'expected_result': 'OK', 'revision': target_req['revision']},
                    headers={'X-CSRF-Token': analyst_csrf},
                ),
            )
            record_check(
                'analyst_cannot_self_approve_test_case',
                'Analyst',
                403,
                analyst.patch(
                    f'/api/requirements/{target_id}/test-cases/{target_case["id"]}/review',
                    json={'revision': target_req['revision'], 'case_revision': target_case['case_revision'], 'review_status': 'Approved'},
                    headers={'X-CSRF-Token': analyst_csrf},
                ),
            )
            record_check(
                'analyst_cannot_accept_ai_review_revision_proposal',
                'Analyst',
                403,
                analyst.post(
                    f'/api/requirements/{target_id}/ai-review/{analyst_cid}/proposals/{analyst_tid}',
                    json={'action': 'accept'},
                    headers={'X-CSRF-Token': analyst_csrf},
                ),
            )
            record_check(
                'sqa_engineer_cannot_create_requirements',
                'SQA Engineer',
                403,
                engineer.post(
                    '/api/requirements',
                    json={'title': 'Blocked SQA draft', 'description': 'SQA cannot author requirements.', 'requirement_type': 'Functional', 'priority': 'Medium'},
                    headers={'X-CSRF-Token': engineer_csrf},
                ),
            )
            record_check(
                'sqa_engineer_cannot_invoke_analyst_ai_endpoint',
                'SQA Engineer',
                403,
                engineer.post(
                    '/api/analyze-requirement',
                    json={'title': 'Blocked', 'description': 'SQA cannot run Analyst endpoint.', 'requirement_type': 'Functional', 'priority': 'Medium'},
                    headers={'X-CSRF-Token': engineer_csrf},
                ),
            )
            record_check(
                'admin_cannot_approve_sqa_decisions',
                'Admin',
                403,
                admin.patch(
                    f'/api/requirements/{target_id}/review',
                    json={'revision': target_req['revision'], 'review_status': 'Approved'},
                    headers={'X-CSRF-Token': admin_csrf},
                ),
            )
            record_check(
                'missing_csrf_token_rejected_on_write',
                'Analyst (No CSRF)',
                403,
                analyst.post('/api/requirements', json={'title': 'No CSRF', 'description': 'Missing header.', 'requirement_type': 'Functional', 'priority': 'Medium'}),
            )

            # Positive control: independent SQA Engineer approves test case and requirement
            for status in ('In Review', 'Approved'):
                case_rev_resp = engineer.patch(
                    f'/api/requirements/{target_id}/test-cases/{target_case["id"]}/review',
                    json={'revision': target_req['revision'], 'case_revision': target_case['case_revision'], 'review_status': status, 'review_notes': 'Verified in evaluation.'},
                    headers={'X-CSRF-Token': engineer_csrf},
                )
                assert case_rev_resp.status_code == 200, case_rev_resp.json
                target_req = case_rev_resp.json['requirement']
                target_case = next(c for c in engineer.get(f'/api/requirements/{target_id}/test-cases').json['test_cases'] if c['id'] == target_case['id'])

            for status in ('In Review', 'Approved'):
                req_rev_resp = engineer.patch(
                    f'/api/requirements/{target_id}/review',
                    json={'revision': target_req['revision'], 'review_status': status, 'reviewer_notes': 'Independent SQA approval in evaluation.'},
                    headers={'X-CSRF-Token': engineer_csrf},
                )
                assert req_rev_resp.status_code == 200, req_rev_resp.json
                target_req = req_rev_resp.json['requirement']
            record_check('independent_sqa_engineer_can_approve_requirement', 'SQA Engineer (Non-Author)', 200, req_rev_resp)

            # Author role promotion cannot bypass author self-review separation
            promoted = admin.patch(
                '/api/admin/users/2',
                json={'role': 'SQA Engineer'},
                headers={'X-CSRF-Token': admin_csrf},
            )
            assert promoted.status_code == 200, promoted.json
            reauth_csrf = _login_https(analyst, 'eval.analyst@example.com')
            record_check(
                'role_promoted_author_still_blocked_from_self_approval',
                'Author Promoted to SQA Engineer',
                403,
                analyst.patch(
                    f'/api/requirements/{target_id}/review',
                    json={'revision': target_req['revision'], 'review_status': 'Needs Revision'},
                    headers={'X-CSRF-Token': reauth_csrf},
                ),
            )

            # Stage 2: Export stage timings (requirement PDF, project PDF, CSV register)
            exports = {}
            export_targets = [
                ('requirement_pdf', f'/api/requirements/{target_id}/report.pdf', 'pdf'),
                ('project_pdf', '/api/reports/project.pdf', 'pdf'),
                ('requirements_csv', '/api/exports/requirements.csv', 'csv'),
            ]
            for format_key, url, kind in export_targets:
                samples = []
                for idx in range(1, export_samples + 1):
                    started = perf_counter()
                    response = engineer.get(url)
                    elapsed_ms = round((perf_counter() - started) * 1000, 2)
                    assert response.status_code == 200, f'Export failed on {url}: {response.status_code}'
                    if kind == 'pdf':
                        assert response.data.startswith(b'%PDF-')
                        assert b'%%EOF' in response.data[-128:]
                    else:
                        csv_rows = list(csv.DictReader(StringIO(response.data.decode('utf-8-sig'))))
                        assert len(csv_rows) == len(cases)
                    timings = _parse_server_timing(response.headers.get('Server-Timing', ''))
                    samples.append({
                        'sample': idx,
                        'elapsed_ms': elapsed_ms,
                        'bytes': len(response.data),
                        'report_data_ms': timings.get('report_data'),
                        'report_render_ms': timings.get('report_render'),
                        'report_response_ms': timings.get('report_response'),
                        'db_connect_ms': timings.get('db_connect'),
                        'db_execute_ms': timings.get('db_execute'),
                        'server_request_ms': timings.get('request'),
                    })
                exports[format_key] = {
                    'bytes': samples[-1]['bytes'],
                    'total_elapsed_ms': _timing_summary([s['elapsed_ms'] for s in samples]),
                    'stages_ms': {
                        stage: _timing_summary([s[f'{stage}_ms'] for s in samples])
                        for stage in ('report_data', 'report_render', 'report_response', 'server_request')
                    },
                    'samples': samples,
                }

            return {
                'rbac_verification': {
                    'total_checks': len(rbac_checks),
                    'passed_checks': sum(1 for item in rbac_checks if item['passed']),
                    'all_passed': all(item['passed'] for item in rbac_checks),
                    'checks': rbac_checks,
                },
                'export_timings': exports,
            }
        finally:
            application.DATABASE_URL = prev_db_url
            application.DATABASE = prev_db_path
            application._POSTGRES_SCHEMA_URL = prev_pg_url
            application.app.test_client_class = prev_test_client
            application.app.config.update(prev_config)
            db_service._SQLITE_READY.clear()
            db_service._SQLITE_READY.update(prev_ready)


def _render_markdown(results):
    schema = results['schema_validity']
    vs = results['value_safety']
    ai_lat = results['ai_latency_ms']
    rbac = results['rbac_verification']
    exports = results['export_timings']
    mode_label = (
        '`--mode fixture` (deterministic offline Gemini payloads + real Flask/SQLite workflow, RBAC, value_safety, and ReportLab/CSV pipelines)'
        if results['mode'] == 'fixture' else
        '`--mode live` (live Google Gemini API calls + real Flask/SQLite workflow, RBAC, value_safety, and ReportLab/CSV pipelines)'
    )

    lines = [
        '# ReqQuality AI — WBS 3.5.4 Controlled Evaluation Report',
        '',
        f'- **Generated (UTC)**: `{results["generated_at_utc"]}`',
        f'- **Evaluation Mode**: {mode_label}',
        f'- **Benchmark Dataset**: [`fyp_benchmark_cases.json`](../../backend/evaluation/fyp_benchmark_cases.json) (`{results["dataset_size"]}` requirements across `5` categories)',
        f'- **Model Configuration**: provider=`{results["generation_config"].get("provider")}`, model=`{results["generation_config"].get("model") or "<unset>"}`, temperature=`{results["generation_config"].get("temperature")}`',
        '',
        '> [!NOTE]',
        '> Per our FYP proposal governance rules, `--mode fixture` validates schema enforcement, `value_safety.py` introduced-value detection, RBAC separation of duties, and export pipeline timings deterministically offline. Live semantic accuracy claims require running `--mode live` with `GEMINI_API_KEY` alongside human rubric review and the SUS user study (`USER_STUDY_PROTOCOL.md`).',
        '',
        '## 1. Executive Summary',
        '',
        '| Metric | Measured Result |',
        '| --- | --- |',
        f'| Schema Validity Pass Rate (12 Cases) | **{schema["pass_rate_percent"]}%** ({schema["valid_cases"]}/{schema["total_cases"]}) |',
        f'| Negative Schema Guard Probes Rejected | **{schema["negative_guard_probes"]["rejected_count"]}/{schema["negative_guard_probes"]["total_probes"]}** |',
        f'| `value_safety.py` Introduced-Value Catches | **{vs["total_introduced_value_catches"]}** across **{vs["cases_with_introduced_values"]}** cases ({vs["false_positives_on_well_formed_and_boundary"]} false positives on boundary/well-formed) |',
        f'| Unconfirmed Flag Coverage (`needs_confirmation=True`) | **{"100% Enforced" if vs["all_completed_outputs_require_confirmation"] else "Incomplete / No Completed AI Cases"}** |',
        f'| AI Analysis Pipeline Latency (Mean / p95) | **{ai_lat["mean_ms"]} ms** / **{ai_lat["p95_ms"]} ms** (`n={ai_lat["count"]}`) |',
        f'| Requirement PDF Export Mean / p95 ({results["export_samples"]} samples) | **{exports["requirement_pdf"]["total_elapsed_ms"]["mean_ms"]} ms** / **{exports["requirement_pdf"]["total_elapsed_ms"]["p95_ms"]} ms** ({exports["requirement_pdf"]["bytes"]} bytes) |',
        f'| Project Summary PDF Mean / p95 ({results["export_samples"]} samples) | **{exports["project_pdf"]["total_elapsed_ms"]["mean_ms"]} ms** / **{exports["project_pdf"]["total_elapsed_ms"]["p95_ms"]} ms** ({exports["project_pdf"]["bytes"]} bytes) |',
        f'| Requirements CSV Export Mean / p95 ({results["export_samples"]} samples) | **{exports["requirements_csv"]["total_elapsed_ms"]["mean_ms"]} ms** / **{exports["requirements_csv"]["total_elapsed_ms"]["p95_ms"]} ms** ({exports["requirements_csv"]["bytes"]} bytes) |',
        f'| RBAC Permission Enforcement Checks | **{rbac["passed_checks"]}/{rbac["total_checks"]} passed** (Analyst self-approval blocked: **HTTP 403**) |',
        '',
        '## 2. Benchmark Dataset & Per-Requirement Results',
        '',
        '| ID | Category | Type | Status | Schema Valid | Criteria | Scenarios | `value_safety` Catches | Latency (ms) |',
        '| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |',
    ]

    for row in results['cases']:
        catches = ', '.join(row['distinct_introduced_values']) if row['distinct_introduced_values'] else 'None'
        lines.append(
            f'| `{row["id"]}` | `{row["category"]}` | {row["requirement_type"]} | `{row["code"]}` | '
            f'{"Pass" if row["schema_valid"] else "Fail"} | {row["criteria_count"]} | {row["scenarios_count"]} | '
            f'{row["introduced_values_count"]} ({catches}) | {row["elapsed_ms"] if row["elapsed_ms"] is not None else "n/a"} |'
        )

    lines.extend([
        '',
        '### Category Coverage Summary',
        '',
        '| Category | Cases | Schema Valid |',
        '| --- | ---: | ---: |',
    ])
    for cat, counts in schema['by_category'].items():
        lines.append(f'| `{cat}` | {counts["total"]} | {counts["schema_valid"]}/{counts["total"]} |')

    lines.extend([
        '',
        '### Negative Schema-Guard Probes (`analyzers/llm_analyzer.py`)',
        '',
        '| Probe | Malformed Output Condition | Rejected (`None`) |',
        '| --- | --- | --- |',
    ])
    probe_descriptions = {
        'non_dict_payload': 'Top-level JSON is a list rather than an object',
        'invalid_risk_level_enum': 'Unsupported `risk_level` value outside allowed enum',
        'empty_test_scenarios': 'Empty `test_scenarios` list with zero scenarios',
        'missing_info_without_clarification_questions': 'Non-empty `missing_information` paired with empty `clarification_questions`',
        'dangling_criterion_code_ac999': 'Scenario references non-existent `AC-999` code',
    }
    for probe in schema['negative_guard_probes']['details']:
        lines.append(f'| `{probe["probe"]}` | {probe_descriptions.get(probe["probe"], "")} | {"Yes" if probe["rejected"] else "No"} |')

    lines.extend([
        '',
        '## 3. `value_safety.py` Introduced-Value & Hallucination Audit',
        '',
        f'- **Total Introduced-Value Matches Flagged**: `{vs["total_introduced_value_catches"]}` across `{vs["cases_with_introduced_values"]}` requirements',
        f'- **Distinct Values Flagged**: `{", ".join(vs["distinct_introduced_values"]) or "None"}`',
        f'- **False Positives on Boundary-Heavy / Well-Formed Cases**: `{vs["false_positives_on_well_formed_and_boundary"]}`',
        '',
        '## 4. Export Pipeline Stage Timings (`Server-Timing`)',
        '',
        '| Export Format | Bytes | Total Mean / p95 (ms) | `report_data` Mean / p95 (ms) | `report_render` Mean / p95 (ms) | `report_response` Mean / p95 (ms) |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
    ])
    for format_key, stats in exports.items():
        total = stats['total_elapsed_ms']
        stages = stats['stages_ms']
        lines.append(
            f'| `{format_key}` | {stats["bytes"]} | '
            f'{total["mean_ms"]} / {total["p95_ms"]} | '
            f'{stages["report_data"]["mean_ms"]} / {stages["report_data"]["p95_ms"]} | '
            f'{stages["report_render"]["mean_ms"]} / {stages["report_render"]["p95_ms"]} | '
            f'{stages["report_response"]["mean_ms"]} / {stages["report_response"]["p95_ms"]} |'
        )

    lines.extend([
        '',
        '## 5. Automated RBAC Permission Enforcement Matrix',
        '',
        '| Verification Check | Actor | Expected HTTP | Actual HTTP | Result |',
        '| --- | --- | ---: | ---: | --- |',
    ])
    for check in rbac['checks']:
        lines.append(
            f'| `{check["check"]}` | {check["actor"]} | {check["expected_status"]} | {check["actual_status"]} | '
            f'{"PASS" if check["passed"] else "FAIL"} |'
        )

    lines.extend([
        '',
        '## 6. Reproducibility Commands',
        '',
        '```powershell',
        '# Offline deterministic CI/local verification (no API quota used)',
        '.\\backend\\.venv\\Scripts\\python.exe backend/evaluation/run_fyp_evaluation.py --mode fixture',
        '',
        '# Live Google Gemini empirical run (requires GEMINI_API_KEY and GEMINI_MODEL in environment or backend/.env)',
        '.\\backend\\.venv\\Scripts\\python.exe backend/evaluation/run_fyp_evaluation.py --mode live',
        '```',
        '',
    ])
    return '\n'.join(lines)


def run_evaluation(
    mode='fixture',
    dataset_path=DEFAULT_DATASET,
    json_output=DEFAULT_JSON_OUTPUT,
    report_output=DEFAULT_REPORT_OUTPUT,
    export_samples=3,
):
    dataset_file = Path(dataset_path)
    cases = json.loads(dataset_file.read_text(encoding='utf-8'))
    samples_count = max(1, int(export_samples))

    previous_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        ai_benchmark = _evaluate_ai_benchmark(cases, mode=mode)
        raw_results = ai_benchmark.pop('raw_results')
        workflow = _run_workflow_rbac_and_exports(cases, raw_results, mode=mode, export_samples=samples_count)
    finally:
        logging.disable(previous_level)

    results = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'mode': mode,
        'dataset_path': str(dataset_file.name),
        'dataset_size': len(cases),
        'export_samples': samples_count,
        **ai_benchmark,
        **workflow,
    }

    if json_output:
        json_path = Path(json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    if report_output:
        report_path = Path(report_output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_markdown(results), encoding='utf-8')

    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('fixture', 'live'), default='fixture')
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--json-output', type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument('--report-output', type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument('--export-samples', type=int, default=3)
    args = parser.parse_args()

    results = run_evaluation(
        mode=args.mode,
        dataset_path=args.dataset,
        json_output=args.json_output,
        report_output=args.report_output,
        export_samples=args.export_samples,
    )
    print(json.dumps({
        'mode': results['mode'],
        'dataset_size': results['dataset_size'],
        'schema_validity_percent': results['schema_validity']['pass_rate_percent'],
        'value_safety_catches': results['value_safety']['total_introduced_value_catches'],
        'ai_mean_ms': results['ai_latency_ms']['mean_ms'],
        'ai_p95_ms': results['ai_latency_ms']['p95_ms'],
        'rbac_all_passed': results['rbac_verification']['all_passed'],
        'json_output': str(args.json_output),
        'report_output': str(args.report_output),
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
