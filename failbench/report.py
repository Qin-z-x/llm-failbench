"""FailBench report generator: static, self-contained dashboard plus Markdown report.

This module is the public-facing report layer. It reads a contract-shaped
``results.json`` (docs/CONTRACT.md section 7), the probe corpus (section 5) and
the evidence atlas (section 4), and writes:

* ``<out_dir>/index.html`` - a single self-contained HTML file (inline CSS, JS
  and JSON data; no external scripts, fonts, images or network requests;
  external ``<a>`` links point only at cited evidence sources and carry
  ``rel="noopener noreferrer"``).
* a generated Markdown report (``docs/RESULTS.md`` by default).

Honesty rules from docs/CONTRACT.md section 1 governed this module: the demo run
uses a deterministic mock provider, no live model endpoint was measured during
the build, and the generated artifacts must say so verbatim. Nothing in the
report is fabricated at render time: every number is derived from the input
files and every missing input degrades to an explicit empty state.

Usage::

    from failbench.report import render
    summary = render("results/demo", "site")

The CLI wrapper (``failbench/cli.py``) calls :func:`render` and prints the
returned summary. This module is stdlib-only.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .schema import (
    CLASSES,
    EVIDENCE_METRIC_KEYS,
    load_evidence,
    load_probes,
    ROOT as REPO_ROOT,
)

__all__ = ["render", "HONESTY_SENTENCE"]

VERSION = "0.1.0"

#: Required verbatim honesty sentence (docs/CONTRACT.md section 1). Both the
#: committed Markdown report and the generated site must contain this exact
#: string; the site additionally shows it inside an amber demo note box.
HONESTY_SENTENCE = (
    "No live model endpoint was available during this build, so the committed "
    "demo numbers exercise the pipeline rather than measure any model."
)

HONESTY_SUBSTRING = "mock provider"

CLASS_LABELS: Dict[str, str] = {
    "hallucination": "Hallucination",
    "instruction_following": "Instruction following",
    "context_retrieval": "Context retrieval",
    "reasoning_consistency": "Reasoning consistency",
    "sycophancy": "Sycophancy",
    "structured_output": "Structured output",
    "multilingual": "Multilingual",
    "safety_consistency": "Safety consistency",
    "agentic_reliability": "Agentic reliability",
    "determinism_calibration": "Determinism & calibration",
}

SEVERITY_ORDER: Tuple[str, ...] = ("critical", "high", "medium", "low")
SEVERITY_WEIGHTS: Dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SEVERITY_LABELS: Dict[str, str] = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}
STATUS_ORDER: Tuple[str, ...] = ("pass", "fail", "error")

SOURCE_TYPE_LABELS: Dict[str, str] = {
    "hn_story": "Hacker News",
    "github_issue": "GitHub issue",
    "arxiv": "arXiv preprint",
    "blog": "Blog post",
    "vendor_doc": "Vendor documentation",
    "reddit_thread": "Reddit thread",
    "forum_thread": "Forum thread",
    "docs": "Documentation",
}

METRIC_LABELS: Dict[str, str] = {
    "hn_points": "HN points",
    "hn_comments": "HN comments",
    "github_reactions": "GitHub reactions",
    "github_comments": "GitHub comments",
    "reddit_upvotes": "Reddit upvotes",
    "reddit_comments": "Reddit comments",
    "citations": "Citations",
    "stars": "Stars",
}

# Priority used to rank evidence records inside a class. These are attention
# signals reported by the cited source, never measurements of model behaviour.
METRIC_SORT_PRIORITY: Tuple[str, ...] = (
    "hn_points",
    "citations",
    "github_reactions",
    "reddit_upvotes",
    "stars",
    "hn_comments",
    "github_comments",
    "reddit_comments",
)

DEMO_BANNER_TEXT = (
    "Demo data. This committed report was produced by the deterministic mock "
    "provider, not by a live model endpoint. Treat every number below as a "
    "pipeline demonstration, not as a measurement of any model."
)
FIXTURE_BANNER_TEXT = (
    "Fixture render. This page was generated from a synthetic fixture while the "
    "real demo run and cited evidence corpus were still being built. It "
    "validates the report pipeline only; regenerate the site from the committed "
    "results before publishing."
)
LIVE_BANNER_TEXT = (
    "Live run. These numbers were produced by the configured provider against a "
    "real endpoint. Results are specific to that endpoint, model, parameters "
    "and date; they are not a general benchmark of the model family."
)

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _esc(value: Any) -> str:
    """HTML-escape any value for safe use in text or attribute position."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _text(value: Any) -> str:
    """Plain-text rendering of a value (escaped, newlines preserved as spaces)."""
    if value is None:
        return ""
    return _esc(" ".join(str(value).split()))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return _esc(value)


def _fmt_pct(rate: Optional[float]) -> str:
    if rate is None:
        return "&mdash;"
    return f"{rate * 100:.1f}%"


def _fmt_pct_md(rate: Optional[float]) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.1f}%"


def _ratio(passed: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(passed / total, 4)


def _safe_href(url: Any) -> str:
    """Return an escaped http(s) href, or an empty string for unsafe values."""
    if not isinstance(url, str):
        return ""
    url = url.strip()
    if not re.match(r"^https?://[^\s]+$", url):
        return ""
    return _esc(url)


def _host(url: str) -> str:
    match = re.match(r"^https?://([^/]+)", url or "")
    if not match:
        return ""
    host = match.group(1).lower()
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def _truncate(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def _warn(warnings: List[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


# ---------------------------------------------------------------------------
# Loading and normalization
# ---------------------------------------------------------------------------


def _resolve_results_path(results_path: Any) -> Path:
    if results_path is None:
        raise ValueError("results_path is required (path to a results directory or results.json)")
    path = Path(results_path)
    if path.is_dir():
        path = path / "results.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"results.json not found at {path}. Run the benchmark first, e.g. "
            "`python -m failbench run --provider mock --demo --out results/demo`."
        )
    return path


def _load_json_file(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return data


def _load_corpus(probes_dir: Any, warnings: List[str]) -> List[Dict[str, Any]]:
    try:
        probes = load_probes(Path(probes_dir) if probes_dir is not None else None)
    except (ValueError, OSError) as exc:
        _warn(warnings, f"probe corpus could not be loaded ({exc}); the report shows results-only data.")
        return []
    if not probes:
        _warn(warnings, "probe corpus is empty or missing; corpus table and probe metadata are limited.")
    return [record for record in probes if isinstance(record, dict)]


def _load_atlas(evidence_dir: Any, warnings: List[str]) -> List[Dict[str, Any]]:
    try:
        records = load_evidence(Path(evidence_dir) if evidence_dir is not None else None)
    except (ValueError, OSError) as exc:
        _warn(warnings, f"evidence atlas could not be loaded ({exc}); the atlas section is empty.")
        return []
    if not records:
        _warn(warnings, "evidence atlas is empty or missing; the atlas section shows an explicit empty state.")
    return [record for record in records if isinstance(record, dict)]


def _class_abbr(cls: str) -> str:
    return CLASSES.get(cls, cls[:3] if cls else "?")


def _class_label(cls: str) -> str:
    return CLASS_LABELS.get(cls, cls.replace("_", " ").title() if cls else "Unknown")


def _severity_rank(severity: str) -> int:
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return len(SEVERITY_ORDER)


def _normalize_probe_rows(
    results: Dict[str, Any],
    corpus_by_id: Dict[str, Dict[str, Any]],
    warnings: List[str],
) -> List[Dict[str, Any]]:
    raw_probes = results.get("probes")
    if not isinstance(raw_probes, list):
        _warn(warnings, "results.json has no probe list; the results table is empty.")
        raw_probes = []

    rows: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    for index, raw in enumerate(raw_probes):
        if not isinstance(raw, dict):
            _warn(warnings, f"results probe entry #{index} is not an object; skipped.")
            continue
        probe_id = raw.get("probe_id")
        if not isinstance(probe_id, str) or not probe_id:
            probe_id = f"probe_{index + 1:03d}"
            _warn(warnings, f"results probe entry #{index} has no probe_id; labelled {probe_id}.")
        if probe_id in seen:
            _warn(warnings, f"duplicate probe_id {probe_id} in results.json; later entry rows are still shown.")
        corpus = corpus_by_id.get(probe_id, {})
        cls = raw.get("class") or corpus.get("class") or ""
        status = raw.get("status")
        if status not in STATUS_ORDER:
            _warn(warnings, f"probe {probe_id} has unexpected status {status!r}; treated as error.")
            status = "error"
        severity = raw.get("severity") or corpus.get("severity") or "unknown"
        if severity not in SEVERITY_WEIGHTS:
            _warn(warnings, f"probe {probe_id} has no valid severity ({severity!r}); excluded from weighted stats.")
        scoring = corpus.get("scoring") if isinstance(corpus.get("scoring"), dict) else {}
        row = {
            "id": probe_id,
            "class": cls,
            "class_label": _class_label(cls),
            "abbr": _class_abbr(cls),
            "title": str(raw.get("title") or corpus.get("title") or probe_id),
            "severity": severity,
            "status": status,
            "reason": str(raw.get("reason") or ""),
            "latency_ms": raw.get("latency_ms"),
            "tokens": raw.get("tokens") if isinstance(raw.get("tokens"), dict) else {},
            "response_sha256": raw.get("response_sha256"),
            "response_excerpt": str(raw.get("response_excerpt") or ""),
            "attempts": [],
            "rationale": str(corpus.get("rationale") or ""),
            "tags": [str(tag) for tag in (corpus.get("tags") or []) if isinstance(tag, str)][:8],
            "scoring_type": str(scoring.get("type") or ""),
            "evidence_ids": [str(eid) for eid in (corpus.get("evidence_ids") or []) if isinstance(eid, str)][:8],
            "corpus_present": bool(corpus),
        }
        attempts = raw.get("attempts")
        if isinstance(attempts, list):
            for attempt in attempts[:5]:
                if not isinstance(attempt, dict):
                    continue
                row["attempts"].append(
                    {
                        "index": attempt.get("index"),
                        "status": attempt.get("status"),
                        "reason": str(attempt.get("reason") or ""),
                        "latency_ms": attempt.get("latency_ms"),
                    }
                )
        rows.append(row)
        seen[probe_id] = index + 1

    rows.sort(key=lambda row: (_severity_rank(row["severity"]), row["class"], row["id"]))
    return rows


def _normalize_evidence(
    evidence: Sequence[Dict[str, Any]],
    warnings: List[str],
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, record in enumerate(evidence):
        if not isinstance(record, dict):
            _warn(warnings, f"evidence record #{index} is not an object; skipped.")
            continue
        url = record.get("source_url")
        if not _safe_href(url):
            _warn(warnings, f"evidence record {record.get('id', index)} has no safe http(s) source_url; card shows no link.")
        cls = record.get("class") if isinstance(record.get("class"), str) else ""
        metrics_raw = record.get("metrics")
        metrics: Dict[str, int] = {}
        if isinstance(metrics_raw, dict):
            for key, value in metrics_raw.items():
                if key in EVIDENCE_METRIC_KEYS and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    metrics[key] = value
        normalized.append(
            {
                "id": str(record.get("id") or f"ev_{index:04d}"),
                "class": cls,
                "class_label": _class_label(cls),
                "abbr": _class_abbr(cls),
                "title": str(record.get("title") or ""),
                "source_type": str(record.get("source_type") or ""),
                "source_url": str(url or ""),
                "source_title": str(record.get("source_title") or ""),
                "publisher": str(record.get("publisher") or _host(str(url or "")) or ""),
                "published_date": record.get("published_date"),
                "metrics": metrics,
                "quote": str(record.get("quote") or ""),
                "summary": str(record.get("summary") or ""),
                "status": str(record.get("status") or "cited"),
                "probe_ids": [str(pid) for pid in (record.get("probe_ids") or []) if isinstance(pid, str)][:12],
                "collected_by": str(record.get("collected_by") or ""),
                "collected_at": record.get("collected_at"),
            }
        )
    normalized.sort(
        key=lambda record: (
            list(CLASSES).index(record["class"]) if record["class"] in CLASSES else 99,
            -_popularity(record),
            record["title"].lower(),
        )
    )
    return normalized


def _popularity(record: Dict[str, Any]) -> int:
    metrics = record.get("metrics") or {}
    values = [metrics.get(key, 0) for key in METRIC_SORT_PRIORITY if isinstance(metrics.get(key), int)]
    return max(values) if values else 0


def _atlas_stats(evidence: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Point-in-time attention statistics for the evidence atlas.

    These are the values the sources exposed at collection time. They are
    attention signals, not measurements of model behaviour, and they are never
    normalised into a single composite score.
    """
    dates = sorted({str(record["collected_at"]) for record in evidence if record.get("collected_at")})
    metric_records = sum(1 for record in evidence if record.get("metrics"))
    metric_totals: Dict[str, int] = {}
    for record in evidence:
        for key, value in (record.get("metrics") or {}).items():
            metric_totals[key] = metric_totals.get(key, 0) + value
    source_types: Dict[str, int] = {}
    for record in evidence:
        source_type = record.get("source_type") or "unknown"
        source_types[source_type] = source_types.get(source_type, 0) + 1
    return {
        "records": len(evidence),
        "classes_covered": sum(1 for cls in CLASSES if any(record["class"] == cls for record in evidence)),
        "metric_records": metric_records,
        "metric_totals": metric_totals,
        "source_types": source_types,
        "snapshot_dates": dates,
    }


def _metric_totals_text(metric_totals: Dict[str, int]) -> str:
    parts = []
    for key in METRIC_SORT_PRIORITY:
        if key in metric_totals:
            parts.append(f"{_fmt_int(metric_totals[key])} {METRIC_LABELS.get(key, key).lower()}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _status_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"probes": len(rows), "pass": 0, "fail": 0, "error": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def _class_stats(
    rows: Sequence[Dict[str, Any]],
    evidence: Sequence[Dict[str, Any]],
    corpus: Sequence[Dict[str, Any]],
    warnings: List[str],
    results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    per_class: List[Dict[str, Any]] = []
    evidence_counts: Dict[str, int] = {}
    for record in evidence:
        evidence_counts[record["class"]] = evidence_counts.get(record["class"], 0) + 1
    corpus_counts: Dict[str, int] = {}
    for record in corpus:
        cls = record.get("class")
        if isinstance(cls, str):
            corpus_counts[cls] = corpus_counts.get(cls, 0) + 1

    reported = results.get("by_class")
    if not isinstance(reported, dict):
        reported = {}
    for cls in CLASSES:
        cls_rows = [row for row in rows if row["class"] == cls]
        counts = _status_counts(cls_rows)
        entry = {
            "name": cls,
            "abbr": CLASSES[cls],
            "label": CLASS_LABELS.get(cls, cls),
            "total": counts["probes"],
            "pass": counts["pass"],
            "fail": counts["fail"],
            "error": counts["error"],
            "pass_rate": _ratio(counts["pass"], counts["probes"]),
            "evidence_count": evidence_counts.get(cls, 0),
            "corpus_count": corpus_counts.get(cls, 0),
        }
        per_class.append(entry)
        reported_entry = reported.get(cls)
        if isinstance(reported_entry, dict):
            expected = reported_entry.get("total")
            if isinstance(expected, int) and expected != entry["total"]:
                _warn(
                    warnings,
                    f"results.by_class[{cls}].total={expected} disagrees with "
                    f"{entry['total']} probe rows; recomputed values are shown.",
                )
    return per_class


def _severity_stats(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    stats: Dict[str, Dict[str, Any]] = {
        severity: {"severity": severity, "weight": weight, "total": 0, "pass": 0, "fail": 0, "error": 0}
        for severity, weight in SEVERITY_WEIGHTS.items()
    }
    unknown = 0
    for row in rows:
        severity = row["severity"]
        if severity not in stats:
            unknown += 1
            continue
        entry = stats[severity]
        entry["total"] += 1
        entry[row["status"]] = entry.get(row["status"], 0) + 1
    for entry in stats.values():
        entry["pass_rate"] = _ratio(entry["pass"], entry["total"])
    weighted_num = sum(entry["weight"] * entry["pass"] for entry in stats.values())
    weighted_den = sum(entry["weight"] * entry["total"] for entry in stats.values())
    total = sum(entry["total"] for entry in stats.values())
    passed = sum(entry["pass"] for entry in stats.values())
    return {
        "weights": dict(SEVERITY_WEIGHTS),
        "rows": list(stats.values()),
        "unknown": unknown,
        "weighted_pass_rate": round(weighted_num / weighted_den, 4) if weighted_den else None,
        "unweighted_pass_rate": _ratio(passed, total),
        "total": total,
        "pass": passed,
    }


def _corpus_summary(corpus: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: List[Dict[str, Any]] = []
    total = 0
    for cls in CLASSES:
        records = [record for record in corpus if record.get("class") == cls]
        total += len(records)
        severities = {severity: 0 for severity in SEVERITY_ORDER}
        titles: List[str] = []
        sorted_records = sorted(
            records,
            key=lambda record: (_severity_rank(str(record.get("severity"))), str(record.get("id"))),
        )
        for record in sorted_records:
            severity = record.get("severity")
            if severity in severities:
                severities[severity] += 1
            title = record.get("title")
            if isinstance(title, str) and title:
                titles.append(title)
        by_class.append(
            {
                "class": cls,
                "abbr": CLASSES[cls],
                "label": CLASS_LABELS.get(cls, cls),
                "count": len(records),
                "severities": severities,
                "examples": titles[:3],
            }
        )
    return {"total": total, "by_class": by_class}


# ---------------------------------------------------------------------------
# Build the embedded data payload
# ---------------------------------------------------------------------------


def _build_payload(
    results: Dict[str, Any],
    results_file: Path,
    rows: Sequence[Dict[str, Any]],
    evidence: Sequence[Dict[str, Any]],
    corpus: Sequence[Dict[str, Any]],
    warnings: List[str],
) -> Dict[str, Any]:
    provider = str(results.get("provider") or "unknown")
    run_id = str(results.get("run_id") or "")
    lowered = f"{provider} {run_id}".lower()
    is_mock = provider.lower() == "mock"
    is_fixture = ("fixture" in lowered) or provider.lower() in ("fixture", "synthetic")
    is_demo = is_mock or is_fixture or ("demo" in run_id.lower())
    counts = _status_counts(rows)
    severity = _severity_stats(rows)
    classes = _class_stats(rows, evidence, corpus, warnings, results)
    payload = {
        "schema": 1,
        "generated_at": _now_iso(),
        "generator": f"failbench report {VERSION}",
        "build": {
            "run_id": run_id,
            "provider": provider,
            "model": str(results.get("model") or ""),
            "base_url": results.get("base_url"),
            "suite_version": str(results.get("suite_version") or ""),
            "started_at": results.get("started_at"),
            "finished_at": results.get("finished_at"),
            "environment": results.get("environment") if isinstance(results.get("environment"), dict) else {},
            "config": results.get("config") if isinstance(results.get("config"), dict) else {},
            "is_demo": is_demo,
            "is_mock": is_mock,
            "is_fixture": is_fixture,
            "results_file": str(results_file),
            "warnings": list(warnings),
        },
        "counts": {
            **counts,
            "classes": sum(1 for entry in classes if entry["total"] > 0),
            "evidence": len(evidence),
            "evidence_cited": sum(1 for record in evidence if record["status"] == "cited"),
            "probe_corpus": len(corpus),
        },
        "pass_rate": _ratio(counts["pass"], counts["probes"]),
        "severity": severity,
        "classes": classes,
        "probes": [
            {
                "id": row["id"],
                "class": row["class"],
                "class_label": row["class_label"],
                "abbr": row["abbr"],
                "title": row["title"],
                "severity": row["severity"],
                "status": row["status"],
                "reason": row["reason"],
                "latency_ms": row["latency_ms"],
                "tokens": row["tokens"],
                "response_excerpt": row["response_excerpt"],
                "rationale": row["rationale"],
                "tags": row["tags"],
                "scoring_type": row["scoring_type"],
                "evidence_ids": row["evidence_ids"],
                "attempts": row["attempts"],
            }
            for row in rows
        ],
        "evidence": [
            {
                "id": record["id"],
                "class": record["class"],
                "class_label": record["class_label"],
                "abbr": record["abbr"],
                "title": record["title"],
                "source_type": record["source_type"],
                "source_url": record["source_url"],
                "source_title": record["source_title"],
                "publisher": record["publisher"],
                "published_date": record["published_date"],
                "metrics": record["metrics"],
                "quote": record["quote"],
                "summary": record["summary"],
                "status": record["status"],
                "probe_ids": record["probe_ids"],
                "collected_by": record["collected_by"],
                "collected_at": record["collected_at"],
            }
            for record in evidence
        ],
        "probe_corpus": _corpus_summary(corpus),
        "atlas": _atlas_stats(evidence),
    }
    return payload


# ---------------------------------------------------------------------------
# HTML fragments
# ---------------------------------------------------------------------------

_CSS = r"""/* ==========================================================================
   FailBench static report — stylesheet
   --------------------------------------------------------------------------
   GENERATOR INPUT: failbench/report.py reads this file verbatim and inlines it
   as the entire contents of the report page's single <style> element, keeping
   the page fully self-contained. System font stacks only: no CSS imports, no
   external fonts, no images, no remote asset references.
   Sections: tokens, dark theme, base, accessibility, layout, hero, controls,
   content, code, results, tables, atlas, footer, responsive, print.
   ========================================================================== */

/* 01. Tokens — typography, layout, radii, light palette -------------------- */
:root {
  color-scheme: light;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "Cascadia Code", "Segoe UI Mono", Consolas, "Liberation Mono", monospace;
  --fs-xs: 0.75rem; --fs-sm: 0.875rem; --fs-md: 1rem; --fs-lg: 1.125rem;
  --max-width: 1120px; --gutter: 24px; --header-h: 60px; --section-gap: 4rem;
  --radius-sm: 6px; --radius: 10px; --radius-lg: 16px; --radius-pill: 999px;
  --shadow-sm: 0 1px 2px rgba(16, 24, 40, 0.05);
  --shadow: 0 1px 3px rgba(16, 24, 40, 0.06), 0 12px 28px rgba(16, 24, 40, 0.07);

  /* Light palette. */
  --bg: #ffffff;
  --surface: #ffffff;
  --text: #15171c;
  --text-2: #475467;
  --text-3: #5d6b7e;
  --border: #e4e7ec;
  --border-strong: #d0d5dd;
  --accent: #4f46e5;
  --accent-hover: #4338ca;
  --accent-contrast: #ffffff;
  --pass: #067647;
  --fail: #b42318;
  --warn: #b54708;
  --info: #175cd3;
  --sev-medium: #a15c07;

  /* Tints and neutrals derived from the active palette (resolve per theme). */
  --accent-soft: color-mix(in srgb, var(--accent) 12%, transparent);
  --hero-glow: color-mix(in srgb, var(--accent) 11%, transparent);
  --header-bg: color-mix(in srgb, var(--bg) 86%, transparent);
  --selection: color-mix(in srgb, var(--accent) 22%, transparent);
  --focus-ring: color-mix(in srgb, var(--accent) 50%, transparent);
  --surface-2: color-mix(in srgb, var(--text) 4%, var(--bg));
  --thead-bg: color-mix(in srgb, var(--text) 3%, var(--bg));
  --row-hover: color-mix(in srgb, var(--text) 2.5%, var(--bg));
  --code-bg: color-mix(in srgb, var(--text) 4.5%, var(--bg));
  --code-head-bg: color-mix(in srgb, var(--text) 7%, var(--bg));
  --inline-code-bg: color-mix(in srgb, var(--text) 6%, var(--bg));
  --chart-track: color-mix(in srgb, var(--text) 9%, var(--bg));
  --scroll-thumb: color-mix(in srgb, var(--text) 22%, var(--bg));

  /* Semantic aliases share one source of truth. */
  --sev-critical: var(--fail); --sev-high: var(--warn); --sev-low: var(--text-3);
  --chart-bar: var(--accent); --chart-pass: var(--pass); --chart-fail: var(--fail);
}

/* 02. Dark theme — OS preference, then the explicit data-theme override ---- */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #0a0d13; --surface: #10141b; --text: #e9edf4;
    --text-2: #a7b0c0; --text-3: #818b9c;
    --border: #232a36; --border-strong: #333c4b;
    --accent: #97a6ff; --accent-hover: #b3beff; --accent-contrast: #0a0d13;
    --pass: #6ce9a6; --fail: #fda29b; --warn: #fec84b; --info: #84caff; --sev-medium: #fec84b;
  }
}

/* The explicit toggle wins: higher specificity than the media rule above, and
   that media rule is skipped entirely when data-theme="light" is set. */
html[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0a0d13; --surface: #10141b; --text: #e9edf4;
  --text-2: #a7b0c0; --text-3: #818b9c;
  --border: #232a36; --border-strong: #333c4b;
  --accent: #97a6ff; --accent-hover: #b3beff; --accent-contrast: #0a0d13;
  --pass: #6ce9a6; --fail: #fda29b; --warn: #fec84b; --info: #84caff; --sev-medium: #fec84b;
}

/* Light tokens already live on :root; this only pins the browser UI scheme. */
html[data-theme="light"] { color-scheme: light; }

/* 03. Base / reset --------------------------------------------------------- */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; overflow-x: clip; }
html, body { margin: 0; }
main { display: block; }
body {
  min-height: 100vh; background: var(--bg); color: var(--text);
  font-family: var(--font-sans); font-size: var(--fs-md); line-height: 1.6;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
  overflow-wrap: break-word; accent-color: var(--accent);
}
h1, h2, h3, h4 {
  margin: 0 0 0.5em; font-weight: 600; line-height: 1.2; letter-spacing: -0.02em;
  color: var(--text); text-wrap: balance;
}
h1 { font-weight: 700; }
p, ul, ol, dl, blockquote { margin: 0 0 1em; }
ul, ol { padding-left: 1.3em; }
a { color: var(--accent); text-decoration: none; text-underline-offset: 2px; }
a:hover { text-decoration: underline; }
code, kbd, samp, pre { font-family: var(--font-mono); }
code { font-size: 0.875em; }
:not(pre) > code {
  padding: 0.12em 0.36em; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--inline-code-bg); color: var(--text); word-break: break-word;
}
img, svg, video { max-width: 100%; }
hr { margin: 2rem 0; border: 0; border-top: 1px solid var(--border); }
::selection { background: var(--selection); color: var(--text); }
[id] { scroll-margin-top: calc(var(--header-h) + 20px); }

/* 04. Accessibility utilities --------------------------------------------- */
.skip-link {
  position: fixed; left: 16px; top: -4rem; z-index: 200;
  padding: 0.6rem 1rem; border-radius: var(--radius);
  background: var(--accent); color: var(--accent-contrast);
  box-shadow: var(--shadow); font-size: var(--fs-sm); font-weight: 600;
  text-decoration: none; transition: top 0.15s ease-in-out;
}
.skip-link:focus { top: 0.75rem; text-decoration: none; }
.visually-hidden, .sr-only {
  position: absolute !important; width: 1px !important; height: 1px !important;
  margin: -1px !important; padding: 0 !important; overflow: hidden !important;
  clip: rect(0 0 0 0) !important; clip-path: inset(50%) !important;
  white-space: nowrap !important; border: 0 !important;
}
[hidden] { display: none !important; }
:where(a, button, input, select, textarea, summary, [tabindex]):focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
  border-radius: var(--radius-sm); box-shadow: 0 0 0 4px var(--focus-ring);
}

/* 05. Layout --------------------------------------------------------------- */
.wrap { width: 100%; max-width: var(--max-width); margin-inline: auto; padding-inline: var(--gutter); }
.section { padding-block: var(--section-gap); }
.section + .section { border-top: 1px solid var(--border); }
.section-head { max-width: 70ch; margin-bottom: 2rem; }
.section-head h2 { margin: 0 0 0.6rem; font-size: clamp(1.5rem, 2.6vw, 2rem); letter-spacing: -0.03em; }
.section-lede { margin: 0; color: var(--text-2); font-size: var(--fs-lg); line-height: 1.6; }
.mono { font-family: var(--font-mono); font-size: 0.875em; }
.eyebrow, .kicker {
  display: inline-flex; align-items: center; gap: 0.5rem; margin: 0;
  color: var(--text-3); font-size: var(--fs-xs); font-weight: 600;
  letter-spacing: 0.12em; text-transform: uppercase;
}
.kicker { color: var(--accent); }
.eyebrow .dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--pass);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pass) 22%, transparent);
}

