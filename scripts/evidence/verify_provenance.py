#!/usr/bin/env python3
"""Verify every evidence record against the raw API dumps used to mine it.

Purpose: enforce the FailBench non-negotiable "no fabricated data". The raw
collector dumps under ``_scratch/w1/raw/**`` hold the normalized candidates
exactly as the APIs returned them. For every record in ``data/evidence/*.jsonl``
this script requires that:

  * ``source_url`` appears in a raw dump (i.e. the URL really was returned),
  * ``source_title``, ``publisher`` and ``published_date`` equal the dump values,
  * ``metrics`` equal the dump values,
  * arXiv ``quote`` is an exact substring of that candidate's ``_abstract``
    (and <= 200 chars), while non-arXiv ``quote`` is ``""``,
  * ids/URLs are unique across the whole atlas, ids/classes/file names are
    consistent, ``collected_at``/``status``/``collected_by`` follow the
    contract, dates are ISO, and no placeholder URLs exists.

Usage:
    python scripts/evidence/verify_provenance.py [--raw-root _scratch/w1/raw]
                                                 [--evidence-root data/evidence]
                                                 [--quiet]

Exit code 0 = clean; 1 = errors found (each printed with file:line).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
CLASSES = {
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
EVIDENCE_ID_RE = re.compile(r"^ev_[a-z]{2,3}_\d{4}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://[^\s]+$")
SUSPECT_URL_RE = re.compile(
    r"(example\.(com|org|net)|localhost|127\.0\.0\.1|todo|placeholder|your[-_]?domain)",
    re.IGNORECASE,
)
METRIC_KEYS = {
    "hn_points",
    "hn_comments",
    "github_reactions",
    "github_comments",
    "reddit_upvotes",
    "reddit_comments",
    "citations",
    "stars",
}


def load_raw_candidates(raw_root: Path) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Return source_url -> candidate dict from all normalized raw dumps."""
    candidates: Dict[str, Dict[str, Any]] = {}
    files: List[str] = []
    for path in sorted(raw_root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"FATAL: cannot read raw dump {path}: {exc}")
        if not isinstance(data, dict) or "candidates" not in data:
            continue
        files.append(str(path.relative_to(ROOT)))
        for candidate in data.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            url = candidate.get("source_url")
            if isinstance(url, str) and url:
                candidates.setdefault(url, candidate)
    return candidates, files


