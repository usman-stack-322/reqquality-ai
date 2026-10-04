"""Generate structured, requirement-linked test scenarios with a fallback."""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from analyzers.value_safety import find_introduced_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

CATEGORIES = ("Positive", "Negative", "Boundary", "Edge-case")
CATEGORY_IDS = {
    "Positive": "POS",
    "Negative": "NEG",
    "Boundary": "BND",
    "Edge-case": "EDGE",
}
SCENARIO_FIELDS = (
    "id",
    "category",
    "title",
    "preconditions",
    "test_steps",
    "expected_result",
    "linked_requirement",
)
SCENARIO_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scenarios": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "category": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "preconditions": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "test_steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "expected_result": {"type": "STRING"},
                    "linked_requirement": {"type": "STRING"},
                },
                "required": list(SCENARIO_FIELDS),
            },
        }
    },
    "required": ["scenarios"],
}


def _strings(values):
    if not isinstance(values, list):
        return []
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _validate_scenarios(value):
    if not isinstance(value, dict) or not isinstance(value.get("scenarios"), list):
        return []

    scenarios = []
    for value in value["scenarios"]:
        if not isinstance(value, dict):
            continue
        category = value.get("category")
        title = value.get("title")
        expected_result = value.get("expected_result")
        preconditions = _strings(value.get("preconditions"))
        test_steps = _strings(value.get("test_steps"))
        if (
            category not in CATEGORIES
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(expected_result, str)
            or not expected_result.strip()
            or not test_steps
        ):
            continue
        scenarios.append({
            "category": category,
            "title": title.strip(),
            "preconditions": preconditions,
            "test_steps": test_steps,
            "expected_result": expected_result.strip(),
        })
    return scenarios


def _identity_text(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _deduplicate(scenarios):
    unique = []
    seen_titles = set()
    seen_bodies = set()
    for scenario in scenarios:
        title_key = _identity_text(scenario["title"])
        body_key = _identity_text(" ".join(
            scenario["preconditions"]
            + scenario["test_steps"]
            + [scenario["expected_result"]]
        ))
        if not title_key or title_key in seen_titles or body_key in seen_bodies:
            continue
        unique.append(scenario)
        seen_titles.add(title_key)
        seen_bodies.add(body_key)
    return unique


def _first(analysis, field, default):
    values = _strings(analysis.get(field))
    return values[0] if values else default


def _fallback_scenarios(requirement, analysis):
    title = requirement["title"].strip()
    description = requirement["description"].strip()
    criteria = _strings(analysis.get("acceptance_criteria"))
    ambiguity = _strings(analysis.get("ambiguity_issues"))
    missing = _strings(analysis.get("missing_information"))
    testability = _strings(analysis.get("testability_issues"))
    edge_cases = _strings(analysis.get("edge_cases"))
    risk_reasons = _strings(analysis.get("risk_reasons"))
    risk_context = (
        f"Risk is {analysis.get('risk_level', 'unknown')} "
        f"({analysis.get('risk_score', 'unscored')}/100)."
    )
    linked_requirement = title

    def scenario(category, scenario_title, steps, expected, context=None):
        preconditions = [
            f"Use only the actor, trigger, and conditions stated in: {description}"
        ]
        if context:
            preconditions.append(context)
        preconditions.append(risk_context)
        if risk_reasons:
            preconditions.append(f"Risk finding: {risk_reasons[0]}")
        return {
            "category": category,
            "title": scenario_title,
            "preconditions": preconditions,
            "test_steps": steps,
            "expected_result": expected,
        }

    primary_criterion = criteria[0] if criteria else _first(
        analysis, "improved_requirement", description
    )
    failure_context = _first(
        analysis,
        "testability_issues",
        _first(analysis, "edge_cases", "an invalid or unsuccessful operation"),
    )
    uncertainty_context = _first(
        analysis,
        "missing_information",
        _first(analysis, "ambiguity_issues", "any unspecified requirement condition"),
    )
    boundary_context = _first(
        analysis,
        "edge_cases",
        "minimum, maximum, and boundary values",
    )

    fallback = [
        scenario(
            "Positive",
            f"Complete the stated {title} behavior",
            [
                "Identify the requested actor, trigger, and outcome in the linked requirement.",
                f"Perform the behavior described by the requirement: {description}",
                f"Verify the stated success condition: {primary_criterion}",
            ],
            "The requirement's stated outcome occurs and its applicable acceptance criteria pass.",
        ),
        scenario(
            "Positive",
            f"Verify acceptance criteria for {title}",
            [f"Check acceptance criterion: {criterion}" for criterion in criteria[:3]]
            or [
                f"Exercise the behavior described by: {description}",
                f"Compare the observed result with: {primary_criterion}",
            ],
            "Each stated acceptance criterion is satisfied without adding unstated behavior.",
        ),
        scenario(
            "Negative",
            f"Exercise an unsuccessful {title} operation",
            [
                f"Use the failure condition identified during analysis: {failure_context}",
                "Trigger the linked requirement's behavior with that invalid or unsuccessful condition.",
                "Observe the system response and check for unintended changes.",
            ],
            "The system follows any specified failure behavior; unspecified behavior is recorded as a requirement gap.",
            failure_context,
        ),
        scenario(
            "Negative",
            f"Check unresolved input or conditions for {title}",
            [
                f"Review the identified uncertainty: {uncertainty_context}",
                "Exercise the linked behavior where that missing detail affects the result.",
                "Record whether the behavior can be verified from the requirement as written.",
            ],
            "The check is verifiable against stated behavior, or the unresolved detail is captured for clarification.",
            uncertainty_context,
        ),
        scenario(
            "Boundary",
            f"Verify stated limits for {title}",
            [
                f"Identify any numeric limits or boundaries stated in: {description}",
                f"Check the requirement at its stated boundary: {boundary_context}",
                "Compare the result with the requirement and acceptance criteria.",
            ],
            "Stated limits are handled as specified; absent limits are recorded as a testability gap rather than guessed.",
            boundary_context,
        ),
        scenario(
            "Boundary",
            f"Check behavior around {title} thresholds",
            [
                "Identify the closest values below, at, and above each limit explicitly stated in the requirement.",
                "Exercise the linked behavior at those values without inventing numeric limits.",
                "Compare accepted and rejected values with the specified boundary rules.",
            ],
            "Values at and around each stated threshold follow its documented boundary rule; missing rules are reported for clarification.",
            _first(analysis, "missing_information", boundary_context),
        ),
        scenario(
            "Edge-case",
            f"Check an identified edge case for {title}",
            [
                f"Set up the linked requirement behavior described by: {description}",
                f"Exercise this analyzed edge case: {_first(analysis, 'edge_cases', boundary_context)}",
                "Observe the result and compare it with the stated requirement behavior.",
            ],
            "The edge case is handled consistently with the requirement; any unspecified outcome is recorded for clarification.",
            _first(analysis, "edge_cases", boundary_context),
        ),
        scenario(
            "Edge-case",
            f"Check an additional risk finding for {title}",
            [
                f"Review this risk or quality finding: {_first(analysis, 'risk_reasons', risk_context)}",
                f"Exercise the linked behavior against this condition: {_first(analysis, 'edge_cases', uncertainty_context)}",
                "Check for inconsistent results, unintended changes, or behavior not covered by the requirement.",
            ],
            "The linked behavior remains consistent with its stated outcomes and any uncovered risk is documented.",
            _first(analysis, "ambiguity_issues", _first(analysis, "edge_cases", uncertainty_context)),
        ),
    ]

    for item in fallback:
        item["linked_requirement"] = linked_requirement
    return fallback


def _generate_with_gemini(requirement, analysis):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not api_key or not model or model == "your_model_name_here":
        return []

    context = {
        "requirement": requirement,
        "acceptance_criteria": analysis.get("acceptance_criteria", []),
        "ambiguity_findings": analysis.get("ambiguity_issues", []),
        "missing_information": analysis.get("missing_information", []),
        "testability_findings": analysis.get("testability_issues", []),
        "edge_cases": analysis.get("edge_cases", []),
        "risk_findings": {
            "risk_score": analysis.get("risk_score"),
            "risk_level": analysis.get("risk_level"),
            "risk_reasons": analysis.get("risk_reasons", []),
        },
    }
    prompt = (
        "Generate at least two distinct software test scenarios in each of these "
        "categories: Positive, Negative, Boundary, and Edge-case. Use only behavior "
        "directly supported by the requirement. Do not invent actors, policies, "
        "limits, or outcomes; turn unresolved details into clarification checks. "
        "Use acceptance criteria, ambiguity, missing information, testability, edge "
        "cases, and risk findings to make scenarios specific. Each scenario must "
        "include a short title, preconditions array, ordered test_steps array, and "
        "expected_result. Return JSON matching the schema.\n"
        f"{json.dumps(context, ensure_ascii=True)}"
    )
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30_000),
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCENARIO_SCHEMA,
                temperature=0.2,
            ),
        )
        return _validate_scenarios(json.loads(response.text or ""))
    except Exception:
        return []