/* 06. Hero ----------------------------------------------------------------- */
.hero {
  padding-block: clamp(3rem, 7vw, 5.5rem) clamp(2.5rem, 5vw, 4rem);
  border-bottom: 1px solid var(--border);
  background: radial-gradient(80% 130% at 12% -10%, var(--hero-glow), transparent 62%), var(--bg);
}
.hero-inner { display: grid; gap: 1.25rem; max-width: 60rem; }
.hero-title { margin: 0; font-size: clamp(2rem, 5.2vw, 3.25rem); line-height: 1.06; letter-spacing: -0.035em; }
.hero-tagline {
  margin: 0; color: var(--text); font-size: clamp(1.0625rem, 2.2vw, 1.375rem);
  font-weight: 600; letter-spacing: -0.01em;
}
.hero-lede { max-width: 46rem; margin: 0; color: var(--text-2); font-size: var(--fs-lg); line-height: 1.65; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.5rem; }
.hero-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 1.5rem; }
.stat-card {
  padding: 1rem 1.15rem; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow-sm);
}
.stat-value {
  display: block; color: var(--text); font-family: var(--font-mono);
  font-size: clamp(1.3rem, 2.4vw, 1.65rem); font-weight: 600;
  font-variant-numeric: tabular-nums; line-height: 1.15; letter-spacing: -0.03em;
}
.stat-label {
  display: block; margin-top: 0.3rem; color: var(--text-3); font-size: var(--fs-xs);
  font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase;
}

/* 07. Buttons, copy controls, notes --------------------------------------- */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem;
  min-height: 40px; padding: 0.55rem 1.15rem;
  border: 1px solid transparent; border-radius: var(--radius-sm);
  font: inherit; font-size: var(--fs-sm); font-weight: 600; line-height: 1.2;
  text-decoration: none; cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
}
.btn:hover { text-decoration: none; }
.btn-primary { background: var(--accent); color: var(--accent-contrast); box-shadow: var(--shadow-sm); }
.btn-primary:hover { background: var(--accent-hover); }
.btn-primary:active { transform: translateY(1px); }
.btn-ghost { border-color: var(--border-strong); background: transparent; color: var(--text); }
.btn-ghost:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }
.btn-small, .copy-btn, [data-copy] {
  display: inline-flex; align-items: center; justify-content: center; gap: 0.3rem;
  min-height: 28px; padding: 0.2rem 0.6rem;
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--text-2);
  font-family: var(--font-sans); font-size: var(--fs-xs); font-weight: 600; line-height: 1.4;
  text-decoration: none; white-space: nowrap; cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.copy-btn:hover, .btn-small:hover, [data-copy]:hover {
  border-color: var(--accent); background: var(--accent-soft); color: var(--accent); text-decoration: none;
}
.copy-btn:active, .btn-small:active { transform: translateY(1px); }
.link-btn {
  display: inline; padding: 0; border: 0; background: none; color: var(--accent);
  font: inherit; font-size: var(--fs-sm); font-weight: 500;
  text-decoration: underline; text-underline-offset: 2px; cursor: pointer;
}
.link-btn:hover { color: var(--accent-hover); }
.note {
  padding: 1rem 1.15rem; border: 1px solid var(--border);
  border-left: 3px solid var(--text-3); border-radius: var(--radius);
  background: var(--surface-2); color: var(--text-2); font-size: var(--fs-sm);
}
.note > :last-child { margin-bottom: 0; }
.note strong { color: var(--text); }
.note-demo { border-left-color: var(--warn); background: color-mix(in srgb, var(--warn) 9%, var(--bg)); }
.note-info { border-left-color: var(--info); background: color-mix(in srgb, var(--info) 8%, var(--bg)); }
.note-warn { border-left-color: var(--fail); background: color-mix(in srgb, var(--fail) 8%, var(--bg)); }

/* 08. Header and navigation ------------------------------------------------ */
.site-header {
  position: sticky; top: 0; z-index: 100;
  border-bottom: 1px solid var(--border); background: var(--header-bg);
  -webkit-backdrop-filter: blur(14px) saturate(1.4);
  backdrop-filter: blur(14px) saturate(1.4);
}
.header-inner {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem 1.25rem;
  min-height: var(--header-h); padding-block: 0.5rem;
}
.brand {
  display: inline-flex; align-items: center; gap: 0.6rem; color: var(--text);
  font-size: 1.0625rem; font-weight: 700; letter-spacing: -0.02em; text-decoration: none;
}
.brand:hover { color: var(--accent); text-decoration: none; }
.brand-mark {
  display: grid; place-items: center; width: 30px; height: 30px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--info)));
  color: var(--accent-contrast); box-shadow: var(--shadow-sm);
  font-family: var(--font-mono); font-size: 0.6875rem; font-weight: 700; letter-spacing: -0.03em;
}
.brand-name { white-space: nowrap; }
.nav { margin-left: auto; }
.nav-list {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem 1.25rem;
  margin: 0; padding: 0; list-style: none;
}
.nav-list a {
  display: inline-block; padding: 0.35rem 0; border-bottom: 2px solid transparent;
  color: var(--text-2); font-size: var(--fs-sm); font-weight: 500; text-decoration: none;
}
.nav-list a:hover, .nav-list a[aria-current="page"] {
  border-bottom-color: var(--accent); color: var(--text); text-decoration: none;
}
.theme-toggle {
  display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem;
  min-height: 32px; padding: 0.25rem 0.7rem;
  border: 1px solid var(--border-strong); border-radius: var(--radius-pill);
  background: var(--surface); color: var(--text-2);
  font: inherit; font-size: var(--fs-xs); font-weight: 600; cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.theme-toggle:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); }

/* 09. Content blocks: cards, steps, prose, method, threats ----------------- */
.cards-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
.card {
  padding: 1.35rem; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow-sm);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.card:hover { border-color: var(--border-strong); box-shadow: var(--shadow); transform: translateY(-2px); }
