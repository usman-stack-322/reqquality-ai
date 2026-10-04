"""Find measurable values and standards introduced beyond original text."""

import re

VALUE_PATTERNS = (
    re.compile(
        r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:milliseconds?|msecs?|ms|seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?|%|percent|bytes?|kb|mb|gb|tb|users?|requests?|records?|items?|transactions?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:within|at least|at most|no more than|less than|greater than|up to|minimum(?: of)?|maximum(?: of)?|<=|>=|<|>)\s*\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:milliseconds?|msecs?|ms|seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?|%|percent|users?|requests?|records?|items?))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:TLS|SSL|OAuth|HTTP|HTTPS|SAML|ISO(?:\s*/\s*IEC)?|NIST|PCI)\s*[-/]?\s*\d+(?:\.\d+)*(?:[-/]\d+)*\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bPCI\s*[- ]?\s*DSS\b|\bGDPR\b|\bHIPAA\b|\bSOC\s*2\b", re.IGNORECASE),
    re.compile(r"\bISO\s*[- ]?\d{3,5}(?:\s*:\s*\d{4})?\b", re.IGNORECASE),
)


def _normalize_value(value):
    normalized = value.casefold()
    unit_aliases = (
        (r"\bmilliseconds?\b|\bmsecs?\b", "ms"),
        (r"\bseconds?\b|\bsecs?\b", "s"),
        (r"\bminutes?\b|\bmins?\b", "min"),
        (r"\bhours?\b|\bhrs?\b", "h"),
        (r"\bpercent\b", "%"),
    )
    for pattern, replacement in unit_aliases:
        normalized = re.sub(pattern, replacement, normalized)
    return re.sub(r"[^a-z0-9%]+", "", normalized)


def extract_values(text):
    """Return distinct concrete values found in text, preserving their spelling."""
    if not isinstance(text, str):
        return []

    found = []
    seen = set()
    for pattern in VALUE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            normalized = _normalize_value(value)
            if not normalized or any(existing in normalized for existing in seen):
                continue
            found.append(value)
            seen.add(normalized)
    return found


def find_introduced_values(text, original_text):
    """Return detected values that do not already appear in the original text."""
    original_values = {_normalize_value(value) for value in extract_values(original_text)}
    return [
        value
        for value in extract_values(text)
        if _normalize_value(value) not in original_values
    ]