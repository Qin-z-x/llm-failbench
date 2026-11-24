"""Shared offline fixtures and helpers for the FailBench test suite.

Everything in this module is synthetic test material (``example.org`` URLs and
fixture probes live only under temporary directories). Nothing here is part of
the shipped corpus and no network access is performed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Imported here so tests and fixtures share the authoritative vocabulary.
from failbench.schema import CLASS_ABBR, CLASSES  # noqa: E402  (path setup is implicit)

#: One valid probe id per failure class (matches <abbr>_<slug>_<2 digits>).
FIXTURE_IDS: Dict[str, str] = {
    "hallucination": "hal_fixture_01",
    "instruction_following": "if_fixture_01",
    "context_retrieval": "ctx_fixture_01",
    "reasoning_consistency": "rea_fixture_01",
    "sycophancy": "syc_fixture_01",
    "structured_output": "str_fixture_01",
    "multilingual": "ml_fixture_01",
    "safety_consistency": "saf_fixture_01",
    "agentic_reliability": "agt_fixture_01",
    "determinism_calibration": "det_fixture_01",
}


# ---------------------------------------------------------------------------
# Probe fixtures
# ---------------------------------------------------------------------------

def make_probe(
    probe_id: str,
    cls: str,
    *,
    title: Optional[str] = None,
    severity: str = "high",
    scoring: Optional[Dict[str, Any]] = None,
    prompt: Optional[List[Dict[str, str]]] = None,
    repeats: int = 1,
    params: Optional[Dict[str, Any]] = None,
    rationale: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a schema-valid probe record suitable for offline tests."""
    if cls not in CLASSES:
        raise ValueError("unknown class: {0!r}".format(cls))
    probe: Dict[str, Any] = {
        "id": probe_id,
        "class": cls,
        "title": title or "Fixture probe {0} for offline unit tests".format(probe_id),
        "severity": severity,
        "rationale": rationale
        or "Fixture rationale that is long enough to satisfy the schema minimum.",
        "evidence_ids": [],
        "prompt": prompt
        or [{"role": "user", "content": "Reply with the single word OK."}],
        "params": params if params is not None else {"temperature": 0, "max_tokens": 64},
        "repeats": repeats,
        "scoring": scoring or {"type": "contains_all", "value": ["OK"]},
        "tags": tags if tags is not None else ["fixture"],
        "notes": notes if notes is not None else "Offline fixture probe; not part of the corpus.",
    }
    return probe


def make_all_class_probes() -> List[Dict[str, Any]]:
    """Return one schema-valid probe per failure class (10 probes)."""
    probes: List[Dict[str, Any]] = []
    for cls in CLASSES:
        probe_id = FIXTURE_IDS[cls]
        probes.append(
            make_probe(
                probe_id,
                cls,
                scoring={"type": "exact_match", "value": "OK"},
            )
        )
    return probes


