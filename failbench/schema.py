"""Schema loading and validation for FailBench (stdlib only).

Authoritative definitions live in ``docs/CONTRACT.md``. This module is the
executable form of that contract: it loads probes/evidence from disk and
validates records, returning human-readable error lists (never raising for
ordinary data errors).
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASSES: Dict[str, str] = {
    "hallucination": "hal",
    "instruction_following": "if",
    "context_retrieval": "ctx",
    "reasoning_consistency": "rea",
    "sycophancy": "syc",
    "structured_output": "str",
    "multilingual": "ml",
    "safety_consistency": "saf",
    "agentic_reliability": "agt",
    "determinism_calibration": "det",
}
CLASS_ABBR: Dict[str, str] = {v: k for k, v in CLASSES.items()}

SEVERITIES: Tuple[str, ...] = ("critical", "high", "medium", "low")
EVIDENCE_STATUS: Tuple[str, ...] = ("cited", "refuted", "tested")
SOURCE_TYPES: Tuple[str, ...] = (
    "hn_story",
    "github_issue",
    "arxiv",
    "blog",
    "vendor_doc",
    "reddit_thread",
    "forum_thread",
    "docs",
)
SCORING_TYPES: Tuple[str, ...] = (
    "contains_all",
    "contains_any",
    "not_contains_any",
    "exact_match",
    "regex",
    "json_schema",
    "numeric",
    "all_of",
)
PROMPT_ROLES: Tuple[str, ...] = ("system", "user", "assistant")
EVIDENCE_METRIC_KEYS: Tuple[str, ...] = (
    "hn_points",
    "hn_comments",
    "github_reactions",
    "github_comments",
    "reddit_upvotes",
    "reddit_comments",
    "citations",
    "stars",
)

PROBE_ID_RE = re.compile(r"^[a-z]{2,3}_[a-z0-9_]{2,56}_\d{2}$")
EVIDENCE_ID_RE = re.compile(r"^ev_[a-z]{2,3}_\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://[^\s]+$")

ROOT = Path(__file__).resolve().parent.parent
PROBES_DIR = ROOT / "probes"
EVIDENCE_DIR = ROOT / "data" / "evidence"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    # utf-8-sig tolerates a BOM written by some Windows editors.
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _iter_probe_files(probes_root: Optional[Path] = None) -> Iterable[Path]:
    root = Path(probes_root) if probes_root else PROBES_DIR
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.json") if p.is_file() and not p.name.startswith("_"))


def load_probes(probes_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return all probe records found under ``probes/``.

    Records that fail to parse raise ``ValueError`` with the file path; schema
    problems are reported by :func:`validate_probe`.
    """
    records: List[Dict[str, Any]] = []
    for path in _iter_probe_files(probes_root):
        try:
            data = load_json(path)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path}: top-level JSON value must be an object")
        data.setdefault("_file", str(path))
        records.append(data)
    return records


def _iter_evidence_files(evidence_root: Optional[Path] = None) -> Iterable[Path]:
    root = Path(evidence_root) if evidence_root else EVIDENCE_DIR
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.jsonl") if p.is_file())