def load_evidence(evidence_root: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(evidence_root.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"FATAL: {path}:{lineno}: invalid JSON: {exc}")
                record["_file"] = path.name
                record["_line"] = lineno
                record["_stem"] = path.stem
                records.append(record)
    return records


def verify(records: List[Dict[str, Any]], candidates: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: Dict[str, str] = {}
    seen_urls: Dict[str, str] = {}
    for record in records:
        where = f"{record['_file']}:{record['_line']}"
        rid = record.get("id")
        cls = record.get("class")
        # --- identity / file consistency ---------------------------------
        if not isinstance(rid, str) or not EVIDENCE_ID_RE.match(rid):
            errors.append(f"{where}: bad evidence id {rid!r}")
        elif rid in seen_ids:
            errors.append(f"{where}: duplicate id {rid} (also {seen_ids[rid]})")
        else:
            seen_ids[rid] = where
        if cls not in CLASSES:
            errors.append(f"{where}: unknown class {cls!r}")
        elif isinstance(rid, str) and not rid.startswith(f"ev_{CLASSES[cls]}_"):
            errors.append(f"{where}: id {rid} does not match class {cls}")
        if record["_stem"] != cls:
            errors.append(f"{where}: file {record['_file']} does not match class {cls}")
        # --- contract fields ---------------------------------------------
        url = record.get("source_url")
        if not isinstance(url, str) or not URL_RE.match(url):
            errors.append(f"{where}: source_url missing or not http(s)")
        elif SUSPECT_URL_RE.search(url):
            errors.append(f"{where}: non-primary/suspect source_url {url}")
        elif url in seen_urls:
            errors.append(f"{where}: duplicate source_url (also {seen_urls[url]}) {url}")
        else:
            seen_urls[url] = where
        if record.get("status") != "cited":
            errors.append(f"{where}: status must be 'cited', got {record.get('status')!r}")
        if record.get("collected_at") != "2026-11-24":
            errors.append(f"{where}: collected_at must be 2026-11-24, got {record.get('collected_at')!r}")
        collected_by = record.get("collected_by")
        if not isinstance(collected_by, str) or not collected_by.startswith("W1/"):
            errors.append(f"{where}: collected_by must start with 'W1/'")
        title = record.get("title")
        if not isinstance(title, str) or not (5 <= len(title) <= 200):
            errors.append(f"{where}: title must be 5-200 chars")
        summary = record.get("summary")
        if not isinstance(summary, str) or not (10 <= len(summary) <= 400):
            errors.append(f"{where}: summary must be 10-400 chars")
        quote = record.get("quote")
        if not isinstance(quote, str):
            errors.append(f"{where}: quote must be a string")
        elif len(quote) > 200:
            errors.append(f"{where}: quote > 200 chars")
        published = record.get("published_date")
        if published is not None and (not isinstance(published, str) or not DATE_RE.match(published)):
            errors.append(f"{where}: published_date must be YYYY-MM-DD or null")
        metrics = record.get("metrics")
        if metrics is not None:
            if not isinstance(metrics, dict):
                errors.append(f"{where}: metrics must be an object")
            else:
                for key, value in metrics.items():
                    if key not in METRIC_KEYS:
                        errors.append(f"{where}: unsupported metric key {key}")
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        errors.append(f"{where}: metric {key} must be a non-negative int")
        if record.get("probe_ids") != []:
            errors.append(f"{where}: probe_ids must be [] during collection")
        # --- provenance against the raw API dumps ------------------------
        candidate = candidates.get(url) if isinstance(url, str) else None
        if candidate is None:
            errors.append(
                f"{where}: source_url NOT FOUND in any raw API dump (possible fabrication): {url}"
            )
            continue
        dump = candidate
        if record.get("source_title") != dump.get("source_title"):
            errors.append(
                f"{where}: source_title mismatch: evidence={record.get('source_title')!r} "
                f"api={dump.get('source_title')!r}"
            )
        if record.get("source_type") != dump.get("source_type"):
            errors.append(
                f"{where}: source_type mismatch: evidence={record.get('source_type')!r} "
                f"api={dump.get('source_type')!r}"
            )
        if record.get("publisher") != dump.get("publisher"):
            errors.append(
                f"{where}: publisher mismatch: evidence={record.get('publisher')!r} "
                f"api={dump.get('publisher')!r}"
            )
        if record.get("published_date") != dump.get("published_date"):
            errors.append(
                f"{where}: published_date mismatch: evidence={record.get('published_date')!r} "
                f"api={dump.get('published_date')!r}"
            )
        api_metrics = dump.get("metrics") or {}
        ev_metrics = metrics or {}
        if ev_metrics != api_metrics:
            errors.append(
                f"{where}: metrics mismatch: evidence={ev_metrics!r} api={api_metrics!r}"
            )
        source_type = record.get("source_type")
        if source_type == "arxiv":
            abstract = dump.get("_abstract") or ""
            if not isinstance(quote, str) or not (20 <= len(quote) <= 200):
                errors.append(f"{where}: arxiv quote must be 20-200 chars, got {len(quote or '')}")
            elif quote not in abstract:
                errors.append(f"{where}: arxiv quote is not a verbatim substring of the API abstract")
        elif quote != "":
            errors.append(f"{where}: non-arXiv quote must be \"\", got {quote[:40]!r}...")
        if record.get("title") == record.get("source_title"):
            warnings.append(f"{where}: title equals source_title (paraphrase expected)")
        notes = record.get("notes")
        if notes is not None and (not isinstance(notes, str) or len(notes) > 300):
            warnings.append(f"{where}: notes should be a short string")
    return errors, warnings


def check_index(records: List[Dict[str, Any]], evidence_root: Path) -> List[str]:
    index_path = evidence_root / "index.json"
    if not index_path.exists():
        return [f"{index_path}: index.json is missing"]
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{index_path}: invalid JSON: {exc}"]
    problems: List[str] = []
    if index.get("total") != len(records):
        problems.append(f"index.total={index.get('total')} does not match {len(records)} records")
    by_class = index.get("by_class") or {}
    for cls in CLASSES:
        expected = sum(1 for record in records if record.get("class") == cls)
        got = (by_class.get(cls) or {}).get("count")
        if got != expected:
            problems.append(f"index.by_class[{cls}].count={got} does not match {expected}")
        hn_points = sum(
            int((record.get("metrics") or {}).get("hn_points", 0) or 0)
            for record in records
            if record.get("class") == cls
        )
        got_points = (by_class.get(cls) or {}).get("hn_points")
        if got_points != hn_points:
            problems.append(f"index.by_class[{cls}].hn_points={got_points} does not match {hn_points}")
        github_reactions = sum(
            int((record.get("metrics") or {}).get("github_reactions", 0) or 0)
            for record in records
            if record.get("class") == cls
        )
        got_reactions = (by_class.get(cls) or {}).get("github_reactions")
        if got_reactions != github_reactions:
            problems.append(
                f"index.by_class[{cls}].github_reactions={got_reactions} does not match {github_reactions}"
            )
    actual_sources: Dict[str, int] = {}
    for record in records:
        source_type = record.get("source_type")
        actual_sources[source_type] = actual_sources.get(source_type, 0) + 1
    if index.get("sources") != actual_sources:
        problems.append(f"index.sources={index.get('sources')} does not match {actual_sources}")
    if not isinstance(index.get("generated_at"), str):
        problems.append("index.generated_at missing")
    return problems


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default="_scratch/w1/raw", help="raw API dump root")
    parser.add_argument("--evidence-root", default="data/evidence", help="evidence dir")
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    args = parser.parse_args(argv)

    raw_root = (ROOT / args.raw_root).resolve()
    evidence_root = (ROOT / args.evidence_root).resolve()
    candidates, dump_files = load_raw_candidates(raw_root)
    records = load_evidence(evidence_root)
    errors, warnings = verify(records, candidates)
    errors.extend(check_index(records, evidence_root))

    if not args.quiet:
        for warning in warnings:
            print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(
        f"records={len(records)} raw_dumps={len(dump_files)} api_candidates={len(candidates)} "
        f"errors={len(errors)} warnings={len(warnings)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