def write_probes(directory: Any, probes: Iterable[Dict[str, Any]]) -> Path:
    """Write probes to ``<directory>/<class>/<id>.json`` and return directory."""
    root = Path(directory)
    for probe in probes:
        cls = probe.get("class")
        target = root / str(cls) / "{0}.json".format(probe["id"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(probe, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return root


# ---------------------------------------------------------------------------
# Evidence fixtures (only needed by strict-validation tests)
# ---------------------------------------------------------------------------

def make_evidence(ev_id: str, cls: str, **overrides: Any) -> Dict[str, Any]:
    """Return a schema-valid synthetic evidence record for offline tests."""
    record: Dict[str, Any] = {
        "id": ev_id,
        "class": cls,
        "title": "Fixture evidence record for offline unit tests",
        "source_type": "arxiv",
        "source_url": "https://example.org/fixture",
        "source_title": "Fixture source title (synthetic)",
        "publisher": "Example",
        "published_date": None,
        "metrics": {"citations": 1},
        "quote": "",
        "summary": "Synthetic fixture evidence used only by unit tests; not real evidence.",
        "status": "cited",
        "probe_ids": [],
        "collected_by": "W3 test fixture",
        "collected_at": "2026-01-01",
    }
    record.update(overrides)
    return record


def write_evidence(directory: Any, records: Iterable[Dict[str, Any]]) -> Path:
    """Write evidence records to ``<directory>/<class>.jsonl``."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("class")), []).append(record)
    for cls, items in grouped.items():
        target = root / "{0}.jsonl".format(cls)
        lines = [json.dumps(item, ensure_ascii=False) for item in items]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def make_all_class_evidence() -> List[Dict[str, Any]]:
    """Return one schema-valid evidence record per failure class (10 records)."""
    records: List[Dict[str, Any]] = []
    for index, (cls, abbr) in enumerate(sorted(CLASSES.items()), start=1):
        records.append(make_evidence("ev_{0}_{1:04d}".format(abbr, index), cls))
    return records


# ---------------------------------------------------------------------------
# CLI / subprocess helpers
# ---------------------------------------------------------------------------

def run_cli(
    args: Sequence[Any],
    *,
    cwd: Optional[Any] = None,
    timeout: float = 120.0,
    env_extra: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Run ``python -m failbench <args>`` offline and capture output.

    The repository root is put on ``PYTHONPATH`` so the command works from any
    current directory; ``OPENAI_API_KEY`` and friends are scrubbed so no test
    can accidentally depend on a real key.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "FAILBENCH_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        env.pop(key, None)
    if env_extra:
        env.update(env_extra)
    command = [PYTHON, "-m", "failbench"] + [str(arg) for arg in args]
    return subprocess.run(
        command,
        cwd=str(Path(cwd) if cwd is not None else ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Results-document fixtures (gate tests and CLI tests)
# ---------------------------------------------------------------------------

def make_results_doc(
    entries: Iterable[Dict[str, Any]],
    *,
    run_id: str = "20260101T000000Z-mock",
    provider: str = "mock",
    model: str = "failbench-mock-1",
) -> Dict[str, Any]:
    """Build a contract-shaped ``results.json`` document from simple entries.

    ``entries`` items need ``probe_id``, ``class`` and ``status``
    (``pass|fail|error``); optional ``reason``, ``severity``, ``title``.
    """
    from failbench.schema import CLASSES as _CLASSES

    class_order = {name: index for index, name in enumerate(_CLASSES)}
    probes: List[Dict[str, Any]] = []
    counts = {"probes": 0, "pass": 0, "fail": 0, "error": 0}
    by_class: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        status = str(entry["status"])
        if status not in ("pass", "fail", "error"):
            raise ValueError("bad fixture status: {0!r}".format(status))
        cls = str(entry["class"])
        probe_id = str(entry["probe_id"])
        counts["probes"] += 1
        counts[status] += 1
        bucket = by_class.setdefault(
            cls, {"total": 0, "pass": 0, "fail": 0, "error": 0, "pass_rate": 0.0}
        )
        bucket["total"] += 1
        bucket[status] += 1
        probes.append(
            {
                "probe_id": probe_id,
                "class": cls,
                "title": entry.get("title", "Fixture probe {0}".format(probe_id)),
                "severity": entry.get("severity", "high"),
                "status": status,
                "reason": entry.get("reason", "fixture"),
                "latency_ms": int(entry.get("latency_ms", 1)),
                "tokens": {"prompt": 0, "completion": 0},
                "response_sha256": entry.get("response_sha256", "0" * 64),
                "response_excerpt": entry.get("response_excerpt", "fixture"),
                "attempts": [
                    {
                        "index": 0,
                        "status": status,
                        "reason": entry.get("reason", "fixture"),
                        "response_sha256": entry.get("response_sha256", "0" * 64),
                        "latency_ms": int(entry.get("latency_ms", 1)),
                    }
                ],
            }
        )

    for bucket in by_class.values():
        total = bucket["total"]
        bucket["pass_rate"] = round(bucket["pass"] / total, 4) if total else 0.0

    probes.sort(key=lambda item: (class_order.get(item["class"], 99), item["probe_id"]))
    return {
        "schema": 1,
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "base_url": None,
        "suite_version": "0.2.0",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "environment": {"python": "3.13.15", "platform": "Windows"},
        "config": {"temperature": 0, "max_tokens": 256, "concurrency": 4, "repeats": 1},
        "counts": counts,
        "by_class": by_class,
        "probes": probes,
    }


def write_json(path: Any, payload: Any) -> Path:
    """Write JSON with a trailing newline; returns the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target


def read_json(path: Any) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Any) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip():
            lines.append(json.loads(line))
    return lines
