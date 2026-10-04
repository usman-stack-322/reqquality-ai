"""Combine deterministic analysis with an optional LLM result."""

from analyzers.llm_analyzer import analyze_with_llm
from analyzers.rule_analyzer import analyze_with_rules
from analyzers.risk_analyzer import analyze_risk
from analyzers.test_scenario_generator import generate_test_scenarios
from analyzers.value_safety import find_introduced_values

LIST_FIELDS = (
    "ambiguity_issues",
    "missing_information",
    "testability_issues",
    "assumptions",
    "edge_cases",
    "acceptance_criteria",
)


def _merge_unique(rule_values, llm_values):
    merged = []
    seen = set()

    rule_values = rule_values if isinstance(rule_values, list) else []
    llm_values = llm_values if isinstance(llm_values, list) else []
    for value in rule_values + llm_values:
        if not isinstance(value, str):
            continue
        cleaned_value = value.strip()
        normalized_value = cleaned_value.casefold()
        if cleaned_value and normalized_value not in seen:
            merged.append(cleaned_value)
            seen.add(normalized_value)

    return merged


def _label_items(values, rule_values, llm_values, original_text, forced_source=None):
    rule_items = {value.strip().casefold() for value in rule_values if isinstance(value, str)}
    llm_items = {value.strip().casefold() for value in llm_values if isinstance(value, str)}
    labeled = []
    for value in values:
        if forced_source:
            source = forced_source
        elif value.strip().casefold() in rule_items:
            source = "rule_based"
        elif value.strip().casefold() in llm_items:
            source = "ai_suggestion"
        else:
            source = "rule_based"
        introduced_values = (
            find_introduced_values(value, original_text)
            if source in {"ai_suggestion", "ai_assumption"}
            else []
        )
        labeled.append({
            "text": value,
            "source": source,
            "needs_confirmation": source == "ai_assumption" or bool(introduced_values),
            "introduced_values": introduced_values,
        })
    return labeled


def analyze_hybrid(title, description, requirement_type, priority):
    rule_result = analyze_with_rules(title, description, requirement_type)
    requirement = {
        "title": title,
        "description": description,
        "requirement_type": requirement_type,
        "priority": priority,
    }

    try:
        llm_response = analyze_with_llm(requirement)
    except Exception:
        llm_response = {"status": "api_error", "analysis": None}

    if not isinstance(llm_response, dict):
        llm_response = {"status": "api_error", "analysis": None}

    llm_status = llm_response.get("status", "api_error")
    llm_result = llm_response.get("analysis")
    if llm_status != "success" or not isinstance(llm_result, dict):
        analysis_mode = "rule_based_only"
        status = "fallback"
        llm_status = llm_status if isinstance(llm_status, str) else "api_error"
        merged_result = dict(rule_result)
    else:
        analysis_mode = "hybrid"
        status = "completed"
        merged_result = dict(rule_result)
        for field in LIST_FIELDS:
            merged_result[field] = _merge_unique(
                rule_result.get(field, []), llm_result.get(field, [])
            )

        llm_improved_requirement = llm_result.get("improved_requirement")
        if isinstance(llm_improved_requirement, str) and llm_improved_requirement.strip():
            merged_result["improved_requirement"] = llm_improved_requirement.strip()

    merged_result.update({
        "analysis_mode": analysis_mode,
        "source": analysis_mode,
        "status": status,
        "llm_status": llm_status,
    })
    original_text = f"{title}\n{description}"
    labeled_analysis = {
        "original_requirement": {
            "title": title,
            "description": description,
            "source": "original",
            "needs_confirmation": False,
            "introduced_values": [],
        },
    }
    for field in LIST_FIELDS:
        labeled_analysis[field] = _label_items(
            merged_result.get(field, []),
            rule_result.get(field, []),
            llm_result.get(field, []) if isinstance(llm_result, dict) else [],
            original_text,
            forced_source="ai_assumption" if field == "assumptions" else None,
        )
    improved_source = "ai_suggestion" if analysis_mode == "hybrid" else "rule_based"
    improved_values = (
        find_introduced_values(merged_result["improved_requirement"], original_text)
        if improved_source == "ai_suggestion"
        else []
    )
    labeled_analysis["improved_requirement"] = {
        "text": merged_result["improved_requirement"],
        "source": improved_source,
        "needs_confirmation": bool(improved_values),
        "introduced_values": improved_values,
    }
    merged_result["labeled_analysis"] = labeled_analysis
    merged_result.update(analyze_risk(merged_result, requirement_type, priority))
    merged_result.update(generate_test_scenarios(requirement, merged_result))
    return merged_result