"""Gemini-backed requirement analysis with safe, structured failures."""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")
LOGGER = logging.getLogger(__name__)

LIST_FIELDS = (
    "ambiguity_issues",
    "missing_information",
    "testability_issues",
    "assumptions",
    "edge_cases",
    "acceptance_criteria",
)
REQUIRED_FIELDS = (*LIST_FIELDS, "improved_requirement")

SYSTEM_INSTRUCTION = """
Act as a Requirements Engineering and Software Quality Engineering assistant.
Analyze the provided requirement without inventing project facts. Clearly
identify uncertainty as an assumption. Make improved requirements specific,
measurable, and testable. Generate practical acceptance criteria. Return JSON
only, with exactly the requested fields. Every list field must contain strings.
""".strip()

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ambiguity_issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        "missing_information": {"type": "ARRAY", "items": {"type": "STRING"}},
        "testability_issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        "assumptions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "edge_cases": {"type": "ARRAY", "items": {"type": "STRING"}},
        "improved_requirement": {"type": "STRING"},
        "acceptance_criteria": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": list(REQUIRED_FIELDS),
}


def _validate_analysis(value):
    if not isinstance(value, dict):
        return None

    analysis = {}
    for field in LIST_FIELDS:
        items = value.get(field)
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            return None
        analysis[field] = [item.strip() for item in items if item.strip()]

    improved_requirement = value.get("improved_requirement")
    if not isinstance(improved_requirement, str) or not improved_requirement.strip():
        return None
    analysis["improved_requirement"] = improved_requirement.strip()
    return analysis


def _error_status(error):
    code = getattr(error, "code", None)
    if not isinstance(code, int):
        code = getattr(getattr(error, "response", None), "status_code", None)
    error_name = type(error).__name__.lower()

    if code in (401, 403) or "unauthorized" in error_name or "permissiondenied" in error_name:
        return "authentication_error"
    if code == 404 or "notfound" in error_name:
        return "model_unavailable"
    if code == 429 or "quota" in error_name or "resourceexhausted" in error_name:
        return "quota_exceeded"
    if code in (408, 504) or any(word in error_name for word in ("timeout", "connect", "network")):
        return "network_error"
    if isinstance(error, (TypeError, ValueError)):
        return "sdk_usage_error"
    return "api_error"


def _log_status(model, status, category, error=None):
    exception_type = type(error).__name__ if error is not None else "none"
    http_api_code = getattr(error, "code", None) if error is not None else "none"
    if error is not None and not isinstance(http_api_code, int):
        http_api_code = getattr(getattr(error, "response", None), "status_code", "none")

    log = LOGGER.info if status == "success" else LOGGER.warning
    log(
        "Gemini diagnostic model=%s category=%s http_api_code=%s exception_type=%s llm_status=%s",
        model or "<missing>",
        category,
        http_api_code,
        exception_type,
        status,
    )


def analyze_with_llm(requirement):
    """Return a validated Gemini analysis and a non-sensitive status code."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip()

    if not api_key:
        _log_status(model, "missing_api_key", "configuration")
        return {"status": "missing_api_key", "analysis": None}
    if not model or model == "your_model_name_here":
        _log_status(model, "missing_model", "configuration")
        return {"status": "missing_model", "analysis": None}

    prompt = (
        "Analyze this requirement data and return the required JSON structure:\n"
        f"{json.dumps(requirement, ensure_ascii=True)}"
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
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                temperature=0.2,
            ),
        )
    except Exception as error:
        status = _error_status(error)
        _log_status(model, status, status, error)
        return {"status": status, "analysis": None}

    try:
        parsed_response = json.loads(response.text or "")
    except (json.JSONDecodeError, TypeError) as error:
        _log_status(model, "malformed_json", "malformed_json", error)
        return {"status": "malformed_json", "analysis": None}

    analysis = _validate_analysis(parsed_response)
    if analysis is None:
        _log_status(model, "malformed_json", "schema_validation", ValueError())
        return {"status": "malformed_json", "analysis": None}

    _log_status(model, "success", "none")
    return {"status": "success", "analysis": analysis}