def generate_test_scenarios(requirement, analysis):
    """Return deduplicated Gemini scenarios, filling gaps with deterministic ones."""
    generated = _generate_with_gemini(requirement, analysis)
    fallback = _fallback_scenarios(requirement, analysis)
    for scenario in generated:
        scenario["source"] = "ai_suggestion"
    for scenario in fallback:
        scenario["source"] = "rule_based"
    scenarios = _deduplicate(generated)

    for category in CATEGORIES:
        category_count = sum(item["category"] == category for item in scenarios)
        for item in fallback:
            if category_count >= 2:
                break
            if item["category"] != category:
                continue
            candidate = _deduplicate(scenarios + [item])
            if len(candidate) > len(scenarios):
                scenarios = candidate
                category_count += 1

    counters = {category: 0 for category in CATEGORIES}
    original_text = f"{requirement['title']}\n{requirement['description']}"
    assumptions = _strings(analysis.get("assumptions"))
    for item in scenarios:
        counters[item["category"]] += 1
        item["id"] = f"{CATEGORY_IDS[item['category']]}-{counters[item['category']]:03d}"
        item["linked_requirement"] = requirement["title"].strip()
        scenario_text = " ".join(
            [item["title"], *item["preconditions"], *item["test_steps"], item["expected_result"]]
        )
        introduced_values = find_introduced_values(scenario_text, original_text)
        depends_on_assumptions = item["source"] == "ai_suggestion" and bool(assumptions)
        item["introduced_values"] = introduced_values
        item["assumption_reasons"] = assumptions if depends_on_assumptions else []
        item["needs_confirmation"] = bool(introduced_values or depends_on_assumptions)
    return {
        "test_scenarios": scenarios,
        "test_scenario_source": "gemini" if generated else "fallback",
    }