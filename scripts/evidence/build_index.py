#!/usr/bin/env python3
"""Rebuild ``data/evidence/index.json`` from the evidence JSONL files.

The index is a derived artifact: counts always come from the files on disk, so
it is safe to re-run at any time (e.g. after adding evidence):

    python scripts/evidence/build_index.py

Output shape (see docs/CONTRACT.md section 4 and the W1 deliverables):

    {
      "generated_at": "2026-11-24T02:30:00Z",
      "total": 108,
      "by_class": {
        "hallucination": {"count": 11, "hn_points": 4210,
                          "github_reactions": 0, "citations_known": 0},
        ...
      },
      "sources": {"hn_story": 60, "arxiv": 40, "github_issue": 8}
    }

``citations_known`` stays 0 because the collectors only record arXiv metadata;
no citation counts were fetched, so no citation metric may be claimed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "data" / "evidence"
INDEX_PATH = EVIDENCE_DIR / "index.json"

CLASSES: List[str] = [
    "hallucination",
    "instruction_following",
    "context_retrieval",
    "reasoning_consistency",
    "sycophancy",
    "structured_output",
    "multilingual",
    "safety_consistency",
    "agentic_reliability",
    "determinism_calibration",
]


def load_records() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(EVIDENCE_DIR.glob("*.jsonl")):
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
                records.append(record)
    return records


def build_index(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, Dict[str, Any]] = {
        cls: {"count": 0, "hn_points": 0, "github_reactions": 0, "citations_known": 0}
        for cls in CLASSES
    }
    sources: Dict[str, int] = {}
    for record in records:
        cls = record.get("class")
        if cls not in by_class:
            raise SystemExit(f"FATAL: record {record.get('id')!r} has unknown class {cls!r}")
        bucket = by_class[cls]
        bucket["count"] += 1
        metrics = record.get("metrics") or {}
        bucket["hn_points"] += int(metrics.get("hn_points", 0) or 0)
        bucket["github_reactions"] += int(metrics.get("github_reactions", 0) or 0)
        bucket["citations_known"] += int(metrics.get("citations", 0) or 0)
        source_type = record.get("source_type")
        if not isinstance(source_type, str) or not source_type:
            raise SystemExit(f"FATAL: record {record.get('id')!r} has no source_type")
        sources[source_type] = sources.get(source_type, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(records),
        "by_class": by_class,
        "sources": dict(sorted(sources.items())),
    }


def main() -> int:
    records = load_records()
    index = build_index(records)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as handle:
        json.dump(index, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"wrote {INDEX_PATH} total={index['total']} sources={index['sources']}")
    for cls in CLASSES:
        print(f"  {cls}: {index['by_class'][cls]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
