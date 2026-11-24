"""Mechanical, judge-free scoring for FailBench probes (stdlib only).

Every scorer is a pure function of (scoring spec, model response text) and
returns ``(passed: bool, detail: str)``. Provider/network failures must be
handled by the runner as *errors*, never routed through these functions.

Scoring semantics are specified in ``docs/CONTRACT.md`` section 6.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

_WHITESPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def normalize(text: Any, case_sensitive: bool = False) -> str:
    """Collapse whitespace, normalize NBSP, trim; lowercase unless sensitive."""
    if text is None:
        return ""
    value = str(text).replace("\u00a0", " ")
    value = _WHITESPACE.sub(" ", value).strip()
    return value if case_sensitive else value.lower()


def _truncate(text: Any, limit: int = 200) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").replace("\n", " ")
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


# ---------------------------------------------------------------------------
# JSON extraction and minimal schema validation
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Tuple[Optional[Any], str]:
    """Extract the first parseable JSON value from a model response.

    Tries fenced code blocks first, then the whole string, then every
    ``{``/``[`` start position. Returns ``(value, "")`` on success or
    ``(None, reason)`` on failure.
    """
    if not isinstance(text, str) or not text.strip():
        return None, "empty response"
    candidates: List[str] = []
    for match in _FENCE.finditer(text):
        candidates.append(match.group(1).strip())
    candidates.append(text.strip())
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            return json.loads(candidate), ""
        except (json.JSONDecodeError, ValueError):
            pass
    stripped = text.strip()
    for index, char in enumerate(stripped):
        if char not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
            return value, ""
        except (json.JSONDecodeError, ValueError):
            continue
    return None, "no parseable JSON found in response"


def validate_schema_value(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Validate ``value`` against the minimal JSON Schema subset from the contract.

    Returns a list of human-readable errors (empty means valid).
    """
    errors: List[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: schema must be an object"]

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: {_truncate(value, 60)!r} not in enum {enum[:6]}")

    expected = schema.get("type")
    if expected is not None:
        ok = True
        if expected == "object":
            ok = isinstance(value, dict)
        elif expected == "array":
            ok = isinstance(value, list)
        elif expected == "string":
            ok = isinstance(value, str)
        elif expected == "boolean":
            ok = isinstance(value, bool)
        elif expected == "null":
            ok = value is None
        elif expected == "integer":
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif expected == "number":
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            errors.append(f"{path}: unsupported schema type {expected!r}")
            return errors
        if not ok:
            errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
            return errors

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required key {key!r}")
        if isinstance(properties, dict):
            for key, subschema in properties.items():
                if key in value:
                    errors.extend(validate_schema_value(value[key], subschema, f"{path}.{key}"))
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            extras = [key for key in value if key not in properties]
            if extras:
                errors.append(f"{path}: unexpected keys {sorted(extras)[:6]}")

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(validate_schema_value(item, schema["items"], f"{path}[{index}]"))

    return errors


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------

def score(scoring: Dict[str, Any], response_text: str) -> Tuple[bool, str]:
    """Score one response against one scoring spec. Returns (passed, detail)."""
    if not isinstance(scoring, dict):
        return False, "invalid scoring spec: not an object"
    stype = scoring.get("type")
    text = "" if response_text is None else str(response_text)
    case_sensitive = scoring.get("case_sensitive") is True
    normalized = normalize(text, case_sensitive)

    if stype in ("contains_all", "contains_any", "not_contains_any"):
        values = scoring.get("value")
        if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
            return False, "invalid scoring spec: 'value' must be a non-empty string list"
        targets = [item if case_sensitive else item.lower() for item in values]
        haystack = normalize(text, case_sensitive)
        hits = [values[i] for i, target in enumerate(targets) if normalize(target, case_sensitive) in haystack]
        if stype == "contains_all":
            missing = [v for v in values if v not in hits]
            if missing:
                return False, f"missing required substring(s): {_truncate(', '.join(missing), 160)}"
            return True, f"found all {len(values)} required substring(s)"
        if stype == "contains_any":
            if not hits:
                return False, f"none of the expected substrings found: {_truncate(', '.join(values), 160)}"
            return True, f"found expected substring: {_truncate(hits[0], 120)}"
        found = [v for v in values if v in hits]
        if found:
            return False, f"forbidden substring(s) present: {_truncate(', '.join(found), 160)}"
        return True, "no forbidden substrings present"

    if stype == "exact_match":
        expected = scoring.get("value")
        if not isinstance(expected, str) or not expected:
            return False, "invalid scoring spec: 'value' must be a non-empty string"
        expected_norm = normalize(expected, case_sensitive)
        if normalized == expected_norm:
            return True, "normalized response equals expected value"
        return False, f"expected {_truncate(expected_norm, 120)!r}, got {_truncate(normalized, 120)!r}"

    if stype == "regex":
        pattern = scoring.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return False, "invalid scoring spec: 'pattern' must be a non-empty string"
        try:
            compiled = re.compile(pattern, re.S | re.M)
        except re.error as exc:
            return False, f"invalid regex: {exc}"
        match = compiled.search(text)
        negate = scoring.get("negate") is True
        if negate:
            if match:
                return False, f"forbidden pattern matched: {_truncate(match.group(0), 120)!r}"
            return True, "forbidden pattern not present"
        if match:
            return True, f"pattern matched: {_truncate(match.group(0), 120)!r}"
        return False, f"pattern not found: {_truncate(pattern, 120)}"

    if stype == "json_schema":
        schema = scoring.get("schema")
        if not isinstance(schema, dict):
            return False, "invalid scoring spec: 'schema' must be an object"
        value, err = extract_json(text)
        if err:
            return False, f"JSON extraction failed: {err}. Response: {_truncate(text, 160)}"
        errors = validate_schema_value(value, schema)
        if errors:
            return False, "schema violation(s): " + "; ".join(errors[:5])
        return True, "valid JSON matching schema"

    if stype == "numeric":
        expected = scoring.get("value")
        tolerance = scoring.get("tolerance", 0)
        if not isinstance(expected, (int, float)) or isinstance(expected, bool):
            return False, "invalid scoring spec: 'value' must be a number"
        try:
            tolerance = float(tolerance)
        except (TypeError, ValueError):
            return False, "invalid scoring spec: 'tolerance' must be a number"
        match = _NUMBER.search(text)
        if not match:
            return False, f"no number found in response: {_truncate(text, 160)}"
        try:
            found = float(match.group(0))
        except ValueError:
            return False, f"could not parse number {match.group(0)!r}"
        if abs(found - float(expected)) <= tolerance:
            return True, f"found {found} within tolerance {tolerance} of expected {expected}"
        return False, f"expected {expected} (tolerance {tolerance}) but found {found}"

    if stype == "all_of":
        units = scoring.get("units")
        if not isinstance(units, list) or not units:
            return False, "invalid scoring spec: 'units' must be a non-empty list"
        details: List[str] = []
        for index, unit in enumerate(units):
            passed, detail = score(unit, text)
            if not passed:
                return False, f"unit[{index}] failed: {detail}"
            details.append(f"unit[{index}] ok")
        return True, "; ".join(details)

    return False, f"unsupported scoring type: {stype!r}"


def score_probe_scoring(scoring: Dict[str, Any], responses: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Score all repeats for a probe.

    The probe passes only if **all** repeats pass (deterministic probes should
    not be flaky). Returns ``(passed, attempts)`` where attempts is a list of
    ``{"index", "passed", "detail", "response_sha256"}``.
    """
    import hashlib

    attempts: List[Dict[str, Any]] = []
    all_passed = True
    for index, response in enumerate(responses):
        passed, detail = score(scoring, response)
        all_passed = all_passed and passed
        attempts.append(
            {
                "index": index,
                "passed": passed,
                "detail": detail,
                "response_sha256": hashlib.sha256(str(response).encode("utf-8")).hexdigest(),
            }
        )
    return all_passed, attempts