.card h3 { margin: 0 0 0.5rem; font-size: 1.0625rem; }
.card p, .card ul { margin: 0; color: var(--text-2); font-size: var(--fs-sm); }
.card ul { margin-top: 0.5rem; padding-left: 1.1rem; }
.steps {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem;
  margin: 0; padding: 0; list-style: none; counter-reset: step;
}
.step {
  position: relative; padding: 1.25rem 1.25rem 1.25rem 3.4rem;
  border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface);
}
.step::before {
  counter-increment: step; content: counter(step); position: absolute;
  left: 1.15rem; top: 1.15rem; display: grid; place-items: center;
  width: 1.65rem; height: 1.65rem; border-radius: 50%;
  background: var(--accent-soft); color: var(--accent);
  font-family: var(--font-mono); font-size: 0.75rem; font-weight: 600;
}
.step h3 { margin: 0 0 0.35rem; font-size: 1rem; }
.step p { margin: 0; color: var(--text-2); font-size: var(--fs-sm); }
.prose { max-width: 72ch; color: var(--text-2); }
.prose > :last-child { margin-bottom: 0; }
.prose p, .prose li { line-height: 1.7; }
.prose strong { color: var(--text); font-weight: 600; }
.prose h2, .prose h3 { margin-top: 1.6em; margin-bottom: 0.5em; color: var(--text); }
.prose li + li { margin-top: 0.35rem; }
.method-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.25rem 2rem; }
.method-grid > * {
  padding: 1.25rem; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface);
}
.threat-list { display: grid; gap: 0.75rem; margin: 0; padding: 0; list-style: none; }
.threat-list > li {
  padding: 0.9rem 1.1rem; border: 1px solid var(--border);
  border-left: 3px solid var(--fail); border-radius: var(--radius);
  background: var(--surface); color: var(--text-2); font-size: var(--fs-sm);
}
.threat-list > li strong { color: var(--text); }

/* 10. Code blocks, excerpts, citations ------------------------------------ */
.code-block { overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); background: var(--code-bg); }
.code-head {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0.45rem 0.75rem; border-bottom: 1px solid var(--border);
  background: var(--code-head-bg); color: var(--text-3);
  font-family: var(--font-mono); font-size: var(--fs-xs); letter-spacing: 0.02em;
}
.code-head span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.code-head .copy-btn { flex: none; }
pre {
  max-width: 100%; margin: 0; padding: 1rem 1.15rem;
  overflow-x: auto; background: var(--code-bg); color: var(--text);
  font-size: 0.8125rem; line-height: 1.7; tab-size: 2;
  -webkit-overflow-scrolling: touch;
}
pre code { padding: 0; border: 0; background: none; color: inherit; font-size: inherit; white-space: pre; }
pre.excerpt, .excerpt { border: 1px solid var(--border); border-radius: var(--radius); background: var(--code-bg); }
.excerpt { max-height: 20rem; overflow: auto; }
.excerpt pre { border: 0; border-radius: 0; background: transparent; max-height: none; }
pre.bibtex, .bibtex {
  padding: 0.9rem 1rem; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--code-bg); color: var(--text-2); font-size: 0.78125rem; line-height: 1.6;
  white-space: pre-wrap; word-break: break-word;
}
.citation-box {
  position: relative; padding: 1.1rem 1.2rem; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface);
}
.citation-box .copy-btn { position: absolute; top: 0.7rem; right: 0.7rem; }
.citation-box .bibtex { margin: 0; padding-right: 4.5rem; }

/* 11. Results: stat strip, chart panel, legend ---------------------------- */
.stat-strip {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px;
  overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); background: var(--border);
}
.stat { padding: 1rem 1.15rem; background: var(--surface); }
.stat-pass .stat-value { color: var(--pass); }
.stat-fail .stat-value { color: var(--fail); }
.stat-error .stat-value { color: var(--warn); }
.chart-panel {
  padding: 1.25rem 1.35rem; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow-sm);
}
.chart { width: 100%; overflow-x: auto; }
.bar-chart { display: block; width: 100%; min-width: 420px; height: auto; font-family: var(--font-sans); }
.bar-chart .bar-label { fill: var(--text-2); font-size: 12px; font-weight: 600; }
.bar-chart .bar-track { fill: var(--chart-track); }
.bar-chart .bar-fill { fill: var(--chart-bar); transition: opacity 0.15s ease; }
.bar-chart .bar-fill-pass { fill: var(--chart-pass); }
.bar-chart .bar-fill-fail { fill: var(--chart-fail); }
.bar-chart .bar-value { fill: var(--text-3); font-family: var(--font-mono); font-size: 11px; font-weight: 600; }
.bar-chart g.bar-row:hover .bar-fill, .bar-chart g.bar-row:hover .bar-fill-pass { opacity: 0.82; }
.chart-legend {
  display: flex; flex-wrap: wrap; gap: 0.4rem 1.25rem; margin: 1rem 0 0;
  padding: 0; list-style: none; color: var(--text-2); font-size: var(--fs-sm);
}
.legend-item { display: inline-flex; align-items: center; gap: 0.45rem; }
.legend-item::before { content: ""; width: 10px; height: 10px; border-radius: 3px; background: var(--legend-color, var(--accent)); }
.legend-pass { --legend-color: var(--chart-pass); }
.legend-fail { --legend-color: var(--chart-fail); }

/* 12. Toolbar / filter fields --------------------------------------------- */
.toolbar { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 0.75rem 1rem; margin: 1.25rem 0 1rem; }
.field { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
.field label, .field > span {
  color: var(--text-3); font-size: var(--fs-xs); font-weight: 600;
  letter-spacing: 0.06em; text-transform: uppercase;
}
.field :is(select, input) {
  min-height: 36px; padding: 0.4rem 0.65rem;
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--text); font: inherit; font-size: var(--fs-sm);
}
.field :is(select, input):focus-visible { border-color: var(--accent); }
.field-search { flex: 1 1 220px; max-width: 26rem; }
.field-search input { width: 100%; }
.toolbar-count {
  margin-left: auto; align-self: center; color: var(--text-3);
  font-family: var(--font-mono); font-size: var(--fs-xs);
  font-variant-numeric: tabular-nums; white-space: nowrap;
}

/* 13. Data tables ---------------------------------------------------------- */
.table-wrap {
  overflow-x: auto; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface); -webkit-overflow-scrolling: touch;
}
.table { width: 100%; min-width: 680px; border-collapse: collapse; font-size: var(--fs-sm); }
.table thead th {
  position: sticky; top: 0; z-index: 1; padding: 0.7rem 0.85rem;
  border-bottom: 1px solid var(--border); background: var(--thead-bg);
  color: var(--text-3); font-size: var(--fs-xs); font-weight: 600;
  letter-spacing: 0.07em; text-align: left; text-transform: uppercase; white-space: nowrap;
}
.table tbody td { padding: 0.7rem 0.85rem; border-top: 1px solid var(--border); vertical-align: middle; }
.table tbody tr:first-child td { border-top: 0; }
.table tbody tr.result-row { transition: background-color 0.12s ease; }
.table tbody tr.result-row:hover { background: var(--row-hover); }
.result-row[data-status="pass"] td:first-child { box-shadow: inset 3px 0 0 var(--pass); }
.result-row[data-status="fail"] td:first-child { box-shadow: inset 3px 0 0 var(--fail); }
.result-row[data-status="error"] td:first-child { box-shadow: inset 3px 0 0 var(--warn); }
.cell-probe { min-width: 220px; }
.probe-id { display: block; color: var(--text-3); font-family: var(--font-mono); font-size: var(--fs-xs); }
.probe-title { display: block; color: var(--text); font-weight: 500; }
.cell-class, .cell-severity, .cell-status, .cell-toggle { white-space: nowrap; }
.cell-latency {
  color: var(--text-2); font-family: var(--font-mono); font-size: var(--fs-xs);
  font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap;
}
.cell-toggle { width: 1%; text-align: right; }
.row-toggle {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; padding: 0;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--text-2);
  font: inherit; font-size: var(--fs-xs); cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.row-toggle:hover, .row-toggle[aria-expanded="true"] {
  border-color: var(--accent); background: var(--accent-soft); color: var(--accent);
}
.table-corpus { min-width: 560px; }

/* 14. Tags, badges, status pills, severity chips -------------------------- */
.tag, .badge {
  display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.12rem 0.45rem;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface-2); color: var(--text-2);
  font-size: var(--fs-xs); line-height: 1.5; white-space: nowrap;
}
.tag { font-family: var(--font-mono); }
.badge { border-radius: var(--radius-pill); font-weight: 600; }
.tag-class { border-color: color-mix(in srgb, var(--accent) 30%, transparent); background: var(--accent-soft); color: var(--accent); }
.tag-source { font-size: 0.6875rem; letter-spacing: 0.04em; text-transform: uppercase; }
.tag-muted { border-style: dashed; background: transparent; color: var(--text-3); }
.tag-label { color: var(--text-3); font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.status {
  display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.12rem 0.5rem;
  border-radius: var(--radius-pill); background: var(--surface-2); color: var(--text-2);
  font-size: var(--fs-xs); font-weight: 600; line-height: 1.6; white-space: nowrap;
}
.status::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-pass { background: color-mix(in srgb, var(--pass) 13%, transparent); color: var(--pass); }
.status-fail { background: color-mix(in srgb, var(--fail) 13%, transparent); color: var(--fail); }
.status-error { background: color-mix(in srgb, var(--warn) 13%, transparent); color: var(--warn); }
.sev {
  display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.1rem 0.45rem;
  border: 1px solid transparent; border-radius: var(--radius-sm);
  font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.05em;
  line-height: 1.6; text-transform: uppercase; white-space: nowrap;
}
.sev::before { content: ""; width: 6px; height: 6px; border-radius: 2px; background: currentColor; }
.sev-critical { border-color: color-mix(in srgb, var(--sev-critical) 28%, transparent); background: color-mix(in srgb, var(--sev-critical) 10%, transparent); color: var(--sev-critical); }
.sev-high { border-color: color-mix(in srgb, var(--sev-high) 28%, transparent); background: color-mix(in srgb, var(--sev-high) 10%, transparent); color: var(--sev-high); }
.sev-medium { border-color: color-mix(in srgb, var(--sev-medium) 30%, transparent); background: color-mix(in srgb, var(--sev-medium) 10%, transparent); color: var(--sev-medium); }
.sev-low { border-color: var(--border); background: transparent; color: var(--sev-low); }
.severity-mini { display: inline-flex; gap: 0.35rem; color: var(--text-3); font-family: var(--font-mono); font-size: var(--fs-xs); }

/* 15. Result detail rows, attempts, empty state --------------------------- */
.table tbody tr.result-detail > td {
  padding: 1.1rem 1.25rem 1.35rem; border-top: 1px solid var(--border); background: var(--surface-2);
}
.detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem 1.5rem; }
.detail-block h4 { margin: 0 0 0.4rem; color: var(--text-3); font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; }
.detail-block p { margin: 0; color: var(--text-2); font-size: var(--fs-sm); }
.detail-block pre {
  max-height: 16rem; padding: 0.8rem 0.9rem;
  border: 1px solid var(--border); border-radius: var(--radius-sm); font-size: 0.78125rem;
}
.detail-list { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.35rem 0.9rem; margin: 0; font-size: var(--fs-sm); }
.detail-list dt { color: var(--text-3); font-weight: 600; }
.detail-list dd { margin: 0; color: var(--text-2); overflow-wrap: anywhere; }
.attempts { display: grid; gap: 0.4rem; margin: 0; padding: 0; list-style: none; }
.attempts li {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem;
  padding: 0.5rem 0.6rem; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--surface);
  color: var(--text-2); font-size: var(--fs-xs);
}
.empty-state {
  padding: 3rem 1.5rem; border: 1px dashed var(--border-strong); border-radius: var(--radius);
  background: var(--surface-2); color: var(--text-3); text-align: center;
}
.empty-state p { margin: 0; }
.empty-state strong { color: var(--text-2); }

