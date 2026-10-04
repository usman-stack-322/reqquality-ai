"""Deterministic quality-risk scoring for analyzed requirements."""

ISSUE_LIMIT = 4
EDGE_CASE_LIMIT = 5

REQUIREMENT_TYPE_RISK = {
    "Functional": 40,
    "Non-Functional": 80,
    "Business": 60,
}
PRIORITY_RISK = {"Low": 0, "Medium": 50, "High": 100}


def _list_count(analysis, field):
    values = analysis.get(field, [])
    return len(values) if isinstance(values, list) else 0


def _count_score(count, limit):
    return min(count, limit) / limit * 100


def analyze_risk(analysis, requirement_type, priority):
    """Return a weighted 0-100 score, its band, and contributing reasons."""
    counts = {
        "ambiguity": _list_count(analysis, "ambiguity_issues"),
        "missing information": _list_count(analysis, "missing_information"),
        "testability": _list_count(analysis, "testability_issues"),
        "edge case": _list_count(analysis, "edge_cases"),
    }
    factor_scores = {
        "ambiguity": _count_score(counts["ambiguity"], ISSUE_LIMIT),
        "missing_information": _count_score(counts["missing information"], ISSUE_LIMIT),
        "testability": _count_score(counts["testability"], ISSUE_LIMIT),
        "edge_cases": _count_score(counts["edge case"], EDGE_CASE_LIMIT),
        "requirement_type": REQUIREMENT_TYPE_RISK.get(requirement_type, 50),
        "user_priority": PRIORITY_RISK.get(priority, 50),
    }
    weights = {
        "ambiguity": 0.25,
        "missing_information": 0.25,
        "testability": 0.20,
        "edge_cases": 0.15,
        "requirement_type": 0.10,
        "user_priority": 0.05,
    }
    risk_score = round(sum(factor_scores[factor] * weight for factor, weight in weights.items()))

    if risk_score >= 80:
        risk_level = "Critical"
        suggested_priority = "High"
    elif risk_score >= 60:
        risk_level = "High"
        suggested_priority = "High"
    elif risk_score >= 30:
        risk_level = "Medium"
        suggested_priority = "Medium"
    else:
        risk_level = "Low"
        suggested_priority = "Low"

    risk_reasons = [
        f"{counts['ambiguity']} ambiguity issue(s) contribute to risk.",
        f"{counts['missing information']} missing-information issue(s) contribute to risk.",
        f"{counts['testability']} testability issue(s) contribute to risk.",
        f"{counts['edge case']} edge case(s) were identified.",
        f"{requirement_type} requirements use a type-risk factor of {factor_scores['requirement_type']}/100.",
        f"The selected {priority} priority uses a priority-risk factor of {factor_scores['user_priority']}/100.",
    ]

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "suggested_priority": suggested_priority,
        "risk_reasons": risk_reasons,
    }