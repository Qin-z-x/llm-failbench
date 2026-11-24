"""CI regression gate for FailBench results (stdlib only, offline).

Compares a baseline ``results.json`` with a current one and reports status
regressions (``pass`` -> ``fail``/``error``, ``fail`` -> ``error``), probes
that disappeared from the current run, improvements, and new probes.

The public API consumed by ``failbench/cli.py`` is :func:`compare_files`,
:func:`format_report` and :class:`GateError`::

    try:
        comparison = compare_files(baseline, current)
    except GateError as exc:          # config error -> CLI exit code 2
        ...
    print(format_report(comparison))
    return 1 if comparison["has_regressions"] else 0

Results documents follow ``docs/CONTRACT.md`` section 7. Nothing here touches
the network, and the filesystem is only read for the two results files.

Documented defensive choices
----------------------------
* Probe status ranking is ``pass`` (0) < ``fail`` (1) < ``error`` (2). A worse
  current status is a regression, a better one an improvement, equal is
  unchanged.
* A probe present in the baseline but absent from the current results is
  always a regression with ``kind == "missing_probe"`` and
  ``current_status is None``, regardless of its baseline status.
* A probe present only in the current results is reported under
  ``new_probes``; it is informational and never a regression.
* Non-standard status strings (for example ``"skipped"``) are accepted by the
  loader but are not comparable on the pass/fail/error scale. Such pairs never
  produce a regression or an improvement on their own; they are reported under
  ``unchanged`` using the *current* status, so unexpected status values can
  never crash the gate or raise a false alarm. (Missing probes are still
  regressions.)
* Duplicate probe ids inside one document: the first occurrence wins, keeping
  ordering deterministic.
* Regressions, improvements and unchanged entries follow the baseline probe
  order; new probes follow the current probe order.
* ``counts`` metadata is copied from the document when present; when absent or
  malformed it is rebuilt from the probe list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Filename looked up when the caller passes a results *run directory*.
RESULTS_FILENAME = "results.json"

#: Severity ordering from best to worst: pass(0) < fail(1) < error(2).
STATUS_RANK: Dict[str, int] = {"pass": 0, "fail": 1, "error": 2}

_MAX_LIST_ENTRIES = 20
_MAX_PATH_CHARS = 120
_MAX_LINE_CHARS = 199

_REGRESSION_LABELS: Dict[str, str] = {
    "status_regression": "REGRESSION",
    "missing_probe": "MISSING",
}

__all__ = [
    "GateError",
    "load_results",
    "compare_results",
    "compare_files",
    "format_report",
]


class GateError(Exception):
    """A results file is missing, unreadable, or not a results document.

    The CLI turns this into a clean configuration error (exit code 2) instead
    of printing a traceback.
    """


# ---------------------------------------------------------------------------
# Loading and validation
# ---------------------------------------------------------------------------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _resolve_results_path(path: Any) -> Path:
    """Return the concrete ``results.json`` path for a file or run directory."""
    if path is None:
        raise GateError("results file not found: None")
    try:
        candidate = Path(path)
    except TypeError as exc:  # defensive: unsupported path object
        raise GateError("results file not found: {0!r}".format(path)) from exc
    if candidate.is_dir():
        candidate = candidate / RESULTS_FILENAME
    if not candidate.is_file():
        raise GateError("results file not found: {0}".format(candidate))
    return candidate


def _document_problem(document: Any) -> Optional[str]:
    """Return a human-readable problem with a results document, or ``None``."""
    if not isinstance(document, dict):
        return "top-level JSON value must be an object"
    if not _is_int(document.get("schema")):
        return "schema: must be an integer"
    probes = document.get("probes")
    if not isinstance(probes, list):
        return "probes: must be a list"
    for index, probe in enumerate(probes):
        where = "probes[{0}]".format(index)
        if not isinstance(probe, dict):
            return "{0}: must be an object".format(where)
        for field in ("probe_id", "class", "status"):
            value = probe.get(field)
            if not isinstance(value, str) or not value.strip():
                return "{0}.{1}: must be a non-empty string".format(where, field)
    return None


def load_results(path: Any) -> Dict[str, Any]:
    """Load and minimally validate one results document.

    ``path`` may be a results run directory containing ``results.json`` or the
    ``results.json`` file itself. Raises :class:`GateError` when the file is
    missing, unreadable, not valid UTF-8/JSON, or not shaped like a results
    document (``schema`` integer + ``probes`` list with ``probe_id``,
    ``class`` and ``status`` on every entry).
    """
    resolved = _resolve_results_path(path)
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        raise GateError(
            "{0}: invalid JSON: file is not valid UTF-8 ({1})".format(resolved, exc)
        ) from exc
    except OSError as exc:
        raise GateError("cannot read results file: {0}: {1}".format(resolved, exc)) from exc

    try:
        document = json.loads(text)
    except (ValueError, RecursionError) as exc:  # JSONDecodeError is a ValueError
        raise GateError("{0}: invalid JSON: {1}".format(resolved, exc)) from exc

    problem = _document_problem(document)
    if problem is not None:
        raise GateError("invalid results document: {0}: {1}".format(resolved, problem))
    return document


def _index_probes(
    document: Dict[str, Any],
) -> Tuple[List[Tuple[str, Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
    """Return ``(ordered_pairs, by_id)`` for a validated document.

    The first occurrence of a duplicated probe id wins.
    """
    ordered: List[Tuple[str, Dict[str, Any]]] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    probes = document.get("probes")
    if not isinstance(probes, list):
        return ordered, by_id
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        probe_id = probe.get("probe_id")
        if not isinstance(probe_id, str) or probe_id in by_id:
            continue
        by_id[probe_id] = probe
        ordered.append((probe_id, probe))
    return ordered, by_id


def _probe_class(probe: Dict[str, Any]) -> str:
    value = probe.get("class")
    return value if isinstance(value, str) else ""


def _document_counts(document: Dict[str, Any]) -> Dict[str, Any]:
    """Return the document ``counts`` dict, rebuilt from probes if absent."""
    counts = document.get("counts")
    if isinstance(counts, dict):
        return dict(counts)
    fallback: Dict[str, Any] = {"probes": 0, "pass": 0, "fail": 0, "error": 0}
    probes = document.get("probes")
    if isinstance(probes, list):
        fallback["probes"] = len(probes)
        for probe in probes:
            status = probe.get("status") if isinstance(probe, dict) else None
            if status in STATUS_RANK:
                fallback[status] += 1
    return fallback


def _metadata(document: Dict[str, Any], path: Optional[str]) -> Dict[str, Any]:
    run_id = document.get("run_id")
    return {
        "path": None if path is None else str(path),
        "run_id": run_id if isinstance(run_id, str) and run_id.strip() else None,
        "counts": _document_counts(document),
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_results(
    baseline: Dict[str, Any],
    current: Dict[str, Any],
    *,
    baseline_path: Optional[str] = None,
    current_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare two already-loaded results documents.

    Never raises for status differences; only :class:`GateError` for malformed
    documents. The returned dict has exactly these keys::

        baseline, current, regressions, improvements, new_probes, unchanged,
        has_regressions, summary

    See the module docstring for ordering and severity rules.
    """
    for label, document in (("baseline", baseline), ("current", current)):
        problem = _document_problem(document)
        if problem is not None:
            raise GateError("invalid results document: {0}: {1}".format(label, problem))

    baseline_ordered, baseline_index = _index_probes(baseline)
    current_ordered, current_index = _index_probes(current)

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []
    unchanged: List[Dict[str, Any]] = []

    # Baseline order decides the order of all baseline-derived sections.
    for probe_id, base_probe in baseline_ordered:
        base_status = base_probe.get("status")
        base_class = _probe_class(base_probe)
        current_probe = current_index.get(probe_id)

        if current_probe is None:
            regressions.append(
                {
                    "probe_id": probe_id,
                    "class": base_class,
                    "baseline_status": base_status,
                    "current_status": None,
                    "kind": "missing_probe",
                }
            )
            continue

        current_status = current_probe.get("status")
        base_rank = STATUS_RANK.get(base_status) if isinstance(base_status, str) else None
        current_rank = (
            STATUS_RANK.get(current_status) if isinstance(current_status, str) else None
        )

        if base_rank is None or current_rank is None:
            # Non-standard status on either side: not comparable, never alarm.
            unchanged.append(
                {"probe_id": probe_id, "class": base_class, "status": current_status}
            )
            continue

        if current_rank > base_rank:
            regressions.append(
                {
                    "probe_id": probe_id,
                    "class": base_class,
                    "baseline_status": base_status,
                    "current_status": current_status,
                    "kind": "status_regression",
                }
            )
        elif current_rank < base_rank:
            improvements.append(
                {
                    "probe_id": probe_id,
                    "class": base_class,
                    "baseline_status": base_status,
                    "current_status": current_status,
                }
            )
        else:
            unchanged.append(
                {"probe_id": probe_id, "class": base_class, "status": current_status}
            )

    # Current order decides the order of new (informational) probes.
    new_probes: List[Dict[str, Any]] = []
    for probe_id, current_probe in current_ordered:
        if probe_id in baseline_index:
            continue
        new_probes.append(
            {
                "probe_id": probe_id,
                "class": _probe_class(current_probe),
                "current_status": current_probe.get("status"),
            }
        )

    summary = {
        "regressions": len(regressions),
        "improvements": len(improvements),
        "new": len(new_probes),
        "unchanged": len(unchanged),
        "baseline_probes": len(baseline_ordered),
        "current_probes": len(current_ordered),
    }

    return {
        "baseline": _metadata(baseline, baseline_path),
        "current": _metadata(current, current_path),
        "regressions": regressions,
        "improvements": improvements,
        "new_probes": new_probes,
        "unchanged": unchanged,
        "has_regressions": bool(regressions),
        "summary": summary,
    }