/* 16. Atlas cards ---------------------------------------------------------- */
.atlas-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
.atlas-card {
  display: flex; flex-direction: column; gap: 0.65rem; padding: 1.25rem;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); box-shadow: var(--shadow-sm);
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
.atlas-card:hover, .atlas-card:focus-within { border-color: var(--border-strong); box-shadow: var(--shadow); transform: translateY(-2px); }
.atlas-card-head { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; }
.atlas-title { margin: 0; font-size: 1.0625rem; line-height: 1.35; letter-spacing: -0.01em; }
.atlas-title a { color: var(--text); text-decoration: none; }
.atlas-title a:hover { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
.atlas-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.3rem 0.75rem; color: var(--text-3); font-family: var(--font-mono); font-size: var(--fs-xs); }
.atlas-summary { margin: 0; color: var(--text-2); font-size: var(--fs-sm); line-height: 1.65; }
.atlas-quote {
  margin: 0.2rem 0 0; padding: 0.1rem 0 0.1rem 0.9rem;
  border-left: 3px solid color-mix(in srgb, var(--accent) 45%, transparent);
  color: var(--text-2); font-size: var(--fs-sm); font-style: italic;
}
.atlas-quote p { margin: 0; }
.atlas-quote cite { display: block; margin-top: 0.35rem; color: var(--text-3); font-size: var(--fs-xs); font-style: normal; }
.atlas-metrics { display: flex; flex-wrap: wrap; gap: 0.4rem 1.25rem; margin: auto 0 0; padding-top: 0.35rem; }
.metric { display: flex; flex-direction: column; gap: 0.1rem; color: var(--text-3); font-size: var(--fs-xs); }
.metric strong { color: var(--text); font-family: var(--font-mono); font-size: 1.0625rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.atlas-probes { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0; padding-top: 0.6rem; border-top: 1px dashed var(--border); }
.atlas-probes code { font-size: 0.6875rem; }

/* 17. Footer, plain lists, table of contents, scrollbars ----------------- */
.plain-list { display: grid; gap: 0.4rem; margin: 0; padding: 0; list-style: none; }
.toc { position: sticky; top: calc(var(--header-h) + 1rem); max-width: 18rem; font-size: var(--fs-sm); }
.toc ul { margin: 0; padding-left: 1rem; }
.toc a { color: var(--text-2); text-decoration: none; }
.toc a:hover { color: var(--accent); text-decoration: underline; }
.site-footer { margin-top: var(--section-gap); border-top: 1px solid var(--border); background: var(--surface-2); color: var(--text-2); }
.site-footer > .wrap { padding-block: 2.5rem 1.5rem; }
.footer-grid { display: grid; grid-template-columns: 1.6fr repeat(3, minmax(0, 1fr)); gap: 2rem; }
.footer-col h2, .footer-col h3, .footer-col h4 {
  margin: 0 0 0.6rem; color: var(--text-3); font-size: var(--fs-xs);
  font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
}
.footer-col p { max-width: 36ch; margin: 0 0 0.5rem; font-size: var(--fs-sm); }
.footer-col ul { display: grid; gap: 0.35rem; margin: 0; padding: 0; list-style: none; }
.footer-col a { color: var(--text-2); font-size: var(--fs-sm); text-decoration: none; }
.footer-col a:hover { color: var(--accent); text-decoration: underline; }
.footer-bottom {
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.5rem 1rem;
  margin-top: 2rem; padding-top: 1.25rem; border-top: 1px solid var(--border);
  color: var(--text-3); font-size: var(--fs-xs);
}
.footer-bottom p { margin: 0; }
.footer-bottom a { color: var(--text-3); }
.footer-bottom a:hover { color: var(--accent); }
* { scrollbar-width: thin; scrollbar-color: var(--scroll-thumb) transparent; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  border: 2px solid transparent; border-radius: var(--radius-pill);
  background: var(--scroll-thumb); background-clip: padding-box;
}

/* 18. Responsive ----------------------------------------------------------- */
@media (max-width: 1000px) {
  .cards-3, .steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .footer-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  :root { --gutter: 20px; --section-gap: 3rem; }
  .hero { padding-block: 2.75rem 2.25rem; }
  .hero-title { font-size: clamp(1.75rem, 7vw, 2.5rem); }
  .hero-lede, .section-lede { font-size: var(--fs-md); }
  .cards-3, .steps, .method-grid { grid-template-columns: 1fr; }
  .nav { order: 3; width: 100%; margin-left: 0; overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .nav-list { flex-wrap: nowrap; gap: 1rem; padding-bottom: 0.15rem; }
  .nav-list a { white-space: nowrap; }
  .toolbar-count { margin-left: 0; }
  .theme-toggle { margin-left: auto; }
  .detail-grid { grid-template-columns: 1fr; }
  .footer-grid { gap: 1.5rem; }
}
@media (max-width: 560px) {
  .hero-stats, .stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero-actions .btn { flex: 1 1 auto; }
  .theme-toggle { margin-left: auto; }
  .section-head h2 { font-size: 1.35rem; }
  .footer-grid { grid-template-columns: 1fr; }
  .table { min-width: 560px; }
  pre { font-size: 0.78125rem; }
  .atlas-grid { grid-template-columns: 1fr; }
}

/* 19. Reduced motion ------------------------------------------------------- */
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}

/* 20. Print ---------------------------------------------------------------- */
@page { margin: 16mm 14mm; }

@media print {
  html, body { background: #fff !important; color: #000 !important; font-size: 10.5pt; }
  .wrap { max-width: none; padding-inline: 0; }
  .site-header, .theme-toggle, .toolbar, .skip-link, .copy-btn,
  .btn, .row-toggle, .nav, .hero-actions { display: none !important; }
  .hero { padding: 0 0 14pt; border-bottom: 1px solid #999; background: none !important; }
  .hero-title { font-size: 24pt; }
  .section { padding-block: 14pt; border-top: 1px solid #999; }
  .section-head { margin-bottom: 10pt; }
  .stat-strip, .cards-3, .steps, .method-grid, .atlas-grid { gap: 8pt; }
  .stat-card, .stat, .card, .step, .chart-panel, .code-block, .note,
  .citation-box, .atlas-card, .threat-list > li {
    border-color: #999 !important; background: #fff !important;
    box-shadow: none !important; break-inside: avoid;
  }
  .atlas-card:hover, .card:hover { transform: none; box-shadow: none; }
  h1, h2, h3, h4, p, li, dt, dd, .section-lede, .hero-lede, .hero-tagline,
  .atlas-summary, .prose, .prose strong, .note, .note strong, .empty-state,
  .empty-state strong { color: #000 !important; }
  a { color: #000 !important; text-decoration: underline; }
  a[href^="http"]::after { content: " (" attr(href) ")"; color: #333 !important; font-size: 8.5pt; word-break: break-all; }
  a[href^="#"]::after, .brand::after { content: none; }
  .table-wrap { overflow: visible !important; border: 1px solid #666; }
  .table { min-width: 0; }
  .table thead { display: table-header-group; }
  .table thead th {
    position: static; border-bottom: 1px solid #999;
    background: #f2f2f2 !important; color: #000 !important;
  }
  .table tbody td { border-top: 1px solid #bbb; background: #fff !important; color: #000 !important; }
  .table tbody tr { break-inside: avoid; }
  .table tbody tr:hover, .table tbody tr.result-detail > td { background: #fff !important; }
  .result-row[data-status] td:first-child { box-shadow: none; }
  .tag, .badge, .status, .sev { border: 1px solid #999 !important; background: transparent !important; color: #000 !important; }
  .status::before, .sev::before { background: #555 !important; }
  pre, pre code, .excerpt, .bibtex, .code-block, .citation-box .bibtex {
    border-color: #999 !important; background: #fff !important;
    color: #000 !important; white-space: pre-wrap; word-break: break-word;
  }
  .bar-chart .bar-track { fill: #e6e6e6 !important; }
  .bar-chart .bar-fill, .bar-chart .bar-fill-pass, .bar-chart .bar-fill-fail { fill: #555 !important; }
  .bar-chart .bar-label, .bar-chart .bar-value { fill: #000 !important; }
  .chart { overflow: visible; }
  .site-footer { border-top: 1px solid #999; background: #fff !important; }
  .footer-bottom { border-top: 1px solid #999; }
}
"""

_JS = r"""'use strict';

/*
 * FailBench static report interactions.
 *
 * The report markup and all report data are rendered ahead of time by the
 * Python generator. This file only adds client-side interaction on top of
 * that markup: results/atlas filtering, detail-row expansion, the theme
 * toggle, and copy buttons. It loads no resources, performs no network
 * access, writes no report data, and every feature is inert when its
 * markup is absent.
 */
(function () {
  var THEME_KEY = 'fb-theme';
  var SEARCH_DELAY = 120;
  var COPY_RESET_DELAY = 1500;

  var pendingTimers = {};

  var copyLabels = [];
  var copyTimers = [];

  var themeButton = null;
  var themeLabel = null;
  var themeQuery = null;
  var manualTheme = null;

  /* ---------- safe DOM helpers ---------- */

  function byId(id) {
    return document.getElementById(id);
  }

  function lower(value) {
    return typeof value === 'string' ? value.toLowerCase() : '';
  }

  function normalizeValue(value) {
    return typeof value === 'string' ? value.trim() : '';
  }

  function isUnfilteredValue(value) {
    var normalized = lower(normalizeValue(value));
    return normalized === '' || normalized === 'all' || normalized === 'any';
  }

  function setHidden(element, shouldHide) {
    if (!element) return;
    if (shouldHide) {
      element.hidden = true;
      if (element.classList) element.classList.add('is-hidden');
    } else {
      element.hidden = false;
      if (element.classList) element.classList.remove('is-hidden');
    }
  }

  function updateCount(element, shown, total, noun) {
    if (!element) return;
    element.textContent = 'Showing ' + shown + ' of ' + total + ' ' + noun;
  }

  function readSearchValue(element) {
    if (!element) return '';
    return typeof element.value === 'string' ? element.value : '';
  }

  function readFilterValue(element) {
    if (!element) return '';
    var value = typeof element.value === 'string' ? element.value : '';
    if (isUnfilteredValue(value)) return '';
    return lower(normalizeValue(value));
  }

  function resetSelect(element) {
    if (!element) return;
    var options = element.options;
    if (options) {
      for (var i = 0; i < options.length; i += 1) {
        if (isUnfilteredValue(options[i].value)) {
          element.selectedIndex = i;
          return;
        }
      }
    }
    element.value = '';
  }

  /* ---------- filter matching (pure) ---------- */

  function tokenizeSearch(raw) {
    var text = typeof raw === 'string' ? raw.toLowerCase().trim() : '';
    if (text === '') return [];
    var parts = text.split(/\s+/);
    var tokens = [];
    for (var i = 0; i < parts.length; i += 1) {
      if (parts[i] !== '') tokens.push(parts[i]);
    }
    return tokens;
  }

  function fieldsMatch(fields, filters) {
    if (filters.cls && lower(fields.cls) !== filters.cls) return false;
    if (filters.severity && lower(fields.severity) !== filters.severity) return false;
    if (filters.status && lower(fields.status) !== filters.status) return false;
    if (filters.source && lower(fields.source) !== filters.source) return false;
    var tokens = filters.tokens || [];
    var haystack = lower(fields.search);
    for (var i = 0; i < tokens.length; i += 1) {
      if (haystack.indexOf(tokens[i]) === -1) return false;
    }
    return true;
  }

  function readResultFields(row) {
    return {
      cls: row.getAttribute('data-class') || '',
      severity: row.getAttribute('data-severity') || '',
      status: row.getAttribute('data-status') || '',
      search: row.getAttribute('data-search') || ''
    };
  }

  function readAtlasFields(card) {
    return {
      cls: card.getAttribute('data-class') || '',
      source: card.getAttribute('data-source') || '',
      search: card.getAttribute('data-search') || ''
    };
  }

  function nextDetailRow(row) {
    var next = row.nextElementSibling;
    if (next && next.classList && next.classList.contains('result-detail')) {
      return next;
    }
    return null;
  }

  function detailForRow(row) {
    var detail = nextDetailRow(row);
    if (detail) return detail;
    var toggle = row.querySelector('button.row-toggle');
    if (!toggle) return null;
    var targetId = toggle.getAttribute('aria-controls');
    if (!targetId) return null;
    return byId(targetId);
  }

  /* ---------- debounce helpers ---------- */

  function scheduleApply(key, handler) {
    if (pendingTimers[key]) window.clearTimeout(pendingTimers[key]);
    pendingTimers[key] = window.setTimeout(function () {
      pendingTimers[key] = 0;
      handler();
    }, SEARCH_DELAY);
  }

  function cancelApply(key) {
    if (pendingTimers[key]) {
      window.clearTimeout(pendingTimers[key]);
      pendingTimers[key] = 0;
    }
  }

  function bindChange(ids, handler) {
    for (var i = 0; i < ids.length; i += 1) {
      var element = byId(ids[i]);
      if (element) element.addEventListener('change', handler);
    }
  }

  /* ---------- results filtering ---------- */

  function applyResultsFilters() {
    var body = byId('results-body');
    if (!body) return;
    var filters = {
      cls: readFilterValue(byId('filter-class')),
      severity: readFilterValue(byId('filter-severity')),
      status: readFilterValue(byId('filter-status')),
      tokens: tokenizeSearch(readSearchValue(byId('search-probes')))
    };
    var rows = body.querySelectorAll('tr.result-row');
    var shown = 0;
    for (var i = 0; i < rows.length; i += 1) {
      var row = rows[i];
      var match = fieldsMatch(readResultFields(row), filters);
      if (match) shown += 1;
      setHidden(row, !match);
      if (!match) {
        var detail = detailForRow(row);
        if (detail) setHidden(detail, true);
        var toggle = row.querySelector('button.row-toggle');
        if (toggle) {
          toggle.setAttribute('aria-expanded', 'false');
          toggle.textContent = 'Details';
        }
      }
    }
    updateCount(byId('results-count'), shown, rows.length, 'probes');
    var empty = byId('results-empty');
    if (empty) empty.hidden = shown !== 0;
  }

  function resetResultsFilters() {
    resetSelect(byId('filter-class'));
    resetSelect(byId('filter-severity'));
    resetSelect(byId('filter-status'));
    var search = byId('search-probes');
    if (search) search.value = '';
    cancelApply('results');
    applyResultsFilters();
  }

  function initResultsFilters() {
    var search = byId('search-probes');
    if (search) {
      search.addEventListener('input', function () {
        scheduleApply('results', applyResultsFilters);
      });
    }
    bindChange(['filter-class', 'filter-severity', 'filter-status'], applyResultsFilters);
    var reset = byId('reset-filters');
    if (reset) {
      reset.addEventListener('click', function (event) {
        if (event && typeof event.preventDefault === 'function') event.preventDefault();
        resetResultsFilters();
      });
    }
    var resetInline = byId('reset-filters-inline');
    if (resetInline) {
      resetInline.addEventListener('click', function (event) {
        if (event && typeof event.preventDefault === 'function') event.preventDefault();
        resetResultsFilters();
      });
    }
    applyResultsFilters();
  }

  /* ---------- atlas filtering ---------- */

  function applyAtlasFilters() {
    var grid = byId('atlas-grid');
    if (!grid) return;
    var filters = {
      cls: readFilterValue(byId('filter-atlas-class')),
      source: readFilterValue(byId('filter-atlas-source')),
      tokens: tokenizeSearch(readSearchValue(byId('atlas-search')))
    };
    var cards = grid.querySelectorAll('article.atlas-card');
    var shown = 0;
    for (var i = 0; i < cards.length; i += 1) {
      var card = cards[i];
      var match = fieldsMatch(readAtlasFields(card), filters);
      if (match) shown += 1;
      setHidden(card, !match);
    }
    var groups = grid.querySelectorAll('section.atlas-group');
    for (var g = 0; g < groups.length; g += 1) {
      var groupCards = groups[g].querySelectorAll('article.atlas-card');
      var anyVisible = false;
      for (var c = 0; c < groupCards.length; c += 1) {
        if (!groupCards[c].hidden) {
          anyVisible = true;
          break;
        }
      }
      setHidden(groups[g], !anyVisible);
    }
    updateCount(byId('atlas-count'), shown, cards.length, 'evidence records');
    var empty = byId('atlas-empty');
    if (empty) empty.hidden = shown !== 0;
  }

  function resetAtlasFilters() {
    resetSelect(byId('filter-atlas-class'));
    resetSelect(byId('filter-atlas-source'));
    var search = byId('atlas-search');
    if (search) search.value = '';
    cancelApply('atlas');
    applyAtlasFilters();
  }

  function initAtlasFilters() {
    var search = byId('atlas-search');
    if (search) {
      search.addEventListener('input', function () {
        scheduleApply('atlas', applyAtlasFilters);
      });
    }
    bindChange(['filter-atlas-class', 'filter-atlas-source'], applyAtlasFilters);
    var reset = byId('reset-atlas');
    if (reset) {
      reset.addEventListener('click', function (event) {
        if (event && typeof event.preventDefault === 'function') event.preventDefault();
        resetAtlasFilters();
      });
    }
    applyAtlasFilters();
  }

  /* ---------- detail row expansion ---------- */

  function toggleRowDetail(button) {
    var targetId = button.getAttribute('aria-controls');
    if (!targetId) return;
    var detail = byId(targetId);
    if (!detail) return;
    var expanded = button.getAttribute('aria-expanded') === 'true';
    if (expanded) {
      setHidden(detail, true);
      button.setAttribute('aria-expanded', 'false');
      button.textContent = 'Details';
    } else {
      setHidden(detail, false);
      button.setAttribute('aria-expanded', 'true');
      button.textContent = 'Hide';
    }
  }

  function initRowToggles() {
    var buttons = document.querySelectorAll('button.row-toggle');
    for (var i = 0; i < buttons.length; i += 1) {
      (function (button) {
        button.addEventListener('click', function (event) {
          if (event && typeof event.preventDefault === 'function') event.preventDefault();
          toggleRowDetail(button);
        });
      })(buttons[i]);
    }
  }

  /* ---------- theme toggle ---------- */

  function readStoredTheme() {
    try {
      if (!window.localStorage) return null;
      var stored = window.localStorage.getItem(THEME_KEY);
      if (stored === 'dark' || stored === 'light' || stored === 'auto') return stored;
    } catch (error) {
      return null;
    }
    return null;
  }

  function writeStoredTheme(value) {
    try {
      if (!window.localStorage) return;
      window.localStorage.setItem(THEME_KEY, value);
    } catch (error) {
      return;
    }
  }

  function getThemeQuery() {
    if (themeQuery) return themeQuery;
    try {
      if (typeof window.matchMedia === 'function') {
        themeQuery = window.matchMedia('(prefers-color-scheme: dark)');
      }
    } catch (error) {
      themeQuery = null;
    }
    return themeQuery;
  }

  function prefersDark() {
    var query = getThemeQuery();
    return !!(query && query.matches);
  }

  function htmlThemeAttribute() {
    var root = document.documentElement;
    if (!root) return null;
    var value = root.getAttribute('data-theme');
    if (value === 'dark' || value === 'light') return value;
    return null;
  }

  function effectiveTheme() {
    if (manualTheme === 'dark' || manualTheme === 'light') return manualTheme;
    var attr = htmlThemeAttribute();
    if (attr) return attr;
    return prefersDark() ? 'dark' : 'light';
  }

  function updateThemeButton() {
    if (!themeButton) return;
    var mode = effectiveTheme();
    themeButton.setAttribute('aria-pressed', mode === 'dark' ? 'true' : 'false');
    if (themeLabel) themeLabel.textContent = 'Theme: ' + mode;
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    if (!root) return;
    if (theme === 'dark' || theme === 'light') {
      root.setAttribute('data-theme', theme);
    } else {
      root.removeAttribute('data-theme');
    }
    updateThemeButton();
  }

  function handleThemeToggle() {
    var next = effectiveTheme() === 'dark' ? 'light' : 'dark';
    manualTheme = next;
    applyTheme(next);
    writeStoredTheme(next);
  }

  function watchSystemTheme() {
    var query = getThemeQuery();
    if (!query) return;
    var listener = function () {
      if (manualTheme === 'dark' || manualTheme === 'light') return;
      updateThemeButton();
    };
    try {
      if (typeof query.addEventListener === 'function') {
        query.addEventListener('change', listener);
      } else if (typeof query.addListener === 'function') {
        query.addListener(listener);
      }
    } catch (error) {
      return;
    }
  }

  function initTheme() {
    themeButton = byId('theme-toggle');
    if (themeButton) themeLabel = themeButton.querySelector('.theme-toggle-label');
    var stored = readStoredTheme();
    if (stored === 'dark' || stored === 'light') {
      manualTheme = stored;
      applyTheme(stored);
    } else if (stored === 'auto') {
      manualTheme = 'auto';
      applyTheme('auto');
    } else {
      manualTheme = htmlThemeAttribute();
      updateThemeButton();
    }
    if (themeButton) {
      themeButton.addEventListener('click', function (event) {
        if (event && typeof event.preventDefault === 'function') event.preventDefault();
        handleThemeToggle();
      });
    }
    watchSystemTheme();
  }

  /* ---------- copy buttons ---------- */

  function findEntry(list, element) {
    for (var i = 0; i < list.length; i += 1) {
      if (list[i].el === element) return i;
    }
    return -1;
  }

  function setCopyStatus(message) {
    var status = byId('copy-status');
    if (status) status.textContent = message;
  }

  function markCopied(button) {
    if (!button) return;
    var labelIndex = findEntry(copyLabels, button);
    if (labelIndex === -1) {
      copyLabels.push({ el: button, text: button.textContent });
    }
    button.textContent = 'Copied';
    var timerIndex = findEntry(copyTimers, button);
    if (timerIndex === -1) {
      copyTimers.push({ el: button, id: 0 });
      timerIndex = copyTimers.length - 1;
    } else {
      window.clearTimeout(copyTimers[timerIndex].id);
    }
    copyTimers[timerIndex].id = window.setTimeout(function () {
      var currentLabelIndex = findEntry(copyLabels, button);
      if (currentLabelIndex !== -1) {
        button.textContent = copyLabels[currentLabelIndex].text;
        copyLabels.splice(currentLabelIndex, 1);
      }
      var currentTimerIndex = findEntry(copyTimers, button);
      if (currentTimerIndex !== -1) copyTimers.splice(currentTimerIndex, 1);
    }, COPY_RESET_DELAY);
  }

  function handleCopyResult(button, success) {
    if (success) {
      var message = 'Copied to clipboard.';
      if (button && button.id === 'copy-bibtex') message = 'BibTeX copied to clipboard.';
      setCopyStatus(message);
      markCopied(button);
    } else {
      setCopyStatus('Copy failed; select the text manually.');
    }
  }

  function legacyCopy(text) {
    var area = null;
    try {
      area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', 'readonly');
      area.style.position = 'fixed';
      area.style.top = '0';
      area.style.left = '-9999px';
      area.style.width = '1px';
      area.style.height = '1px';
      document.body.appendChild(area);
      area.focus();
      if (typeof area.select === 'function') area.select();
      if (typeof area.setSelectionRange === 'function') {
        try {
          area.setSelectionRange(0, text.length);
        } catch (selectionError) {
          /* Selection is best effort only. */
        }
      }
      if (typeof document.execCommand === 'function') {
        return document.execCommand('copy') === true;
      }
      return false;
    } catch (error) {
      return false;
    } finally {
      if (area && area.parentNode) {
        try {
          area.parentNode.removeChild(area);
        } catch (removeError) {
          /* The temporary field is detached by the browser if needed. */
        }
      }
    }
  }

  function copyToClipboard(text, done) {
    var value = typeof text === 'string' ? text : '';
    var finished = false;
    function finish(ok) {
      if (finished) return;
      finished = true;
      done(ok === true);
    }
    var nav = window.navigator;
    var clipboard = nav ? nav.clipboard : null;
    if (clipboard && typeof clipboard.writeText === 'function') {
      try {
        var result = clipboard.writeText(value);
        if (result && typeof result.then === 'function') {
          result.then(
            function () {
              finish(true);
            },
            function () {
              finish(legacyCopy(value));
            }
          );
          return;
        }
        finish(true);
        return;
      } catch (error) {
        finish(legacyCopy(value));
        return;
      }
    }
    finish(legacyCopy(value));
  }

  function resolveTargetElement(raw) {
    if (!raw) return null;
    var target = null;
    try {
      target = document.querySelector(raw);
    } catch (queryError) {
      target = null;
    }
    if (target) return target;
    var id = raw.charAt(0) === '#' ? raw.slice(1) : raw;
    if (!id) return null;
    return byId(id);
  }

  function resolveCopyText(button) {
    var direct = button.getAttribute('data-copy');
    if (direct !== null) return direct;
    var target = null;
    var selector = button.getAttribute('data-copy-target');
    if (selector) target = resolveTargetElement(selector);
    if (!target) target = byId('bibtex');
    if (!target) return '';
    return target.textContent || '';
  }

  function attachCopy(button, bound) {
    if (!button || typeof button.addEventListener !== 'function') return;
    if (bound.indexOf(button) !== -1) return;
    bound.push(button);
    button.addEventListener('click', function (event) {
      if (event && typeof event.preventDefault === 'function') event.preventDefault();
      copyToClipboard(resolveCopyText(button), function (success) {
        handleCopyResult(button, success);
      });
    });
  }

  function initCopyButtons() {
    var bound = [];
    var candidates = document.querySelectorAll('[data-copy]');
    for (var i = 0; i < candidates.length; i += 1) {
      attachCopy(candidates[i], bound);
    }
    var bibtex = byId('copy-bibtex');
    if (bibtex) attachCopy(bibtex, bound);
  }

  /* ---------- bootstrap ---------- */

  function init() {
    initTheme();
    initResultsFilters();
    initAtlasFilters();
    initRowToggles();
    initCopyButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""

#: Small additive stylesheet for any class the report needs but the design
#: system does not define. Kept separate so the design system file remains a
#: clean, reusable artifact.
_CSS_EXTRA = r"""
/* Additive report styles: everything below uses the design-system tokens above,
   so light, dark and print themes stay consistent. */
.lead{font-size:1.08rem;line-height:1.65;color:var(--text-2);max-width:68ch}
.subtle{color:var(--text-3);font-size:.92rem}
.mono{font-family:var(--font-mono)}
.text-link{color:inherit;text-decoration:underline;text-underline-offset:2px}
.text-link:hover{color:var(--accent)}
.hero-quickstart{margin-top:1.75rem;max-width:60rem}
.hero-note{margin-top:1.6rem}
.stat-hint{display:block;margin-top:.3rem;font-size:.78rem;line-height:1.45;color:var(--text-3)}
.section-sub{margin-top:2.75rem}
.failure-card-title{margin:.15rem 0 0;font-weight:600;font-size:.98rem}
.code-lang{font-family:var(--font-mono);font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;color:var(--text-3)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.plain-list{list-style:none;margin:0;padding:0}
.plain-list li{font-size:.86rem;line-height:1.55;margin:.12rem 0;color:var(--text-2)}
.table caption{text-align:left;font-size:.85rem;color:var(--text-3);padding:.35rem 0 .65rem;caption-side:top}
.honesty-sentence{font-weight:600}
.atlas-group{margin:2.25rem 0 0}
.atlas-group:first-of-type{margin-top:1.25rem}
.atlas-group-title{display:flex;align-items:center;gap:.6rem;font-size:1.05rem;margin:0 0 .9rem}
.atlas-group-title .count{font-size:.78rem;font-weight:600;letter-spacing:.02em;padding:.15rem .5rem;border-radius:999px;background:var(--surface-2);color:var(--text-3);border:1px solid var(--border)}
.atlas-link{display:inline-block;margin-top:.8rem;font-size:.9rem;font-weight:600;color:var(--accent)}
.atlas-link:hover{color:var(--accent-hover)}
.top-failures{list-style:none;margin:1rem 0 0;padding:0;display:grid;gap:.85rem}
.failure-card{border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.1rem;background:var(--surface)}
.failure-card-head{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin-bottom:.35rem}
.failure-card-head h3{margin:0;font-size:.95rem;flex:1 1 20rem}
.failure-reason{margin:.35rem 0 0;color:var(--text-2);font-size:.93rem}
.data-notes{margin:1rem 0 0;padding:.9rem 1.1rem;border-left:3px solid var(--warn);background:color-mix(in srgb, var(--warn) 9%, var(--bg));border-radius:0 8px 8px 0;font-size:.92rem}
.data-notes ul{margin:.4rem 0 0;padding-left:1.2rem}
.data-notes li{margin:.25rem 0}
.honesty-block{border:1px solid var(--border);border-left:4px solid var(--warn);border-radius:0 var(--radius) var(--radius) 0;background:var(--surface);padding:1.25rem 1.4rem}
.honesty-block p{margin:.5rem 0;line-height:1.6}
.honesty-block p:first-child{margin-top:0}
.footer-title{font-size:.95rem;margin:0 0 .5rem}
.severity-mini{display:inline-flex;gap:.35rem;flex-wrap:wrap}
.severity-mini .sev{padding:.05rem .4rem;font-size:.75rem}
.chart-head{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;align-items:baseline;justify-content:space-between;margin-bottom:.5rem}
.chart-head h3{margin:0}
.chart-legend{font-size:.85rem;color:var(--text-3);margin:0}
.hero-status{display:inline-flex;align-items:center;gap:.45rem;font-size:.82rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--text-3)}
.theme-toggle-label{font:inherit}
.table-severity th:first-child,.table-severity td:first-child{white-space:nowrap}
:where([hidden]){display:none!important}
.atlas-card[hidden],.result-row[hidden],.result-detail[hidden],.atlas-group[hidden],.is-hidden{display:none!important}
@media print{.toolbar,.site-header{display:none!important}.failure-card,.atlas-card,.honesty-block{break-inside:avoid}}
"""


def _note(kind: str, body_html: str, *, as_id: str = "", extra_class: str = "") -> str:
    classes = f"note note-{kind} {extra_class}".strip()
    id_attr = f' id="{_esc(as_id)}"' if as_id else ""
    return f'<aside class="{classes}"{id_attr} role="note">{body_html}</aside>'


def _code_block(code: str, label: str = "shell", *, copy: bool = True, element_id: str = "") -> str:
    foot = ""
    if copy:
        foot = (
            ' <button class="copy-btn" type="button" data-copy="'
            + _esc(code)
            + '">Copy</button>'
        )
    id_attr = f' id="{_esc(element_id)}"' if element_id else ""
    return (
        f'<div class="code-block"{id_attr}>'
        f'<div class="code-head"><span class="code-lang">{_esc(label)}</span>{foot}</div>'
        f"<pre><code>{_esc(code)}</code></pre>"
        "</div>"
    )


def _badge_matrix(entry: Dict[str, Any]) -> str:
    parts = []
    for severity in SEVERITY_ORDER:
        count = entry["severities"].get(severity, 0)
        if count:
            parts.append(f'<span class="sev sev-{severity}">{count}</span>')
    return "".join(parts) if parts else '<span class="subtle">none</span>'


def _status_pill(status: str) -> str:
    safe = status if status in STATUS_ORDER else "error"
    return f'<span class="status status-{safe}">{_esc(status)}</span>'


def _severity_pill(severity: str) -> str:
    safe = severity if severity in SEVERITY_WEIGHTS else "unknown"
    label = SEVERITY_LABELS.get(safe, "Unknown")
    return f'<span class="sev sev-{safe}">{_esc(label)}</span>'


def _metric_row(metrics: Dict[str, int]) -> str:
    parts = []
    for key in METRIC_SORT_PRIORITY:
        if key in metrics:
            parts.append(
                f'<span class="metric"><strong>{_fmt_int(metrics[key])}</strong> {_esc(METRIC_LABELS.get(key, key))}</span>'
            )
    for key, value in metrics.items():
        if key not in METRIC_SORT_PRIORITY:
            parts.append(
                f'<span class="metric"><strong>{_fmt_int(value)}</strong> {_esc(METRIC_LABELS.get(key, key))}</span>'
            )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Inline SVG chart (generated in Python, no JS or network needed)
# ---------------------------------------------------------------------------


def _svg_class_chart(classes: Sequence[Dict[str, Any]]) -> str:
    width = 780
    row_height = 34
    top = 18
    label_width = 176
    value_width = 104
    track_x = label_width + 10
    track_width = width - track_x - value_width - 8
    bar_height = 16
    height = top + row_height * max(1, len(classes)) + 8
    parts = [
        '<svg class="bar-chart" viewBox="0 0 %d %d" role="img" '
        'aria-labelledby="chart-title chart-desc" preserveAspectRatio="xMidYMid meet">'
        % (width, height),
        '<title id="chart-title">Pass rate by failure class</title>',
        '<desc id="chart-desc">Horizontal bar chart of mechanical pass rates for each '
        "failure class in this run. Longer bars are better; empty bars mean no probe "
        "in that class was attempted in this run.</desc>",
    ]
    for index, entry in enumerate(classes):
        y = top + index * row_height
        baseline = y + row_height - 10
        rate = entry["pass_rate"]
        fraction = rate if rate is not None else 0.0
        fill_width = max(0.0, min(1.0, fraction)) * track_width
        bar_y = baseline - bar_height
        label = entry["label"]
        value = f"{entry['pass']}/{entry['total']} \u00b7 {_fmt_pct(rate).replace('&mdash;', 'n/a')}"
        parts.append('<g class="bar-row">')
        parts.append(
            f'<text class="bar-label" x="0" y="{baseline - 4}">{_esc(label)}</text>'
        )
        parts.append(
            f'<rect class="bar-track" x="{track_x}" y="{bar_y}" width="{track_width:.1f}" '
            f'height="{bar_height}" rx="{bar_height / 2:.1f}"></rect>'
        )
        if fill_width > 0:
            parts.append(
                f'<rect class="bar-fill bar-fill-pass" x="{track_x}" y="{bar_y}" '
                f'width="{fill_width:.1f}" height="{bar_height}" rx="{bar_height / 2:.1f}">'
                f"<title>{_esc(label)}: {value}</title></rect>"
            )
        parts.append(
            f'<text class="bar-value" x="{width - 2}" y="{baseline - 4}" '
            f'text-anchor="end">{_esc(value)}</text>'
        )
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_hero(payload: Dict[str, Any]) -> str:
    build = payload["build"]
    counts = payload["counts"]
    if build["is_fixture"]:
        banner = FIXTURE_BANNER_TEXT
        label = "Fixture label."
    elif build["is_mock"]:
        banner = DEMO_BANNER_TEXT
        label = "Demo label."
    else:
        banner = LIVE_BANNER_TEXT
        label = "Run label."
    status_bits = [
        f'<span class="mono">failbench {_esc(VERSION)}</span>',
        _esc("demo report" if build["is_demo"] else "run report"),
    ]
    stats = [
        (f"{_fmt_int(counts['probes'])}", "probes attempted"),
        (f"{_fmt_int(counts['evidence'])}", "cited evidence records"),
        (f"{_fmt_int(sum(1 for entry in payload['classes'] if entry['total'] > 0))}", "failure classes covered"),
        ("0", "LLM judges used"),
    ]
    stat_html = "".join(
        f'<div class="stat-card"><span class="stat-value">{value}</span>'
        f'<span class="stat-label">{label}</span></div>'
        for value, label in stats
    )
    note_body = (
        '<p><strong>Honesty statement.</strong> <span class="honesty-sentence">'
        + _esc(HONESTY_SENTENCE)
        + '</span></p><p class="subtle">'
        + _esc(label + " " + banner)
        + "</p>"
    )
    return f"""
<section class="hero" id="top" aria-labelledby="hero-title">
  <div class="wrap">
    <p class="eyebrow"><span class="dot" aria-hidden="true"></span>{' &middot; '.join(status_bits)}</p>
    <h1 class="hero-title" id="hero-title">FailBench</h1>
    <p class="hero-tagline">The evidence-backed, judge-free failure probe kit for LLMs.</p>
    <p class="hero-lede lead">Every probe is deterministic and every claim is sourced. This report is
    generated from a machine-readable run plus a cited evidence atlas; it prints the numbers that were
    actually measured and marks anything that was not, so the demo can be audited rather than trusted.</p>
    <div class="hero-stats">{stat_html}</div>
    <div class="hero-actions">
      <a class="btn btn-primary" href="#demo">Run the quick-start demo</a>
      <a class="btn" href="#results">Read the results</a>
      <a class="btn btn-ghost" href="#atlas">Browse the evidence atlas</a>
    </div>
    <div class="hero-quickstart">
      {_code_block("python -m failbench run --provider mock --demo --out results/demo", "shell")}
    </div>
    {_note("demo", note_body, as_id="honesty-banner", extra_class="hero-note")}
  </div>
</section>
"""


def _render_demo_section(payload: Dict[str, Any]) -> str:
    commands = [
        ("Validate the corpus and evidence (offline)", "python -m failbench validate --strict"),
        ("Produce the deterministic demo run", "python -m failbench run --provider mock --demo --out results/demo"),
        ("Regenerate this page and the Markdown report", "python -m failbench report --results results/demo --out site"),
    ]
    steps = "".join(
        f'<li class="step"><h3>{_esc(title)}</h3>{_code_block(command, "shell")}</li>'
        for title, command in commands
    )
    return f"""
<section class="section" id="demo" aria-labelledby="demo-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="demo-title">Quick-start demo</h2>
      <p class="section-lede">No install, no API key, no network. The kit is stdlib-only Python and the
      mock provider is deterministic: two demo runs produce identical per-probe statuses, counts and
      response hashes (run metadata such as <code>run_id</code> and timestamps differs).</p>
    </div>
    <ol class="steps">{steps}</ol>
    <p class="subtle">Runs from the repository root with plain <code>python</code>. The demo writes
    <code>results/demo/results.json</code> and <code>results/demo/raw.jsonl</code> so every attempt can be
    re-scored offline with <code>python -m failbench replay --results results/demo --out results/replay</code>
    (the <code>--out</code> keeps the committed demo artifacts untouched).</p>
  </div>
</section>
"""


def _render_why_section() -> str:
    cards = [
        (
            "Judge-free",
            "Every probe is scored by one of a small set of mechanical rules: substring, regex, exact match, "
            "numeric tolerance, JSON-schema validation, or a conjunction of those. There is no LLM-as-judge, "
            "so a failure is a concrete mismatch between an expected and an observed string, not an opinion.",
        ),
        (
            "Deterministic",
            "Prompts are static and self-contained; parameters default to temperature 0 and a fixed token "
            "budget; the mock provider is a pure function of the probe. Two mock demo runs produce identical "
            "per-probe statuses, counts and response hashes (run metadata such as run_id and timestamps "
            "differs). Capped raw responses can be replayed and re-scored without a network.",
        ),
        (
            "Evidence-backed",
            "Each failure class in the atlas is anchored to publicly reported incidents from named sources "
            "(papers, issues, vendor documentation, discussions). Cards carry a source link and its popularity "
            "signal so readers can check the claim instead of taking the benchmark's word for it.",
        ),
    ]
    card_html = "".join(
        f'<article class="card"><h3>{_esc(title)}</h3><p>{_esc(body)}</p></article>'
        for title, body in cards
    )
    return f"""
<section class="section" id="why" aria-labelledby="why-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="why-title">Why this kit exists</h2>
      <p class="section-lede">Benchmarks that depend on a judge model are hard to audit and hard to reproduce.
      FailBench is deliberately narrower: mechanical pass conditions, sourced claims, and a report that shows
      its own limitations.</p>
    </div>
    <div class="cards-3">{card_html}</div>
  </div>
</section>
"""


def _render_summary_stats(payload: Dict[str, Any]) -> str:
    counts = payload["counts"]
    severity = payload["severity"]
    weighted = severity["weighted_pass_rate"]
    stats = [
        (f"{_fmt_pct(payload['pass_rate'])}", "overall pass rate", f"{counts['pass']} of {counts['probes']} probes"),
        (
            f"{_fmt_pct(weighted)}",
            "severity-weighted pass rate",
            "critical 4x, high 3x, medium 2x, low 1x; errors count as not passed",
        ),
        (_fmt_int(counts["fail"]), "failures", "mechanical mismatches"),
        (
            _fmt_int(counts["error"]),
            "errors",
            "provider/runtime errors; excluded from failure analysis",
        ),
    ]
    stat_html = "".join(
        f'<div class="stat"><span class="stat-value">{value}</span>'
        f'<span class="stat-label">{label}</span><span class="stat-hint">{hint}</span></div>'
        for value, label, hint in stats
    )
    rows = "".join(
        "<tr>"
        f'<td>{_severity_pill(entry["severity"])}</td>'
        f'<td class="num">{entry["weight"]}x</td>'
        f'<td class="num">{_fmt_int(entry["total"])}</td>'
        f'<td class="num">{_fmt_int(entry["pass"])}</td>'
        f'<td class="num">{_fmt_int(entry["fail"])}</td>'
        f'<td class="num">{_fmt_int(entry["error"])}</td>'
        f'<td class="num">{_fmt_pct(entry["pass_rate"])}</td>'
        "</tr>"
        for entry in severity["rows"]
    )
    unknown = severity.get("unknown") or 0
    unknown_html = (
        f'<p class="subtle">{_fmt_int(unknown)} probe(s) had no valid severity and are excluded from weighted '
        "statistics.</p>"
        if unknown
        else ""
    )
    return f"""
    <div id="severity-summary" class="stat-strip" role="group" aria-label="Summary statistics">{stat_html}</div>
    <div class="table-wrap">
      <table class="table table-severity" aria-describedby="severity-caption">
        <caption id="severity-caption">Severity-weighted summary. Errors are counted as not passed so the
        weighted number cannot flatter the run.</caption>
        <thead><tr><th scope="col">Severity</th><th scope="col">Weight</th><th scope="col">Probes</th>
        <th scope="col">Pass</th><th scope="col">Fail</th><th scope="col">Error</th>
        <th scope="col">Pass rate</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    {unknown_html}
"""


def _render_results_section(payload: Dict[str, Any], warnings: List[str]) -> str:
    build = payload["build"]
    if build["is_fixture"]:
        banner = FIXTURE_BANNER_TEXT
        run_label = "Fixture label."
    elif build["is_mock"]:
        banner = DEMO_BANNER_TEXT
        run_label = "Demo label."
    else:
        banner = LIVE_BANNER_TEXT
        run_label = "Run label."

    class_options = "".join(
        f'<option value="{_esc(entry["name"])}">{_esc(entry["label"])}</option>'
        for entry in payload["classes"]
    )
    severity_options = "".join(
        f'<option value="{severity}">{_esc(SEVERITY_LABELS[severity])}</option>'
        for severity in SEVERITY_ORDER
    )
    status_options = "".join(
        f'<option value="{status}">{status.capitalize()}</option>' for status in STATUS_ORDER
    )

    rows_html: List[str] = []
    for row in payload["probes"]:
        search_blob = " ".join(
            part
            for part in (
                row["id"],
                row["title"],
                row["class_label"],
                row["reason"],
                " ".join(row["tags"]),
                row["scoring_type"],
            )
            if part
        ).lower()
        detail_id = f"detail-{re.sub(r'[^A-Za-z0-9_-]', '-', row['id'])}"
        status = row["status"]
        latency = f'{_fmt_int(row["latency_ms"])} ms' if isinstance(row["latency_ms"], int) else "&mdash;"
        tokens = row.get("tokens") or {}
        token_bits = []
        if isinstance(tokens.get("prompt"), int) or isinstance(tokens.get("completion"), int):
            token_bits.append(
                f'prompt {_fmt_int(tokens.get("prompt", 0))} / completion {_fmt_int(tokens.get("completion", 0))}'
            )
        attempts = row["attempts"]
        attempts_html = ""
        if attempts:
            items = "".join(
                f"<li>{_status_pill(str(attempt.get('status')))} "
                f"<span class=\"mono\">attempt {_fmt_int(attempt.get('index'))}</span> "
                f"{_text(_truncate(attempt.get('reason'), 220))}</li>"
                for attempt in attempts
            )
            attempts_html = f'<div class="detail-block"><h4>Attempts</h4><ol class="attempts">{items}</ol></div>'
        excerpt = _truncate(row["response_excerpt"], 500) or "(no response excerpt recorded)"
        meta_items = []
        if row["scoring_type"]:
            meta_items.append(f"<dt>Scoring rule</dt><dd>{_esc(row['scoring_type'])}</dd>")
        if row["rationale"]:
            meta_items.append(f"<dt>Rationale</dt><dd>{_text(row['rationale'])}</dd>")
        if row["tags"]:
            meta_items.append(f"<dt>Tags</dt><dd>{_text(', '.join(row['tags']))}</dd>")
        if token_bits:
            meta_items.append(f"<dt>Tokens</dt><dd>{_text(' '.join(token_bits))}</dd>")
        if row["evidence_ids"]:
            meta_items.append(f"<dt>Linked evidence</dt><dd>{_text(', '.join(row['evidence_ids']))}</dd>")
        meta_html = "<dl class=\"detail-list\">" + "".join(meta_items) + "</dl>"
        rows_html.append(
            f'<tr class="result-row" data-class="{_esc(row["class"])}" data-severity="{_esc(row["severity"])}" '
            f'data-status="{_esc(status)}" data-search="{_esc(search_blob)}">'
            f'<td class="cell-probe"><span class="probe-id mono">{_esc(row["id"])}</span>'
            f'<span class="probe-title">{_esc(row["title"])}</span></td>'
            f'<td class="cell-class"><span class="tag tag-class">{_esc(row["abbr"])}</span>'
            f'<span class="tag-label">{_esc(row["class_label"])}</span></td>'
            f'<td class="cell-severity">{_severity_pill(row["severity"])}</td>'
            f'<td class="cell-status">{_status_pill(status)}</td>'
            f'<td class="cell-latency mono">{latency}</td>'
            f'<td class="cell-toggle"><button class="row-toggle" type="button" aria-expanded="false" '
            f'aria-controls="{_esc(detail_id)}">Details</button></td>'
            "</tr>"
        )
        rows_html.append(
            f'<tr class="result-detail" id="{_esc(detail_id)}" hidden>'
            '<td colspan="6"><div class="detail-grid">'
            f'<div class="detail-block"><h4>Outcome</h4><p>{_status_pill(status)} '
            f'{_text(_truncate(row["reason"], 400)) or "(no reason recorded)"}</p></div>'
            f'<div class="detail-block"><h4>Response excerpt</h4><pre class="excerpt">{_esc(excerpt)}</pre></div>'
            f'<div class="detail-block"><h4>Probe metadata</h4>{meta_html}</div>'
            f"{attempts_html}"
            "</div></td></tr>"
        )

    notes_html = ""
    if warnings:
        items = "".join(f"<li>{_esc(message)}</li>" for message in warnings)
        notes_html = (
            f'<div class="data-notes" role="note"><strong>Data notes.</strong>'
            f"<ul>{items}</ul></div>"
        )

    failures = [row for row in payload["probes"] if row["status"] in ("fail", "error")]
    failures.sort(key=lambda row: (_severity_rank(row["severity"]), 0 if row["status"] == "fail" else 1))
    top_cards = []
    for row in failures[:6]:
        top_cards.append(
            '<li class="failure-card">'
            '<div class="failure-card-head">'
            + _severity_pill(row["severity"])
            + f'<span class="tag tag-class">{_esc(row["abbr"])}</span>'
            + _status_pill(row["status"])
            + f'<h3 class="mono">{_esc(row["id"])}</h3>'
            + "</div>"
            + f'<p class="failure-card-title">{_esc(row["title"])}</p>'
            + f'<p class="failure-reason">{_text(_truncate(row["reason"], 320)) or "No reason recorded."}</p>'
            + "</li>"
        )
    top_failures_html = (
        f'<ul class="top-failures">{"".join(top_cards)}</ul>'
        if top_cards
        else '<p class="empty-state">No failures or errors were recorded in this run.</p>'
    )

    return f"""
<section class="section" id="results" aria-labelledby="results-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="results-title">Benchmark results</h2>
      <p class="section-lede">Mechanical pass rates for this run, with per-class breakdowns, severity
      weighting, and the concrete reason for every recorded mismatch. Filters and search are local to this
      file; nothing is fetched.</p>
    </div>
    {_note("demo", "<p><strong>" + _esc(run_label) + "</strong>"
                    + _esc(banner) + "</p>", as_id="demo-note")}
    {notes_html}
    {_render_summary_stats(payload)}
    <div class="chart-panel">
      <div class="chart-head">
        <h3>Pass rate by failure class</h3>
        <p class="chart-legend">Bars show mechanical pass rate; labels show pass/total. Longer is better.</p>
      </div>
      <div class="chart" id="class-chart">{_svg_class_chart(payload["classes"])}</div>
    </div>
    <div class="toolbar" id="results-toolbar" role="search" aria-label="Filter probes">
      <div class="field"><label for="filter-class">Class</label>
        <select id="filter-class"><option value="">All classes</option>{class_options}</select></div>
      <div class="field"><label for="filter-severity">Severity</label>
        <select id="filter-severity"><option value="">All severities</option>{severity_options}</select></div>
      <div class="field"><label for="filter-status">Status</label>
        <select id="filter-status"><option value="">All statuses</option>{status_options}</select></div>
      <div class="field field-search"><label for="search-probes">Search</label>
        <input id="search-probes" type="search" autocomplete="off" placeholder="probe id, title, reason, tag"></div>
      <button class="btn btn-small btn-ghost" id="reset-filters" type="button">Reset</button>
      <p class="toolbar-count" id="results-count" role="status" aria-live="polite">Showing {_fmt_int(len(payload["probes"]))} of {_fmt_int(len(payload["probes"]))} probes</p>
    </div>
    <div class="table-wrap">
      <table class="table" id="results-table">
        <caption class="visually-hidden">Per-probe results with expandable failure details</caption>
        <thead><tr>
          <th scope="col">Probe</th><th scope="col">Class</th><th scope="col">Severity</th>
          <th scope="col">Status</th><th scope="col">Latency</th>
          <th scope="col"><span class="visually-hidden">Details</span></th>
        </tr></thead>
        <tbody id="results-body">{"".join(rows_html)}</tbody>
      </table>
    </div>
    <p class="empty-state" id="results-empty" hidden>No probes match the current filters.
    <button class="link-btn" id="reset-filters-inline" type="button">Clear all filters</button></p>
    <div class="section-sub">
      <h3>Top failure examples</h3>
      <p class="subtle">Highest-severity mismatches first. These are mechanical mismatches; provider errors
      are shown but are not treated as model failures.</p>
      {top_failures_html}
    </div>
  </div>
</section>
"""


def _render_atlas_section(payload: Dict[str, Any]) -> str:
    evidence = payload["evidence"]
    class_options = "".join(
        f'<option value="{_esc(entry["name"])}">{_esc(entry["label"])}</option>'
        for entry in payload["classes"]
    )
    source_types = sorted({record["source_type"] for record in evidence if record["source_type"]})
    source_options = "".join(
        f'<option value="{_esc(source_type)}">{_esc(SOURCE_TYPE_LABELS.get(source_type, source_type))}</option>'
        for source_type in source_types
    )
    groups: List[str] = []
    for cls in CLASSES:
        records = [record for record in evidence if record["class"] == cls]
        if not records:
            continue
        cards: List[str] = []
        for record in records:
            href = _safe_href(record["source_url"])
            search_blob = " ".join(
                part
                for part in (
                    record["id"],
                    record["title"],
                    record["source_title"],
                    record["publisher"],
                    record["summary"],
                    record["class_label"],
                )
                if part
            ).lower()
            meta_bits = []
            if record["publisher"]:
                meta_bits.append(_esc(record["publisher"]))
            if record["published_date"]:
                meta_bits.append(_esc(record["published_date"]))
            meta_bits.append(_esc(SOURCE_TYPE_LABELS.get(record["source_type"], record["source_type"] or "source")))
            if record["status"] != "cited":
                meta_bits.append(f'<span class="tag tag-muted">{_esc(record["status"])}</span>')
            title_html = _esc(record["title"] or record["source_title"] or record["id"])
            if href:
                title_html = (
                    f'<a class="text-link" href="{href}" target="_blank" rel="noopener noreferrer">'
                    f"{title_html}</a>"
                )
            quote_html = ""
            if record["quote"]:
                quote_html = f'<blockquote class="atlas-quote">{_esc(_truncate(record["quote"], 200))}</blockquote>'
            summary_html = (
                f'<p class="atlas-summary">{_esc(_truncate(record["summary"], 400))}</p>'
                if record["summary"]
                else '<p class="atlas-summary subtle">No summary was recorded for this source.</p>'
            )
            metrics_html = ""
            if record["metrics"]:
                metrics_html = f'<div class="atlas-metrics">{_metric_row(record["metrics"])}</div>'
            probes_html = ""
            if record["probe_ids"]:
                probes_html = (
                    f'<p class="atlas-probes"><span class="subtle">Linked probes:</span> '
                    f'<span class="mono">{_esc(", ".join(record["probe_ids"]))}</span></p>'
                )
            link_html = (
                f'<a class="atlas-link" href="{href}" target="_blank" rel="noopener noreferrer">'
                "Open source</a>"
                if href
                else '<span class="atlas-link subtle">Link unavailable</span>'
            )
            cards.append(
                f'<article class="atlas-card" data-class="{_esc(cls)}" '
                f'data-source="{_esc(record["source_type"])}" data-search="{_esc(search_blob)}">'
                '<header class="atlas-card-head">'
                f'<span class="tag tag-class">{_esc(record["abbr"])}</span>'
                f'<span class="tag tag-source">{_esc(SOURCE_TYPE_LABELS.get(record["source_type"], record["source_type"] or "source"))}</span>'
                '<span class="tag tag-muted mono">' + _esc(record["id"]) + "</span>"
                "</header>"
                f'<h3 class="atlas-title">{title_html}</h3>'
                f'<p class="atlas-meta">{" &middot; ".join(meta_bits)}</p>'
                f"{summary_html}{quote_html}{metrics_html}{probes_html}"
                f"{link_html}"
                "</article>"
            )
        groups.append(
            f'<section class="atlas-group" data-class="{_esc(cls)}" aria-label="{_esc(CLASS_LABELS[cls])} evidence">'
            f'<h3 class="atlas-group-title">{_esc(CLASS_LABELS[cls])}'
            f'<span class="count">{_fmt_int(len(records))} records</span></h3>'
            f'<div class="atlas-grid">{"".join(cards)}</div></section>'
        )

    if groups:
        body = "".join(groups)
        empty = '<p class="empty-state" id="atlas-empty" hidden>No evidence records match the current filters.</p>'
    else:
        body = ""
        empty = (
            '<p class="empty-state" id="atlas-empty">The evidence atlas has not been generated into this '
            "report yet. Add cited records to <code>data/evidence/&lt;class&gt;.jsonl</code> and regenerate "
            "with <code>python -m failbench report</code>.</p>"
        )
    description = (
        "Publicly reported failure modes grouped by class. Each card links to the original source and, "
        "where the source provides one, its popularity signal. Popularity is an attention signal, not a "
        "measurement of model behaviour."
    )
    atlas = payload.get("atlas") or _atlas_stats(evidence)
    snapshot_dates = ", ".join(atlas.get("snapshot_dates") or []) or "not recorded"
    metric_totals_text = _metric_totals_text(atlas.get("metric_totals") or {}) or "none recorded"
    source_mix = ", ".join(
        f"{_fmt_int(count)} {SOURCE_TYPE_LABELS.get(source_type, source_type)}"
        for source_type, count in sorted(
            (atlas.get("source_types") or {}).items(), key=lambda item: (-item[1], item[0])
        )
    ) or "no sources recorded"
    atlas_stats = [
        (_fmt_int(atlas.get("records", len(evidence))), "cited evidence records"),
        (f"{_fmt_int(atlas.get('classes_covered', 0))} of 10", "failure classes covered"),
        (_fmt_int(atlas.get("metric_records", 0)), "records with popularity metrics"),
        (_esc(snapshot_dates), "collection snapshot date(s)"),
    ]
    atlas_stats_html = (
        '<div class="stat-strip" id="atlas-summary" role="group" aria-label="Evidence atlas summary">'
        + "".join(
            f'<div class="stat"><span class="stat-value">{value}</span>'
            f'<span class="stat-label">{label}</span></div>'
            for value, label in atlas_stats
        )
        + "</div>"
    )
    snapshot_note = _note(
        "info",
        "<p><strong>Popularity snapshot.</strong> Metrics are point-in-time values captured from the "
        f"source APIs on {_esc(snapshot_dates)}. Recorded attention signals in this snapshot: "
        f"{_esc(metric_totals_text)}; source mix: {_esc(source_mix)}. Values are shown only where a "
        "source exposed them, are not normalised or independently verified, and are omitted rather than "
        "estimated. No citation-count or completeness claims are made: popularity measures attention, "
        "not severity, prevalence, or model behaviour.</p>",
        as_id="atlas-snapshot",
    )
    return f"""
<section class="section" id="atlas" aria-labelledby="atlas-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="atlas-title">The Evidence Atlas</h2>
      <p class="section-lede">{_esc(description)}</p>
    </div>
    {atlas_stats_html}
    {snapshot_note}
    <div class="toolbar" id="atlas-toolbar" role="search" aria-label="Filter evidence records">
      <div class="field field-search"><label for="atlas-search">Search</label>
        <input id="atlas-search" type="search" autocomplete="off" placeholder="title, publisher, summary"></div>
      <div class="field"><label for="filter-atlas-class">Class</label>
        <select id="filter-atlas-class"><option value="">All classes</option>{class_options}</select></div>
      <div class="field"><label for="filter-atlas-source">Source type</label>
        <select id="filter-atlas-source"><option value="">All source types</option>{source_options}</select></div>
      <button class="btn btn-small btn-ghost" id="reset-atlas" type="button">Reset</button>
      <p class="toolbar-count" id="atlas-count" role="status" aria-live="polite">Showing {_fmt_int(len(evidence))} of {_fmt_int(len(evidence))} evidence records</p>
    </div>
    <div id="atlas-grid">{body}</div>
    {empty}
  </div>
</section>
"""


def _render_corpus_section(payload: Dict[str, Any]) -> str:
    rows = []
    for entry in payload["probe_corpus"]["by_class"]:
        examples = "".join(
            f'<li>{_esc(example)}</li>' for example in entry["examples"]
        )
        evidence_count = next(
            (cls["evidence_count"] for cls in payload["classes"] if cls["name"] == entry["class"]), 0
        )
        rows.append(
            f'<tr data-class="{_esc(entry["class"])}">'
            f'<td><span class="tag tag-class">{_esc(entry["abbr"])}</span> '
            f'<span class="tag-label">{_esc(entry["label"])}</span></td>'
            f'<td class="num">{_fmt_int(entry["count"])}</td>'
            f'<td><span class="severity-mini">{_badge_matrix(entry)}</span></td>'
            f'<td><ul class="plain-list">{examples or "<li>none</li>"}</ul></td>'
            f'<td class="num">{_fmt_int(evidence_count)}</td>'
            "</tr>"
        )
    total = payload["probe_corpus"]["total"]
    return f"""
<section class="section" id="corpus" aria-labelledby="corpus-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="corpus-title">Probe corpus</h2>
      <p class="section-lede">The probe corpus is the fixed, versioned input to every run: {_fmt_int(total)}
      static probes across ten failure classes. A result row is only meaningful relative to this corpus, so
      the corpus and its severity mix are printed alongside the results.</p>
    </div>
    <div class="table-wrap">
      <table class="table table-corpus" id="corpus-table">
        <caption>Probe corpus coverage by class. Severity counts are probe counts; example titles are the
        highest-severity probes in each class.</caption>
        <thead><tr><th scope="col">Class</th><th scope="col">Probes</th><th scope="col">Severity mix</th>
        <th scope="col">Example probes</th><th scope="col">Atlas records</th></tr></thead>
        <tbody id="corpus-body">{"".join(rows)}</tbody>
      </table>
    </div>
  </div>
</section>
"""


def _render_method_section(payload: Dict[str, Any]) -> str:
    severe = payload["severity"]
    threats = [
        "<strong>Small sample per class.</strong> Per-class pass rates rest on a handful of probes; a "
        "single flip moves them by several points. Read the counts, not just the percentage.",
        "<strong>Static, single-turn prompts.</strong> The kit measures controlled failure modes, not "
        "agentic or multi-turn behaviour in production, and it is not a general capability ranking.",
        "<strong>Fixed, public probes.</strong> A model or prompt that has seen the corpus could overfit it. "
        "Treat scores as a regression signal for your own deployment, and add private probes for holdout.",
        "<strong>Mechanical grading only.</strong> Pass conditions favour checkable properties (format, "
        "recall, constraint compliance). Open-ended quality dimensions are intentionally out of scope; a "
        "high pass rate is not evidence of general correctness.",
        "<strong>Prompt and parameter sensitivity.</strong> Results are specific to the committed prompts, "
        "temperature and token budget. Changing any of them changes the measurement.",
        "<strong>Version drift.</strong> Endpoints and models change silently; a run is a snapshot. Keep the "
        "raw transcripts (raw.jsonl) with the results to make runs auditable and replayable.",
        "<strong>Evidence popularity is not severity.</strong> Atlas metrics (HN points, citations, stars) "
        "measure attention, not prevalence or impact. Classes under-reported in public discussion may be "
        "under-represented in the atlas.",
    ]
    threats_html = "".join(f"<li>{item}</li>" for item in threats)
    formula = (
        "weighted pass rate = \u03a3(weight \u00d7 passed probes) / \u03a3(weight \u00d7 attempted probes), "
        "with weights critical 4, high 3, medium 2, low 1. Provider errors count as not passed."
    )
    return f"""
<section class="section" id="methodology" aria-labelledby="methodology-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="methodology-title">Methodology and threats to validity</h2>
      <p class="section-lede">Short version: each probe has exactly one mechanically checkable pass
      condition, every response is recorded, and nothing in the report is inferred by a model.</p>
    </div>
    <div class="method-grid">
      <div class="prose">
        <h3>How a probe is scored</h3>
        <p>A probe declares a static prompt, decoding parameters, a repeat count, and a scoring rule from a
        closed set of mechanical types (substring contains, exact match, regex, numeric tolerance, a minimal
        JSON-schema subset, or a conjunction of these). Scoring normalizes whitespace and, where the rule
        says so, case. The scorer returns a boolean plus a concrete mismatch detail; those details are the
        <code>reason</code> fields on this page.</p>
        <h3>Run semantics</h3>
        <p>Statuses are <code>pass</code>, <code>fail</code> and <code>error</code>. Provider or runtime
        errors are recorded as errors and are never counted as model failures; they are excluded from the
        failure analysis and shown separately. Every attempt is written to <code>raw.jsonl</code> so a run
        can be re-scored offline with the replay provider. Repeat runs of the deterministic mock provider
        agree on per-probe statuses, counts and response hashes; only run metadata differs.</p>
        <h3>Severity weighting</h3>
        <p>{_esc(formula)} The weighting is a presentation choice, not a claim of statistical importance:
        it is a fixed, published function so readers can recompute the summary from the per-class table.</p>
        <h3>What this page does not measure</h3>
        <p>It does not rank models, does not estimate production failure rates, and does not aggregate across
        runs. A pass rate of {_fmt_pct(payload["pass_rate"])} on this corpus means exactly that many committed
        probes met their mechanical condition under the recorded configuration.</p>
      </div>
      <div class="prose">
        <h3>Threats to validity</h3>
        <ul class="threat-list">{threats_html}</ul>
      </div>
    </div>
  </div>
</section>
"""


def _render_endpoint_section() -> str:
    openai_example = (
        "# Any OpenAI-compatible /chat/completions endpoint works; keys are read from an env var\n"
        'export FAILBENCH_BASE_URL="https://<your-host>/v1"\n'
        'python -m failbench run --provider openai \\\n'
        '  --base-url "$FAILBENCH_BASE_URL" --api-key-env FAILBENCH_API_KEY \\\n'
        "  --model <model-name> --out results/run1\n"
        "\n"
        "# Then generate the same kind of report for that run\n"
        "python -m failbench report --results results/run1 --out site"
    )
    local_examples = (
        "# Local vLLM on the default port\n"
        "python -m failbench run --provider openai --base-url http://localhost:8000/v1 \\\n"
        "  --api-key-env FAILBENCH_API_KEY --model <served-model-name> --out results/local\n"
        "\n"
        "# Local Ollama on the default port\n"
        "python -m failbench run --provider openai --base-url http://localhost:11434/v1 \\\n"
        "  --api-key-env FAILBENCH_API_KEY --model llama3.1 --out results/local"
    )
    return f"""
<section class="section" id="your-endpoint" aria-labelledby="endpoint-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="endpoint-title">Run it on your own endpoint</h2>
      <p class="section-lede">The kit speaks the OpenAI-compatible chat-completions protocol through the
      Python standard library. API keys are read from an environment variable and are never written to any
      artifact; raw prompts and responses are recorded without secrets.</p>
    </div>
    <div class="method-grid">
      <div>
        <h3>Hosted OpenAI-compatible endpoint</h3>
        {_code_block(openai_example, "shell")}
      </div>
      <div>
        <h3>Local server</h3>
        {_code_block(local_examples, "shell")}
      </div>
    </div>
    <p class="subtle">Set <code>--concurrency</code> to respect your provider's rate limits, and
    <code>--class</code> or <code>--limit</code> for a quick smoke run. Re-scoring is offline:
    <code>python -m failbench replay --results results/run1 --out results/replay</code>.</p>
  </div>
</section>
"""


def _render_ci_section() -> str:
    gate_example = (
        "# Baseline and candidate results, then a non-zero exit on regressions\n"
        "python -m failbench gate \\\n"
        "  --baseline results/baseline/results.json \\\n"
        "  --current results/candidate/results.json"
    )
    workflow = (
        "name: failbench\n"
        "on: [pull_request]\n"
        "jobs:\n"
        "  probes:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: '3.13'\n"
        "      - run: python -m failbench validate --strict\n"
        "      - run: python -m failbench run --provider mock --demo --out results/demo\n"
        "      - run: python -m failbench gate --baseline results/demo/results.json "
        "--current results/demo/results.json\n"
    )
    return f"""
<section class="section" id="ci" aria-labelledby="ci-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="ci-title">Use it as a CI regression gate</h2>
      <p class="section-lede">The gate compares a baseline result file with a candidate result file and
      exits non-zero when a probe that passed in the baseline now fails or errors, or when a baseline probe
      is missing from the candidate. It is a per-probe status comparison only: it does not compare aggregate
      scores, severity-weighted or otherwise. The demo provider keeps the gate testable offline; point the
      same command at a recorded live run to gate a deployment.</p>
    </div>
    <div class="method-grid">
      <div>
        <h3>Compare two runs</h3>
        {_code_block(gate_example, "shell")}
      </div>
      <div>
        <h3>Minimal workflow shape</h3>
        {_code_block(workflow, "yaml")}
      </div>
    </div>
  </div>
</section>
"""


def _render_contribute_section() -> str:
    return """
<section class="section" id="contribute" aria-labelledby="contribute-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="contribute-title">Contribute evidence or probes</h2>
      <p class="section-lede">Both halves of the project are data: the atlas is cited public reports, and the
      corpus is deterministic probes. Contributions are reviewed against the same contract the generated
      artifacts follow.</p>
    </div>
    <div class="method-grid">
      <div class="prose">
        <h3>Adding evidence</h3>
        <p>Add one JSON object per line to <code>data/evidence/&lt;class&gt;.jsonl</code> with a real source
        URL you verified yourself, a short neutral summary, and no invented metrics. Quote only exact text
        and only when it is short; otherwise leave <code>quote</code> empty. Run
        <code>python -m failbench validate --strict</code> before opening a pull request.</p>
      </div>
      <div class="prose">
        <h3>Adding probes</h3>
        <p>Add one JSON file to <code>probes/&lt;class&gt;/&lt;probe_id&gt;.json</code> with a static,
        self-contained prompt and a single mechanical pass condition. No harmful payloads, no private data,
        no long third-party text. A probe that cannot be graded by a fixed rule does not belong in this
        corpus. The schema and scoring types are documented in <code>docs/CONTRACT.md</code>.</p>
      </div>
    </div>
  </div>
</section>
"""


def _render_citation_section(payload: Dict[str, Any]) -> str:
    bibtex = _bibtex()
    return f"""
<section class="section" id="cite" aria-labelledby="cite-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="cite-title">Cite this work</h2>
      <p class="section-lede">If FailBench is useful in a paper, report, or internal evaluation, cite the
      project as software using the entry below. The canonical repository URL and archived release are
      announced with the public release.</p>
    </div>
    <div class="citation-box">
      <div class="code-head"><span class="code-lang">bibtex</span>
        <button class="copy-btn" id="copy-bibtex" type="button" data-copy-target="bibtex">Copy BibTeX</button>
      </div>
      <pre class="bibtex" id="bibtex">{_esc(bibtex)}</pre>
      <p class="subtle" id="copy-status" role="status" aria-live="polite"></p>
    </div>
  </div>
</section>
"""


def _bibtex() -> str:
    return (
        "@misc{failbench2026,\n"
        "  title        = {FailBench: an evidence-backed, judge-free failure probe kit for LLMs},\n"
        "  author       = {{The FailBench contributors}},\n"
        "  year         = {2026},\n"
        "  note         = {Version " + VERSION + ". Open-source research software; the canonical "
        "repository URL is listed in the project README.},\n"
        "  howpublished = {Open-source software}\n"
        "}"
    )


def _render_honesty_section(payload: Dict[str, Any]) -> str:
    build = payload["build"]
    provider = build["provider"]
    lines = [
        f"<p><strong>Build honesty.</strong> <span class=\"honesty-sentence\">{_esc(HONESTY_SENTENCE)}</span></p>",
    ]
    if build["is_fixture"]:
        lines.append(
            "<p>This particular page was generated from a synthetic fixture to validate the report pipeline "
            "while the demo run and the cited evidence corpus were still being assembled. It is labelled a "
            "fixture render and must be regenerated from committed results before publication.</p>"
        )
    elif build["is_mock"]:
        lines.append(
            "<p>This page was generated from the committed demo run, which uses the deterministic "
            "<em>mock provider</em>. Mock responses are synthetic by construction: the numbers show that the "
            "harness, scorers and report agree with each other, not how any model behaves.</p>"
        )
    else:
        lines.append(
            f"<p>This page was generated from a run with provider <code>{_esc(provider)}</code> and model "
            f"<code>{_esc(build['model'] or 'unspecified')}</code>. That run is a snapshot of one endpoint "
            "configuration; it is not a general benchmark claim about the model family.</p>"
        )
    lines.append(
        "<p>What is printed here is derived from committed files only: "
        f"<code>{_fmt_int(payload['counts']['probes'])}</code> probe attempts, "
        f"<code>{_fmt_int(payload['counts']['evidence'])}</code> cited evidence records, and "
        f"<code>{_fmt_int(payload['counts']['probe_corpus'])}</code> corpus probes. Missing inputs are shown "
        "as explicit empty states rather than filled in.</p>"
    )
    return f"""
<section class="section" id="honesty" aria-labelledby="honesty-title">
  <div class="wrap">
    <div class="section-head">
      <h2 id="honesty-title">Honesty and limitations</h2>
    </div>
    <div class="honesty-block">{''.join(lines)}</div>
  </div>
</section>
"""


def _render_footer(payload: Dict[str, Any]) -> str:
    generated = payload["generated_at"]
    run_id = payload["build"]["run_id"] or "unknown run"
    return f"""
<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-col">
        <h2 class="footer-title">FailBench</h2>
        <p class="subtle">An evidence-backed, judge-free failure probe kit for LLMs. Version
        {_esc(VERSION)}.</p>
      </div>
      <div class="footer-col">
        <h2 class="footer-title">Licenses</h2>
        <p class="subtle">Code: MIT. Data (evidence atlas and probe corpus): CC-BY-4.0. Source links point
        to third-party material that remains under its own license.</p>
      </div>
      <div class="footer-col">
        <h2 class="footer-title">Scope</h2>
        <p class="subtle">Not affiliated with any model vendor. No benchmark claim is made beyond what is
        measured and printed here.</p>
      </div>
    </div>
    <div class="footer-bottom">
      <p class="subtle">Generated by <code>failbench report</code> from <code>{_esc(run_id)}</code> on
      {_esc(generated)}. Report page version {_esc(VERSION)}.</p>
    </div>
  </div>
</footer>
"""


# ---------------------------------------------------------------------------
# Whole-page renderer
# ---------------------------------------------------------------------------


def _render_html(payload: Dict[str, Any], warnings: List[str]) -> str:
    run_id = payload["build"]["run_id"]
    provider = payload["build"]["provider"]
    page_title = f"FailBench report \u2014 {run_id or 'run'}"
    description = (
        "FailBench demo report: judge-free, deterministic LLM failure probes with per-class mechanical "
        "results and a cited evidence atlas. Demo numbers come from a deterministic mock provider."
    )
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Escape closing tags so the JSON can never terminate the script element.
    data_json = data_json.replace("</", "<\\/")
    nav_items = [
        ("#demo", "Demo"),
        ("#why", "Why"),
        ("#results", "Results"),
        ("#atlas", "Atlas"),
        ("#corpus", "Corpus"),
        ("#methodology", "Method"),
        ("#your-endpoint", "Your endpoint"),
        ("#ci", "CI"),
        ("#cite", "Cite"),
    ]
    nav_html = "".join(f'<li><a href="{href}">{label}</a></li>' for href, label in nav_items)
    sections = [
        _render_hero(payload),
        _render_demo_section(payload),
        _render_why_section(),
        _render_results_section(payload, warnings),
        _render_atlas_section(payload),
        _render_corpus_section(payload),
        _render_method_section(payload),
        _render_endpoint_section(),
        _render_ci_section(),
        _render_contribute_section(),
        _render_citation_section(payload),
        _render_honesty_section(payload),
    ]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(page_title)}</title>
<meta name="description" content="{_esc(description)}">
<meta name="generator" content="failbench report {_esc(VERSION)}">
<meta name="color-scheme" content="light dark">
<style>
{_CSS}
{_CSS_EXTRA}
</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to main content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="#top"><span class="brand-mark" aria-hidden="true">FB</span><span class="brand-name">FailBench</span></a>
    <nav class="nav" aria-label="Primary"><ul class="nav-list">{nav_html}</ul></nav>
    <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Toggle color theme" aria-pressed="false">
      <span class="theme-toggle-label">Theme</span>
    </button>
  </div>
</header>
<main id="main">
{"".join(sections)}
</main>
{_render_footer(payload)}
<script id="fb-data" type="application/json">{data_json}</script>
<script>
{_JS}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _md_table(headers: Sequence[str], rows: Iterable[Sequence[str]], align: Optional[Sequence[str]] = None) -> str:
    align = list(align or ["---"] * len(headers))
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(align) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _md_banner(payload: Dict[str, Any]) -> str:
    build = payload["build"]
    if build["is_fixture"]:
        return "Fixture render: generated from a synthetic fixture for pipeline validation. Regenerate this file from the committed demo run before publishing."
    if build["is_mock"]:
        return "Demo run: produced by the deterministic mock provider. These numbers demonstrate the pipeline; they are not measurements of any model."
    return (
        "Live run: produced by the configured provider against a real endpoint. These numbers are a "
        "snapshot of that endpoint, model, configuration and date."
    )


def _render_markdown(payload: Dict[str, Any], warnings: List[str]) -> str:
    build = payload["build"]
    counts = payload["counts"]
    severity = payload["severity"]
    lines: List[str] = []
    add = lines.append

    add("# FailBench results report")
    add("")
    add(
        "> Generated by `failbench report` (version "
        + VERSION
        + ") from `docs/CONTRACT.md`-shaped input files. Do not edit by hand: regenerate with "
        "`python -m failbench report --results <results-dir> --out site`."
    )
    add("")
    add("## Honesty statement")
    add("")
    add(HONESTY_SENTENCE)
    add("")
    add(
        "This build ships a demo run against the deterministic **mock provider** and a cited evidence "
        "atlas. No live model endpoint was available to the build, so the committed demo numbers exercise "
        "the pipeline rather than measure any model. To obtain real numbers, run the kit against your own "
        "OpenAI-compatible endpoint (see below)."
    )
    add("")
    if warnings:
        add("**Data notes.** " + " ".join(f"({index + 1}) {message}" for index, message in enumerate(warnings)))
        add("")
    add("Build label: " + _md_banner(payload))
    add("")
    add("## Run metadata")
    add("")
    config = build.get("config") or {}
    environment = build.get("environment") or {}
    meta_rows = [
        ("Run ID", f"`{build['run_id'] or 'unknown'}`"),
        ("Provider", f"`{build['provider']}`"),
        ("Model", f"`{build['model'] or 'unspecified'}`"),
        ("Base URL", f"`{build['base_url']}`" if build.get("base_url") else ("none (offline mock)" if build["is_mock"] else "not set")),
        ("Suite version", f"`{build['suite_version'] or VERSION}`"),
        ("Started", str(build.get("started_at") or "unknown")),
        ("Finished", str(build.get("finished_at") or "unknown")),
        ("Environment", ", ".join(f"{key}: {value}" for key, value in environment.items()) or "not recorded"),
        ("Configuration", ", ".join(f"{key}: {value}" for key, value in config.items()) or "not recorded"),
        ("Report generated", payload["generated_at"]),
        ("Generator", payload["generator"]),
    ]
    add(_md_table(["Field", "Value"], meta_rows, ["---", "---"]))
    add("")
    add("## Summary")
    add("")
    add(f"- Probes attempted: **{_fmt_int(counts['probes'])}**")
    add(f"- Passed: **{_fmt_int(counts['pass'])}**")
    add(f"- Failed: **{_fmt_int(counts['fail'])}**")
    add(f"- Errors (provider/runtime, not model failures): **{_fmt_int(counts['error'])}**")
    add(f"- Overall pass rate: **{_fmt_pct_md(payload['pass_rate'])}**")
    add(
        f"- Severity-weighted pass rate: **{_fmt_pct_md(severity['weighted_pass_rate'])}** "
        "(critical 4x, high 3x, medium 2x, low 1x; errors count as not passed)"
    )
    add(f"- Evidence records in atlas: **{_fmt_int(counts['evidence'])}**")
    add(f"- Probes in corpus: **{_fmt_int(counts['probe_corpus'])}**")
    add("")
    add("## Results by failure class")
    add("")
    class_rows = []
    for entry in payload["classes"]:
        class_rows.append(
            [
                f"{entry['label']} (`{entry['name']}`)",
                _fmt_int(entry["total"]),
                _fmt_int(entry["pass"]),
                _fmt_int(entry["fail"]),
                _fmt_int(entry["error"]),
                _fmt_pct_md(entry["pass_rate"]),
            ]
        )
    total_row = [
        "**Total**",
        _fmt_int(counts["probes"]),
        _fmt_int(counts["pass"]),
        _fmt_int(counts["fail"]),
        _fmt_int(counts["error"]),
        _fmt_pct_md(payload["pass_rate"]),
    ]
    class_rows.append(total_row)
    add(_md_table(["Class", "Probes", "Pass", "Fail", "Error", "Pass rate"], class_rows, ["---", "---:", "---:", "---:", "---:", "---:"]))
    add("")
    add(
        "Classes with zero attempted probes are still listed so a partial run cannot hide missing coverage. "
        "The corpus column shows how many probes exist in each class; see the probe corpus section."
    )
    add("")
    add("## Severity-weighted summary")
    add("")
    severity_rows = []
    for entry in severity["rows"]:
        severity_rows.append(
            [
                SEVERITY_LABELS[entry["severity"]],
                f"{entry['weight']}x",
                _fmt_int(entry["total"]),
                _fmt_int(entry["pass"]),
                _fmt_int(entry["fail"]),
                _fmt_int(entry["error"]),
                _fmt_pct_md(entry["pass_rate"]),
            ]
        )
    severity_rows.append(
        ["**Weighted**", "", _fmt_int(severity["total"]), _fmt_int(severity["pass"]), "", "", _fmt_pct_md(severity["weighted_pass_rate"])]
    )
    add(_md_table(["Severity", "Weight", "Probes", "Pass", "Fail", "Error", "Pass rate"], severity_rows, ["---", "---:", "---:", "---:", "---:", "---:", "---:"]))
    add("")
    add(
        "Weighted pass rate = sum(weight x passed) / sum(weight x attempted). The weights are a published, "
        "fixed presentation choice, not a statistical estimate of severity."
    )
    if severity.get("unknown"):
        add("")
        add(f"{_fmt_int(severity['unknown'])} probe(s) had no valid severity and are excluded from the weighted summary.")
    add("")
    add("## Top failures (examples)")
    add("")
    failures = [row for row in payload["probes"] if row["status"] in ("fail", "error")]
    failures.sort(key=lambda row: (_severity_rank(row["severity"]), 0 if row["status"] == "fail" else 1))
    if failures:
        for index, row in enumerate(failures[:10], 1):
            reason = _truncate(row["reason"], 300) or "no reason recorded"
            add(
                f"{index}. **`{row['id']}`** ({row['class_label']}, {SEVERITY_LABELS.get(row['severity'], 'unknown')}) "
                f"- {row['status']}: {reason}"
            )
            excerpt = _truncate(row["response_excerpt"], 240)
            if excerpt:
                add(f"   - Response excerpt: `{excerpt}`")
    else:
        add("No failures or errors were recorded in this run.")
    add("")
    add(
        "Failures are mechanical mismatches between the expected condition and the recorded response. "
        "Provider errors are listed in the same table but are not counted as model failures."
    )
    add("")
    add("## Evidence atlas summary")
    add("")
    if payload["evidence"]:
        evidence_by_class: Dict[str, int] = {}
        for record in payload["evidence"]:
            evidence_by_class[record["class"]] = evidence_by_class.get(record["class"], 0) + 1
        atlas_rows = [
            [f"{CLASS_LABELS[cls]} (`{cls}`)", _fmt_int(evidence_by_class.get(cls, 0))]
            for cls in CLASSES
            if evidence_by_class.get(cls, 0)
        ]
        add(_md_table(["Class", "Evidence records"], atlas_rows, ["---", "---:"]))
        add("")
        add(
            "The full atlas, with source links, publishers, dates and popularity metrics, is rendered in "
            "`site/index.html` under the Evidence Atlas section. Popularity signals measure attention, not "
            "model behaviour."
        )
        atlas = payload.get("atlas") or {}
        snapshot_dates = ", ".join(atlas.get("snapshot_dates") or []) or "not recorded"
        metric_totals_text = _metric_totals_text(atlas.get("metric_totals") or {}) or "none recorded"
        source_mix = ", ".join(
            f"{_fmt_int(count)} {SOURCE_TYPE_LABELS.get(source_type, source_type)}"
            for source_type, count in sorted(
                (atlas.get("source_types") or {}).items(), key=lambda item: (-item[1], item[0])
            )
        ) or "no sources recorded"
        add("")
        add(
            f"Popularity snapshot: metrics were captured from the source APIs on {snapshot_dates} and are "
            f"point-in-time values. Recorded attention signals in this snapshot: {metric_totals_text}; "
            f"source mix: {source_mix}. They are not normalised or independently verified, values are "
            "shown only where a source exposed them (omitted rather than estimated), and no citation-count "
            "or completeness claims are made. Popularity is not severity or prevalence."
        )
    else:
        add(
            "No evidence records were loaded for this generation. Add cited records under "
            "`data/evidence/<class>.jsonl` and regenerate."
        )
    add("")
    add("## Reproduction")
    add("")
    add("From the repository root, with plain `python` (Python 3.9 or newer; CI exercises 3.11 and 3.13; no third-party dependencies):")
    add("")
    add("```shell")
    add("python -m failbench validate --strict")
    add("python -m failbench run --provider mock --demo --out results/demo")
    add("python -m failbench report --results results/demo --out site")
    add("python -m failbench replay --results results/demo --out results/replay")
    add("```")
    add("")
    add("The demo run writes `results/demo/results.json` and `results/demo/raw.jsonl`; the reported numbers "
        "come from `results.json` and the raw attempts are replayable offline. Two mock demo runs produce "
        "identical per-probe statuses, counts and response hashes; the run metadata (run_id, timestamps) "
        "differs by design, so compare the normalized per-probe results rather than the raw files.")
    if build["is_fixture"]:
        add("")
        add(
            "This particular file was generated from a synthetic fixture (recorded statuses only) to "
            "validate the report pipeline; the commands above are the canonical reproduction path for the "
            "committed demo run once it lands."
        )
    add("")
    add("## Run against your own endpoint")
    add("")
    add("Any OpenAI-compatible `/chat/completions` endpoint works. API keys are read from an environment "
        "variable and never written to an artifact.")
    add("")
    add("```shell")
    add('export FAILBENCH_BASE_URL="https://<your-host>/v1"')
    add("python -m failbench run --provider openai \\")
    add('  --base-url "$FAILBENCH_BASE_URL" --api-key-env FAILBENCH_API_KEY \\')
    add("  --model <model-name> --out results/run1")
    add("python -m failbench report --results results/run1 --out site")
    add("```")
    add("")
    add("Local servers such as vLLM (`http://localhost:8000/v1`) or Ollama (`http://localhost:11434/v1`) "
        "use the same provider.")
    add("")
    add("## CI gate")
    add("")
    add("```shell")
    add("python -m failbench gate \\")
    add("  --baseline results/baseline/results.json \\")
    add("  --current results/candidate/results.json")
    add("```")
    add("")
    add("The gate exits non-zero when a probe that passed in the baseline now fails or errors, or when a "
        "baseline probe is missing from the current run. It is a per-probe status comparison only: it does "
        "not compare aggregate scores, severity-weighted or otherwise. The offline mock provider keeps the "
        "gate testable in CI without an API key.")
    add("")
    add("## Methodology and threats to validity")
    add("")
    add(
        "Probes are static prompts scored by mechanical rules (substring contains, exact match, regex, "
        "numeric tolerance, a minimal JSON-schema subset, or a conjunction of these). No LLM-as-judge is "
        "used. Errors are recorded separately and never counted as failures."
    )
    add("")
    add("Threats to validity:")
    add("")
    add("- Small per-class samples: one probe can move a class pass rate by several points.")
    add("- Static single-turn prompts only; this is not a general capability ranking.")
    add("- Public fixed corpus: overfitting is possible; add private probes for holdout.")
    add("- Mechanical grading favours checkable properties over open-ended quality.")
    add("- Results are specific to the committed prompts, parameters and endpoint snapshot.")
    add("- Evidence popularity is not severity or prevalence.")
    add("")
    add("## Citation")
    add("")
    add("```bibtex")
    add(_bibtex())
    add("```")
    add("")
    add("## License")
    add("")
    add("Code: MIT. Data (evidence atlas and probe corpus): CC-BY-4.0. External sources remain under their "
        "own licenses; the atlas links to them and stores only short quotations and neutral summaries.")
    add("")
    add("Not affiliated with any model vendor. No benchmark claim is made beyond what is measured above.")
    add("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render(
    results_path: Any,
    out_dir: Any,
    probes_dir: Any = None,
    evidence_dir: Any = None,
    results_md_path: Any = None,
) -> Dict[str, Any]:
    """Render the self-contained site and the generated Markdown report.

    Parameters
    ----------
    results_path:
        Path to a results directory (containing ``results.json``) or directly to
        a ``results.json`` file (docs/CONTRACT.md section 7).
    out_dir:
        Output directory for ``index.html``; created if missing.
    probes_dir:
        Optional probe corpus root (defaults to ``<repo>/probes``).
    evidence_dir:
        Optional evidence atlas root containing ``<class>.jsonl`` files
        (defaults to ``<repo>/data/evidence``). Missing directories degrade to an
        explicit empty atlas.
    results_md_path:
        Optional path for the generated Markdown report. Defaults to
        ``<repo>/docs/RESULTS.md``. Pass an empty string or ``False`` to skip
        writing the Markdown file.

    Returns
    -------
    dict
        ``{"results_path", "site_path", "results_md_path", "probes", "evidence"}``.
    """
    warnings: List[str] = []
    results_file = _resolve_results_path(results_path)
    results = _load_json_file(results_file)

    corpus = _load_corpus(probes_dir, warnings)
    corpus_by_id: Dict[str, Dict[str, Any]] = {}
    for record in corpus:
        probe_id = record.get("id")
        if isinstance(probe_id, str) and probe_id not in corpus_by_id:
            corpus_by_id[probe_id] = record

    evidence = _load_atlas(evidence_dir, warnings)
    if evidence:
        covered = {
            record.get("class")
            for record in evidence
            if isinstance(record, dict) and record.get("class") in CLASSES
        }
        missing_classes = [cls for cls in CLASSES if cls not in covered]
        if missing_classes:
            _warn(
                warnings,
                f"evidence atlas currently covers {len(covered)} of {len(CLASSES)} failure classes; "
                f"{len(missing_classes)} class(es) have no cited records yet.",
            )
    normalized_evidence = _normalize_evidence(evidence, warnings)
    rows = _normalize_probe_rows(results, corpus_by_id, warnings)
    payload = _build_payload(results, results_file, rows, normalized_evidence, corpus, warnings)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    site_path = out_path / "index.html"
    html_text = _render_html(payload, warnings)
    with open(site_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html_text)

    markdown_path: Optional[Path]
    if results_md_path is None:
        markdown_path = REPO_ROOT / "docs" / "RESULTS.md"
    elif not results_md_path:
        markdown_path = None
    else:
        markdown_path = Path(results_md_path)
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = _render_markdown(payload, warnings)
        with open(markdown_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)

    summary: Dict[str, Any] = {
        "results_path": str(results_file),
        "site_path": str(site_path),
        "results_md_path": str(markdown_path) if markdown_path is not None else None,
        "probes": len(rows),
        "evidence": len(normalized_evidence),
    }
    return summary


# ``python -m failbench.report`` convenience entry point (the supported CLI is
# ``python -m failbench report``, implemented in failbench/cli.py).
def _main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover - convenience only
    import argparse

    parser = argparse.ArgumentParser(prog="python -m failbench.report", description="Generate the FailBench static report and Markdown report.")
    parser.add_argument("--results", required=True, help="results directory or results.json path")
    parser.add_argument("--out", default="site", help="output directory for index.html (default: site)")
    parser.add_argument("--probes", default=None, help="probe corpus root (default: <repo>/probes)")
    parser.add_argument("--evidence", default=None, help="evidence atlas root (default: <repo>/data/evidence)")
    parser.add_argument("--results-md", default=None, dest="results_md", help="Markdown output path (default: <repo>/docs/RESULTS.md)")
    args = parser.parse_args(argv)
    summary = render(
        results_path=args.results,
        out_dir=args.out,
        probes_dir=args.probes,
        evidence_dir=args.evidence,
        results_md_path=args.results_md,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