def load_evidence(evidence_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return all evidence records from ``data/evidence/*.jsonl``."""
    records: List[Dict[str, Any]] = []
    for path in _iter_evidence_files(evidence_root):
        with open(path, "r", encoding="utf-8-sig") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
                if not isinstance(data, dict):
                    raise ValueError(f"{path}:{lineno}: evidence record must be an object")
                data.setdefault("_file", str(path))
                data.setdefault("_line", lineno)
                records.append(data)
    return records


# ---------------------------------------------------------------------------
# Small validators
# ---------------------------------------------------------------------------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_url(value: Any, field: str, errors: List[str]) -> None:
    if not isinstance(value, str) or not URL_RE.match(value):
        errors.append(f"{field}: must be an http(s) URL")


def _check_iso_date(value: Any, field: str, errors: List[str], nullable: bool = True) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not DATE_RE.match(value):
        errors.append(f"{field}: must be YYYY-MM-DD" + (" or null" if nullable else ""))
        return
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field}: not a real calendar date: {value!r}")


# ---------------------------------------------------------------------------
# Scoring validation
# ---------------------------------------------------------------------------

def validate_scoring(obj: Any, path: str = "scoring") -> List[str]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return [f"{path}: must be an object"]
    stype = obj.get("type")
    if stype not in SCORING_TYPES:
        return [f"{path}.type: must be one of {', '.join(SCORING_TYPES)}"]
    case_sensitive = obj.get("case_sensitive", False)
    if not isinstance(case_sensitive, bool):
        errors.append(f"{path}.case_sensitive: must be boolean")

    def _string_list(field: str) -> None:
        value = obj.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{path}.{field}: must be a non-empty list of strings")
            return
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item:
                errors.append(f"{path}.{field}[{i}]: must be a non-empty string")

    if stype in ("contains_all", "contains_any", "not_contains_any"):
        _string_list("value")
    elif stype == "exact_match":
        if not isinstance(obj.get("value"), str) or not obj.get("value"):
            errors.append(f"{path}.value: must be a non-empty string")
    elif stype == "regex":
        pattern = obj.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            errors.append(f"{path}.pattern: must be a non-empty string")
        else:
            try:
                re.compile(pattern)
            except re.error as exc:  # pragma: no cover - invalid user data
                errors.append(f"{path}.pattern: invalid regex: {exc}")
        if "negate" in obj and not isinstance(obj["negate"], bool):
            errors.append(f"{path}.negate: must be boolean")
    elif stype == "json_schema":
        schema = obj.get("schema")
        if not isinstance(schema, dict):
            errors.append(f"{path}.schema: must be an object")
        else:
            errors.extend(_validate_schema_definition(schema, f"{path}.schema"))
    elif stype == "numeric":
        if not _is_number(obj.get("value")):
            errors.append(f"{path}.value: must be a number")
        tolerance = obj.get("tolerance", 0)
        if not _is_number(tolerance) or tolerance < 0:
            errors.append(f"{path}.tolerance: must be a non-negative number")
    elif stype == "all_of":
        units = obj.get("units")
        if not isinstance(units, list) or not units:
            errors.append(f"{path}.units: must be a non-empty list")
        else:
            for i, unit in enumerate(units):
                errors.extend(validate_scoring(unit, f"{path}.units[{i}]"))
    return errors


_SCHEMA_TYPES = ("object", "array", "string", "number", "integer", "boolean", "null")


def _validate_schema_definition(schema: Any, path: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: must be an object"]
    stype = schema.get("type")
    if stype is not None and stype not in _SCHEMA_TYPES:
        errors.append(f"{path}.type: unsupported type {stype!r}")
    if "enum" in schema and not isinstance(schema["enum"], list):
        errors.append(f"{path}.enum: must be a list")
    if stype == "object":
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            errors.append(f"{path}.properties: must be an object")
        else:
            for name, sub in props.items():
                errors.extend(_validate_schema_definition(sub, f"{path}.properties.{name}"))
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
            errors.append(f"{path}.required: must be a list of strings")
        if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
            errors.append(f"{path}.additionalProperties: must be boolean")
    if stype == "array" and "items" in schema:
        errors.extend(_validate_schema_definition(schema["items"], f"{path}.items"))
    return errors


# ---------------------------------------------------------------------------
# Record validation
# ---------------------------------------------------------------------------

def validate_evidence(record: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(record, dict):
        return ["record: must be an object"]

    rid = record.get("id")
    if not isinstance(rid, str) or not EVIDENCE_ID_RE.match(rid):
        errors.append("id: must match ev_<abbr>_<4 digits>")
    cls = record.get("class")
    if cls not in CLASSES:
        errors.append(f"class: must be one of {', '.join(CLASSES)}")
    elif isinstance(rid, str):
        prefix = CLASSES[cls]
        if not rid.startswith(f"ev_{prefix}_"):
            errors.append(f"id: prefix must be ev_{prefix}_ for class {cls}")

    title = record.get("title")
    if not isinstance(title, str) or not (5 <= len(title) <= 200):
        errors.append("title: must be a string of 5-200 chars")

    stype = record.get("source_type")
    if stype not in SOURCE_TYPES:
        errors.append(f"source_type: must be one of {', '.join(SOURCE_TYPES)}")
    _check_url(record.get("source_url"), "source_url", errors)

    _check_iso_date(record.get("published_date"), "published_date", errors)
    _check_iso_date(record.get("collected_at"), "collected_at", errors, nullable=False)

    if record.get("status") not in EVIDENCE_STATUS:
        errors.append(f"status: must be one of {', '.join(EVIDENCE_STATUS)}")

    collected_by = record.get("collected_by")
    if not isinstance(collected_by, str) or not collected_by.strip():
        errors.append("collected_by: must be a non-empty string")

    source_title = record.get("source_title")
    if source_title is not None and not isinstance(source_title, str):
        errors.append("source_title: must be a string or null")
    publisher = record.get("publisher")
    if publisher is not None and not isinstance(publisher, str):
        errors.append("publisher: must be a string or null")
    summary = record.get("summary")
    if summary is not None and (not isinstance(summary, str) or len(summary) > 400):
        errors.append("summary: must be a string of <=400 chars or null")
    quote = record.get("quote")
    if quote is not None:
        if not isinstance(quote, str):
            errors.append("quote: must be a string")
        elif len(quote) > 200:
            errors.append("quote: must be <=200 chars")

    metrics = record.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, dict):
            errors.append("metrics: must be an object or null")
        else:
            for key, value in metrics.items():
                if key not in EVIDENCE_METRIC_KEYS:
                    errors.append(f"metrics.{key}: unsupported metric key")
                if not _is_int(value) or value < 0:
                    errors.append(f"metrics.{key}: must be a non-negative integer")

    probe_ids = record.get("probe_ids", [])
    if not isinstance(probe_ids, list) or not all(isinstance(p, str) and p for p in probe_ids):
        errors.append("probe_ids: must be a list of non-empty strings")
    return errors


def validate_probe(record: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(record, dict):
        return ["record: must be an object"]

    rid = record.get("id")
    if not isinstance(rid, str) or not PROBE_ID_RE.match(rid):
        errors.append("id: must match <abbr>_<slug>_<2 digits>, lowercase")
    cls = record.get("class")
    if cls not in CLASSES:
        errors.append(f"class: must be one of {', '.join(CLASSES)}")
    elif isinstance(rid, str):
        prefix = CLASSES[cls]
        if not rid.startswith(f"{prefix}_"):
            errors.append(f"id: prefix must be {prefix}_ for class {cls}")

    title = record.get("title")
    if not isinstance(title, str) or not (5 <= len(title) <= 120):
        errors.append("title: must be a string of 5-120 chars")
    if record.get("severity") not in SEVERITIES:
        errors.append(f"severity: must be one of {', '.join(SEVERITIES)}")
    rationale = record.get("rationale")
    if not isinstance(rationale, str) or not (10 <= len(rationale) <= 400):
        errors.append("rationale: must be a string of 10-400 chars")

    evidence_ids = record.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        errors.append("evidence_ids: must be a list")
    else:
        for i, eid in enumerate(evidence_ids):
            if not isinstance(eid, str) or not EVIDENCE_ID_RE.match(eid):
                errors.append(f"evidence_ids[{i}]: must match ev_<abbr>_<4 digits>")

    prompt = record.get("prompt")
    total_chars = 0
    if not isinstance(prompt, list) or not prompt:
        errors.append("prompt: must be a non-empty list of messages")
    else:
        if len(prompt) > 20:
            errors.append("prompt: at most 20 messages")
        for i, msg in enumerate(prompt):
            if not isinstance(msg, dict):
                errors.append(f"prompt[{i}]: must be an object")
                continue
            if msg.get("role") not in PROMPT_ROLES:
                errors.append(f"prompt[{i}].role: must be system|user|assistant")
            content = msg.get("content")
            if not isinstance(content, str) or not content:
                errors.append(f"prompt[{i}].content: must be a non-empty string")
            elif len(content) > 20000:
                errors.append(f"prompt[{i}].content: must be <=20000 chars")
            else:
                total_chars += len(content)
    if total_chars > 30000:
        errors.append("prompt: total content must be <=30000 chars")

    params = record.get("params")
    if not isinstance(params, dict):
        errors.append("params: must be an object")
    else:
        temperature = params.get("temperature", 0)
        if not _is_number(temperature) or not (0 <= temperature <= 2):
            errors.append("params.temperature: must be a number in [0, 2]")
        max_tokens = params.get("max_tokens", 256)
        if not _is_int(max_tokens) or not (1 <= max_tokens <= 4096):
            errors.append("params.max_tokens: must be an integer in [1, 4096]")
        top_p = params.get("top_p")
        if top_p is not None and (not _is_number(top_p) or not (0 < top_p <= 1)):
            errors.append("params.top_p: must be a number in (0, 1]")

    repeats = record.get("repeats")
    if not _is_int(repeats) or not (1 <= repeats <= 5):
        errors.append("repeats: must be an integer in [1, 5]")

    if "scoring" not in record:
        errors.append("scoring: required")
    else:
        errors.extend(validate_scoring(record["scoring"]))

    for field in ("tags",):
        value = record.get(field, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"{field}: must be a list of strings")
    notes = record.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append("notes: must be a string or null")
    return errors


# ---------------------------------------------------------------------------
# Whole-corpus validation
# ---------------------------------------------------------------------------

def validate_all(
    probes_root: Optional[Path] = None,
    evidence_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate every probe and evidence record on disk.

    Returns a report dict with ``errors`` (list of strings), ``warnings``,
    ``probe_count``, ``evidence_count`` and per-class counts.
    """
    report: Dict[str, Any] = {
        "errors": [],
        "warnings": [],
        "probe_count": 0,
        "evidence_count": 0,
        "probe_by_class": {},
        "evidence_by_class": {},
    }

    probes: List[Dict[str, Any]] = []
    try:
        probes = load_probes(probes_root)
    except ValueError as exc:
        report["errors"].append(str(exc))

    seen_ids: Dict[str, str] = {}
    for record in probes:
        report["probe_count"] += 1
        file_hint = record.get("_file", "?")
        for err in validate_probe(record):
            report["errors"].append(f"probe {file_hint}: {err}")
        rid = record.get("id")
        if isinstance(rid, str):
            if rid in seen_ids:
                report["errors"].append(f"probe {file_hint}: duplicate id {rid} (also {seen_ids[rid]})")
            else:
                seen_ids[rid] = file_hint
        cls = record.get("class")
        if cls in CLASSES:
            report["probe_by_class"][cls] = report["probe_by_class"].get(cls, 0) + 1
        expected_dir = Path(file_hint).parent.name
        if cls in CLASSES and Path(file_hint).name != "_" and expected_dir != cls:
            report["warnings"].append(
                f"probe {file_hint}: expected parent directory {cls}/"
            )

    evidence: List[Dict[str, Any]] = []
    try:
        evidence = load_evidence(evidence_root)
    except ValueError as exc:
        report["errors"].append(str(exc))

    seen_ev: Dict[str, str] = {}
    for record in evidence:
        report["evidence_count"] += 1
        file_hint = f"{record.get('_file', '?')}:{record.get('_line', '?')}"
        for err in validate_evidence(record):
            report["errors"].append(f"evidence {file_hint}: {err}")
        rid = record.get("id")
        if isinstance(rid, str):
            if rid in seen_ev:
                report["errors"].append(f"evidence {file_hint}: duplicate id {rid}")
            else:
                seen_ev[rid] = file_hint
        cls = record.get("class")
        if cls in CLASSES:
            report["evidence_by_class"][cls] = report["evidence_by_class"].get(cls, 0) + 1
        fname = Path(record.get("_file", "")).stem
        if cls in CLASSES and fname != cls:
            report["errors"].append(
                f"evidence {file_hint}: file name must be <class>.jsonl ({cls}.jsonl), got {fname or '?'}.jsonl"
            )

    for cls in CLASSES:
        if report["probe_by_class"].get(cls, 0) == 0:
            report["warnings"].append(f"no probes for class {cls}")
        if report["evidence_by_class"].get(cls, 0) == 0:
            report["warnings"].append(f"no evidence for class {cls}")
    return report


if __name__ == "__main__":  # pragma: no cover - manual helper
    import sys

    result = validate_all()
    for err in result["errors"]:
        print("ERROR:", err)
    for warn in result["warnings"]:
        print("WARN:", warn)
    print(
        f"probes={result['probe_count']} evidence={result['evidence_count']} "
        f"errors={len(result['errors'])} warnings={len(result['warnings'])}"
    )
    sys.exit(1 if result["errors"] else 0)