def compare_files(baseline_path: Any, current_path: Any) -> Dict[str, Any]:
    """Load two results files (or run directories) and compare them.

    Path metadata in the returned comparison is ``str()`` of the paths exactly
    as given to this function.
    """
    baseline = load_results(baseline_path)
    current = load_results(current_path)
    return compare_results(
        baseline,
        current,
        baseline_path=str(baseline_path),
        current_path=str(current_path),
    )


# ---------------------------------------------------------------------------
# Human-readable report
# ---------------------------------------------------------------------------

def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _count(value: Any, fallback: int) -> int:
    return value if _is_int(value) and value >= 0 else fallback


def _display_path(value: Any) -> str:
    if value is None or value == "":
        return "<unknown>"
    text = str(value)
    if len(text) <= _MAX_PATH_CHARS:
        return text
    return "..." + text[-(_MAX_PATH_CHARS - 3):]


def _run_line(label: str, meta: Dict[str, Any], probe_count: int) -> str:
    path_text = _display_path(meta.get("path"))
    run_id = meta.get("run_id")
    run_text = run_id if isinstance(run_id, str) and run_id.strip() else "<unknown>"
    return "{0} {1} (run {2}, {3} probes)".format(label, path_text, run_text, probe_count)


def _field(entry: Any, name: str) -> str:
    value = entry.get(name) if isinstance(entry, dict) else None
    if value is None:
        return "?"
    return str(value)


