"""Deterministic requirement checks that do not call external services."""

import re

VAGUE_TERMS = (
    "fast",
    "quickly",
    "easy",
    "user-friendly",
    "appropriate",
    "efficient",
    "soon",
    "etc",
)
OBSERVABLE_ACTIONS = (
    "allow",
    "create",
    "delete",
    "display",
    "download",
    "export",
    "filter",
    "generate",
    "import",
    "notify",
    "process",
    "return",
    "save",
    "search",
    "send",
    "store",
    "update",
    "upload",
    "validate",
    "show",
)


def analyze_with_rules(title, description, requirement_type):
    normalized_description = " ".join(description.split()).rstrip(".")
    description_lower = normalized_description.lower()

    ambiguity_issues = [
        f'The term "{term}" is subjective; replace it with a measurable threshold.'
        for term in VAGUE_TERMS
        if re.search(rf"\b{re.escape(term)}\b", description_lower)
    ]

    missing_information = []
    if not re.search(r"\b(user|administrator|admin|customer|system|service|operator)\b", description_lower):
        missing_information.append("Identify the actor responsible for starting or receiving this behavior.")
    if not re.search(r"\b(when|whenever|upon|after|before|if|once|on)\b", description_lower):
        missing_information.append("Specify the trigger or condition that starts this behavior.")
    if requirement_type == "Non-Functional" and not re.search(r"\d", description_lower):
        missing_information.append("Add a measurable target, such as response time, capacity, or availability.")

    has_observable_action = any(
        re.search(rf"\b{action}\w*\b", description_lower)
        for action in OBSERVABLE_ACTIONS
    )
    testability_issues = []
    if not has_observable_action and not re.search(r"\d", description_lower):
        testability_issues.append("State an observable result or measurable threshold that can be verified in a test.")
    if not re.search(r"\b(error|invalid|failure|fail|unavailable|timeout)\b", description_lower):
        testability_issues.append("Define the expected behavior for invalid input or an unsuccessful operation.")
    if ambiguity_issues:
        testability_issues.append("Replace subjective wording with objective pass/fail conditions.")

    edge_cases = [
        "Check behavior when required input is missing or invalid.",
        "Check minimum, maximum, and boundary values.",
        "Check repeated or simultaneous requests for duplicate or inconsistent results.",
    ]
    if re.search(r"\b(file|upload|import|export)\b", description_lower):
        edge_cases.append("Check empty, unsupported, and oversized files.")
    if re.search(r"\b(search|filter)\b", description_lower):
        edge_cases.append("Check searches with no matches and unusually long search terms.")

    if re.match(r"^(the system|system|the application|application|the service|service)\s+(shall|must|should|will)\b", description_lower):
        improved_requirement = normalized_description + "."
    elif re.match(r"^(when|whenever|upon|after|before|if|once)\b", description_lower):
        improved_requirement = f"The system shall ensure that {normalized_description[0].lower() + normalized_description[1:]}."
    else:
        improved_requirement = f"The system shall {normalized_description[0].lower() + normalized_description[1:]}."

    if not re.search(r"\d", description_lower):
        if ambiguity_issues:
            improved_requirement += " Replace vague wording with a specific measurable success threshold."
        else:
            improved_requirement += " Define a measurable success threshold where applicable."
    improved_requirement += " Specify a clear response for invalid input and failed operations."

    acceptance_criteria = [
        f"Given valid preconditions, when the behavior is triggered, then the system produces the outcome described for '{title.strip()}'.",
        "Given missing or invalid input, then the system provides clear feedback and avoids unintended changes.",
        "Given boundary values or repeated requests, then the system handles them consistently without data loss.",
    ]

    return {
        "ambiguity_issues": ambiguity_issues,
        "missing_information": missing_information,
        "testability_issues": testability_issues,
        "assumptions": [],
        "edge_cases": edge_cases,
        "improved_requirement": improved_requirement,
        "acceptance_criteria": acceptance_criteria,
    }