def _format_regression(entry: Any) -> str:
    probe_id = _field(entry, "probe_id")
    cls = _field(entry, "class")
    kind = entry.get("kind") if isinstance(entry, dict) else None
    kind_text = kind if isinstance(kind, str) else ""
    label = _REGRESSION_LABELS.get(kind_text, "REGRESSION")
    if kind_text == "missing_probe":
        detail = "probe missing from current results (was {0})".format(
            _field(entry, "baseline_status")
        )
        return "  {0} {1} ({2}): {3}".format(label.ljust(10), probe_id, cls, detail)
    return "  {0} {1} ({2}): {3} -> {4}".format(
        label.ljust(10),
        probe_id,
        cls,
        _field(entry, "baseline_status"),
        _field(entry, "current_status"),
    )


def _format_improvement(entry: Any) -> str:
    return "  IMPROVEMENT {0} ({1}): {2} -> {3}".format(
        _field(entry, "probe_id"),
        _field(entry, "class"),
        _field(entry, "baseline_status"),
        _field(entry, "current_status"),
    )


def _format_entries(entries: List[Any], formatter: Any) -> List[str]:
    lines: List[str] = []
    for entry in entries[:_MAX_LIST_ENTRIES]:
        lines.append(formatter(entry))
    hidden = len(entries) - _MAX_LIST_ENTRIES
    if hidden > 0:
        lines.append("  ... and {0} more".format(hidden))
    return lines


def _clip_line(line: str, limit: int = _MAX_LINE_CHARS) -> str:
    if len(line) <= limit:
        return line
    return line[: limit - 3] + "..."


def format_report(comparison: Dict[str, Any]) -> str:
    """Render a deterministic, human-readable regression gate report."""
    if not isinstance(comparison, dict):
        raise GateError("invalid comparison: expected an object")

    baseline_meta = _as_dict(comparison.get("baseline"))
    current_meta = _as_dict(comparison.get("current"))
    summary = _as_dict(comparison.get("summary"))
    regressions = _as_list(comparison.get("regressions"))
    improvements = _as_list(comparison.get("improvements"))
    unchanged = _as_list(comparison.get("unchanged"))
    new_probes = _as_list(comparison.get("new_probes"))

    common_fallback = len(regressions) + len(improvements) + len(unchanged)
    baseline_count = _count(summary.get("baseline_probes"), common_fallback)
    current_count = _count(summary.get("current_probes"), common_fallback + len(new_probes))
    unchanged_count = _count(summary.get("unchanged"), len(unchanged))
    new_count = _count(summary.get("new"), len(new_probes))

    lines: List[str] = ["FailBench regression gate"]
    lines.append(_run_line("baseline:", baseline_meta, baseline_count))
    lines.append(_run_line("current: ", current_meta, current_count))
    lines.append("")
    if regressions:
        lines.append("Regressions ({0}):".format(len(regressions)))
        lines.extend(_format_entries(regressions, _format_regression))
    if improvements:
        lines.append("Improvements ({0}):".format(len(improvements)))
        lines.extend(_format_entries(improvements, _format_improvement))
    lines.append("Unchanged: {0}".format(unchanged_count))
    lines.append("New probes (not in baseline): {0}".format(new_count))
    lines.append("")
    if regressions:
        lines.append("GATE FAIL: {0} regression(s) detected.".format(len(regressions)))
    else:
        lines.append("GATE PASS: no regressions ({0} probes compared).".format(baseline_count))

    return "\n".join(_clip_line(line) for line in lines)
