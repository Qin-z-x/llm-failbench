"""FailBench runner: execute probes against a provider and write auditable results.

Implements CONTRACT sections 7 (results schema) and 8 (CLI ``run`` behaviour):

* loads probes with :func:`failbench.schema.load_probes`,
* executes them concurrently with a ``ThreadPoolExecutor`` (default 4 workers),
* repeats each probe up to ``repeats`` times (CONTRACT section 5), scoring all
  repeats with mechanical rules, and a probe passes only if every repeat passes,
* isolates per-probe failures: a provider/transport problem becomes
  ``status: "error"`` on that probe and never aborts the run (provider errors
  are never scored as model ``fail``, see CONTRACT section 6),
* writes ``results.json`` and ``raw.jsonl`` atomically, with no API keys or
  request headers persisted, and
* prints a progress/summary stream to stdout.

The runner returns the results document and does not choose an exit code: a
run whose probes all fail is still a successful run. ``RunError`` is raised
only when the run itself cannot execute (missing corpus, bad filter, unwritable
output directory).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO, Tuple

from . import __version__
from .providers.base import Provider, ProviderError, probe_messages
from .schema import CLASSES, PROBES_DIR, load_probes
from .scoring import score, score_probe_scoring

#: Default number of concurrent probe executions (CONTRACT section 8).
DEFAULT_CONCURRENCY = 4
#: Default provider HTTP timeout in seconds (used by the CLI for ``openai``).
DEFAULT_TIMEOUT = 60.0
#: Default provider retry count (used by the CLI for ``openai``).
DEFAULT_RETRIES = 2

#: Deterministic output ordering: contract class order, then probe id.
_CLASS_ORDER: Dict[str, int] = {name: index for index, name in enumerate(CLASSES)}


class RunError(Exception):
    """The run could not be executed at all (bad corpus/filter/output dir).

    Per-probe failures are *not* run errors: they are recorded in the results
    document with ``status: "error"``.
    """


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def utc_now() -> str:
    """Current UTC timestamp as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_run_id(provider_name: str, now: Optional[datetime] = None) -> str:
    """Return ``YYYYMMDDTHHMMSSZ-<provider>`` (CONTRACT section 7 style)."""
    moment = now or datetime.now(timezone.utc)
    return "{0}-{1}".format(moment.strftime("%Y%m%dT%H%M%SZ"), provider_name)


def sha256_text(text: Any) -> str:
    """Hex SHA-256 of a response text (``""`` for missing responses)."""
    value = "" if text is None else str(text)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(text: Any, limit: int = 500) -> str:
    """Single-line response excerpt, at most ``limit`` characters."""
    if text is None:
        return ""
    value = str(text).replace("\r", " ").replace("\n", " ")
    return value if len(value) <= limit else value[:limit]


def _truncate(text: Any, limit: int = 300) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").replace("\n", " ")
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (same-directory temp + replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(path))
    except BaseException:
        try:
            temp_path.unlink()
        except OSError:  # pragma: no cover - best effort cleanup
            pass
        raise


def probe_sort_key(probe: Dict[str, Any]) -> Tuple[int, str]:
    """Deterministic probe ordering: contract class order then probe id."""
    class_name = str(probe.get("class", ""))
    return (_CLASS_ORDER.get(class_name, len(CLASSES)), str(probe.get("id", "")))


def select_probes(
    probes: Sequence[Dict[str, Any]],
    class_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Filter/sort probes for a run. Raises :class:`RunError` for bad filters."""
    if class_filter is not None and class_filter not in CLASSES:
        raise RunError(
            "unknown class {0!r}; expected one of: {1}".format(
                class_filter, ", ".join(CLASSES)
            )
        )
    if limit is not None:
        try:
            limit_value = int(limit)
        except (TypeError, ValueError):
            raise RunError("limit must be a non-negative integer")
        if limit_value < 0:
            raise RunError("limit must be a non-negative integer")
    else:
        limit_value = None

    selected = [
        probe
        for probe in probes
        if class_filter is None or probe.get("class") == class_filter
    ]
    selected.sort(key=probe_sort_key)
    if limit_value is not None:
        selected = selected[:limit_value]
    return selected


def effective_repeats(probe: Dict[str, Any], repeats_override: Optional[int]) -> int:
    """Effective repeat count for a probe, clamped to the contract's 1..5."""
    raw_value: Any = repeats_override
    if raw_value is None:
        raw_value = probe.get("repeats", 1)
    try:
        repeats = int(raw_value)
    except (TypeError, ValueError):
        repeats = 1
    return max(1, min(5, repeats))


# ---------------------------------------------------------------------------
# One probe
# ---------------------------------------------------------------------------

def execute_probe(
    probe: Dict[str, Any],
    provider: Provider,
    repeats: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute one probe ``repeats`` times and return (probe_entry, raw_lines).

    All provider/transport failures are captured as per-attempt ``"error"``
    records; this function never raises for a provider problem.
    """
    probe_id = str(probe.get("id", "?"))
    class_name = str(probe.get("class", "unknown"))
    model = str(getattr(provider, "model", "") or "")
    request_params = probe.get("params")
    request = {
        "model": model,
        "messages": probe_messages(probe),
        "params": dict(request_params) if isinstance(request_params, dict) else {},
    }

    texts: List[str] = []
    text_by_attempt: Dict[int, str] = {}
    attempt_records: List[Dict[str, Any]] = []
    raw_lines: List[Dict[str, Any]] = []
    errors: List[Tuple[int, str]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_latency = 0

    for index in range(repeats):
        timestamp = utc_now()
        started = time.monotonic()
        try:
            response = provider.complete_with_retry(probe, attempt=index)
        except ProviderError as exc:
            message = provider.redact(str(exc)) if hasattr(provider, "redact") else str(exc)
            latency = int((time.monotonic() - started) * 1000)
            total_latency += latency
            errors.append((index, message))
            attempt_records.append(
                {
                    "index": index,
                    "status": "error",
                    "reason": _truncate(message),
                    "response_sha256": sha256_text(""),
                    "latency_ms": latency,
                }
            )
            raw_lines.append(
                {
                    "probe_id": probe_id,
                    "attempt": index,
                    "request": request,
                    "response": None,
                    "error": _truncate(message, 1000),
                    "latency_ms": latency,
                    "timestamp": timestamp,
                }
            )
        except Exception as exc:  # defensive: never let a provider bug kill the run
            message = "unexpected provider error: {0}: {1}".format(
                type(exc).__name__, exc
            )
            latency = int((time.monotonic() - started) * 1000)
            total_latency += latency
            errors.append((index, message))
            attempt_records.append(
                {
                    "index": index,
                    "status": "error",
                    "reason": _truncate(message),
                    "response_sha256": sha256_text(""),
                    "latency_ms": latency,
                }
            )
            raw_lines.append(
                {
                    "probe_id": probe_id,
                    "attempt": index,
                    "request": request,
                    "response": None,
                    "error": _truncate(message, 1000),
                    "latency_ms": latency,
                    "timestamp": timestamp,
                }
            )
        else:
            text = response.text or ""
            texts.append(text)
            text_by_attempt[index] = text
            prompt_tokens = int(response.prompt_tokens or 0)
            completion_tokens = int(response.completion_tokens or 0)
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            measured = int((time.monotonic() - started) * 1000)
            latency = int(response.latency_ms or measured)
            total_latency += latency
            attempt_records.append(
                {
                    "index": index,
                    "status": None,  # filled in by scoring below
                    "reason": "",
                    "response_sha256": sha256_text(text),
                    "latency_ms": latency,
                }
            )
            raw_lines.append(
                {
                    "probe_id": probe_id,
                    "attempt": index,
                    "request": request,
                    "response": {
                        "text": text,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                    },
                    "error": None,
                    "latency_ms": latency,
                    "timestamp": timestamp,
                }
            )

    primary_text = texts[0] if texts else ""
    primary_sha = attempt_records[0]["response_sha256"] if attempt_records else sha256_text("")

    if errors:
        status = "error"
        reason = "provider error: " + _truncate(errors[0][1], 280)
        # Successful repeats of an errored probe still receive their mechanical
        # pass/fail verdicts so per-attempt statuses are never null.
        scoring_spec = probe.get("scoring")
        for index, record in enumerate(attempt_records):
            if record["status"] == "error":
                continue
            try:
                passed_attempt, detail_attempt = score(
                    scoring_spec, text_by_attempt.get(index, "")
                )
            except Exception as exc:  # pragma: no cover - malformed corpus spec
                passed_attempt, detail_attempt = False, "scoring failed: {0}".format(exc)
            record["status"] = "pass" if passed_attempt else "fail"
            record["reason"] = _truncate(detail_attempt)
    else:
        scoring_spec = probe.get("scoring")
        try:
            passed, scored_attempts = score_probe_scoring(scoring_spec, texts)
        except Exception as exc:  # malformed corpus entry: report as error, not fail
            status = "error"
            reason = "scoring failed: {0}: {1}".format(type(exc).__name__, exc)
            for record in attempt_records:
                record["status"] = "error"
                record["reason"] = _truncate(reason)
        else:
            for position, scored in enumerate(scored_attempts):
                if position >= len(attempt_records):  # pragma: no cover - defensive
                    break
                attempt_records[position]["status"] = (
                    "pass" if scored.get("passed") else "fail"
                )
                attempt_records[position]["reason"] = _truncate(
                    scored.get("detail", "")
                )
            if passed:
                status = "pass"
                detail = _truncate(
                    scored_attempts[0].get("detail", "") if scored_attempts else ""
                )
                reason = (
                    detail
                    if repeats == 1
                    else "all {0} repeat(s) passed: {1}".format(repeats, detail)
                )
            else:
                status = "fail"
                failing = [
                    item
                    for item in scored_attempts
                    if not item.get("passed")
                ]
                detail = _truncate(failing[0].get("detail", "")) if failing else ""
                reason = detail or "scoring condition not met"

    entry: Dict[str, Any] = {
        "probe_id": probe_id,
        "class": class_name,
        "title": str(probe.get("title", "")),
        "severity": str(probe.get("severity", "unknown")),
        "status": status,
        "reason": _truncate(reason),
        "latency_ms": total_latency,
        "tokens": {
            "prompt": total_prompt_tokens,
            "completion": total_completion_tokens,
        },
        "response_sha256": primary_sha,
        "response_excerpt": _excerpt(primary_text),
        "attempts": attempt_records,
    }
    return entry, raw_lines


def _synthetic_error_entry(
    probe: Dict[str, Any], exc: BaseException
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Last-resort entry builder so a runner bug can never abort the whole run."""
    probe_id = str(probe.get("id", "?"))
    message = "runner internal error: {0}: {1}".format(type(exc).__name__, exc)
    timestamp = utc_now()
    entry: Dict[str, Any] = {
        "probe_id": probe_id,
        "class": str(probe.get("class", "unknown")),
        "title": str(probe.get("title", "")),
        "severity": str(probe.get("severity", "unknown")),
        "status": "error",
        "reason": _truncate(message),
        "latency_ms": 0,
        "tokens": {"prompt": 0, "completion": 0},
        "response_sha256": sha256_text(""),
        "response_excerpt": "",
        "attempts": [
            {
                "index": 0,
                "status": "error",
                "reason": _truncate(message),
                "response_sha256": sha256_text(""),
                "latency_ms": 0,
            }
        ],
    }
    raw_line = {
        "probe_id": probe_id,
        "attempt": 0,
        "request": {
            "model": "",
            "messages": probe_messages(probe),
            "params": dict(probe.get("params") or {}),
        },
        "response": None,
        "error": _truncate(message, 1000),
        "latency_ms": 0,
        "timestamp": timestamp,
    }
    return entry, [raw_line]


# ---------------------------------------------------------------------------
# Whole suite
# ---------------------------------------------------------------------------

def _aggregate(entries: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    counts: Dict[str, Any] = {"probes": 0, "pass": 0, "fail": 0, "error": 0}
    by_class: Dict[str, Dict[str, Any]] = {}
    order: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status"))
        if status not in ("pass", "fail", "error"):  # pragma: no cover - defensive
            status = "error"
        class_name = str(entry.get("class", "unknown"))
        counts["probes"] += 1
        counts[status] += 1
        bucket = by_class.get(class_name)
        if bucket is None:
            bucket = {"total": 0, "pass": 0, "fail": 0, "error": 0, "pass_rate": 0.0}
            by_class[class_name] = bucket
            order[class_name] = _CLASS_ORDER.get(class_name, len(CLASSES))
        bucket["total"] += 1
        bucket[status] += 1
    for class_name, bucket in by_class.items():
        total = bucket["total"]
        bucket["pass_rate"] = round(bucket["pass"] / total, 4) if total else 0.0
    ordered = {
        class_name: by_class[class_name]
        for class_name in sorted(by_class, key=lambda name: order[name])
    }
    return counts, ordered


def run_suite(
    probes: Sequence[Dict[str, Any]],
    provider: Provider,
    out_dir: Any,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    class_filter: Optional[str] = None,
    limit: Optional[int] = None,
    repeats_override: Optional[int] = None,
    run_id: Optional[str] = None,
    progress: bool = True,
    stream: Optional[TextIO] = None,
) -> Dict[str, Any]:
    """Execute an already-loaded probe list and write results to ``out_dir``.

    Returns the results document (CONTRACT section 7). Raises
    :class:`RunError` only when the run itself cannot execute.
    """
    stream = stream if stream is not None else sys.stdout
    selected = select_probes(probes, class_filter=class_filter, limit=limit)
    if not selected:
        target = PROBES_DIR
        raise RunError(
            "no probes to run under {0}{1}".format(
                target,
                " for class {0!r}".format(class_filter) if class_filter else "",
            )
        )

    try:
        workers = max(1, int(concurrency))
    except (TypeError, ValueError):
        raise RunError("concurrency must be a positive integer")

    output_dir = Path(out_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RunError(
            "cannot create output directory {0}: {1}".format(output_dir, exc)
        )

    provider_name = str(getattr(provider, "name", "unknown"))
    run_identifier = run_id or build_run_id(provider_name)
    started_at = utc_now()
    if progress:
        print(
            "FailBench run: {0} probe(s), provider={1}, model={2}, "
            "concurrency={3}, out={4}".format(
                len(selected),
                provider_name,
                getattr(provider, "model", ""),
                workers,
                output_dir,
            ),
            file=stream,
            flush=True,
        )

    clock_started = time.monotonic()
    total = len(selected)
    entries_in_order: List[Optional[Dict[str, Any]]] = [None] * total
    raw_in_order: List[List[Dict[str, Any]]] = [[] for _ in range(total)]

    def job(position: int, probe: Dict[str, Any]) -> Tuple[int, Dict[str, Any], List[Dict[str, Any]]]:
        repeats = effective_repeats(probe, repeats_override)
        try:
            entry, lines = execute_probe(probe, provider, repeats)
        except Exception as exc:  # pragma: no cover - defensive isolation
            entry, lines = _synthetic_error_entry(probe, exc)
        return position, entry, lines

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(job, position, probe)
            for position, probe in enumerate(selected)
        ]
        try:
            for future in as_completed(futures):
                position, entry, lines = future.result()
                entries_in_order[position] = entry
                raw_in_order[position] = lines
                completed += 1
                if progress:
                    print(
                        "[{0}/{1}] {2:<5} {3} ({4} ms)".format(
                            completed,
                            total,
                            entry["status"],
                            entry["probe_id"],
                            entry["latency_ms"],
                        ),
                        file=stream,
                        flush=True,
                    )
        except KeyboardInterrupt:  # pragma: no cover - operator abort
            for future in futures:
                future.cancel()
            raise

    entries: List[Dict[str, Any]] = []
    for position in range(total):
        entry = entries_in_order[position]
        if entry is None:  # pragma: no cover - defensive
            entry, _lines = _synthetic_error_entry(
                selected[position], RuntimeError("probe did not complete")
            )
        entries.append(entry)

    counts, by_class = _aggregate(entries)
    finished_at = utc_now()
    results: Dict[str, Any] = {
        "schema": 1,
        "run_id": run_identifier,
        "provider": provider_name,
        "model": str(getattr(provider, "model", "")),
        "base_url": getattr(provider, "base_url", None),
        "suite_version": __version__,
        "started_at": started_at,
        "finished_at": finished_at,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
        },
        "config": {
            "temperature": 0,
            "max_tokens": 256,
            "concurrency": workers,
            "repeats": int(repeats_override) if repeats_override is not None else 1,
        },
        "counts": counts,
        "by_class": by_class,
        "probes": entries,
    }

    raw_lines: List[Dict[str, Any]] = []
    for lines in raw_in_order:
        raw_lines.extend(lines)
    raw_text = "".join(
        json.dumps(line, ensure_ascii=False) + "\n" for line in raw_lines
    )
    results_text = json.dumps(results, indent=2, ensure_ascii=False) + "\n"

    try:
        _atomic_write_text(output_dir / "raw.jsonl", raw_text)
        _atomic_write_text(output_dir / "results.json", results_text)
    except OSError as exc:
        raise RunError(
            "cannot write results to {0}: {1}".format(output_dir, exc)
        )

    elapsed = time.monotonic() - clock_started
    if progress:
        pass_rate = (
            (100.0 * counts["pass"] / counts["probes"]) if counts["probes"] else 0.0
        )
        print(
            "Summary: {0} probe(s): {1} pass ({2:.1f}%), {3} fail, {4} error".format(
                counts["probes"],
                counts["pass"],
                pass_rate,
                counts["fail"],
                counts["error"],
            ),
            file=stream,
            flush=True,
        )
        print(
            "Wrote {0}".format(output_dir / "results.json"),
            file=stream,
            flush=True,
        )
        print(
            "Wrote {0}".format(output_dir / "raw.jsonl"),
            file=stream,
            flush=True,
        )
        print("Elapsed: {0:.2f}s".format(elapsed), file=stream, flush=True)

    return results


def run_from_paths(
    *,
    out_dir: Any,
    provider: Provider,
    probes_dir: Any = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    class_filter: Optional[str] = None,
    limit: Optional[int] = None,
    repeats_override: Optional[int] = None,
    progress: bool = True,
    stream: Optional[TextIO] = None,
) -> Dict[str, Any]:
    """Load probes from disk and run the suite (CLI ``run`` entry point)."""
    probes_root = Path(probes_dir) if probes_dir is not None else None
    try:
        probes = load_probes(probes_root)
    except ValueError as exc:
        raise RunError("failed to load probes: {0}".format(exc))
    if not probes:
        shown = probes_root if probes_root is not None else PROBES_DIR
        raise RunError("no probes found under {0}".format(shown))
    return run_suite(
        probes,
        provider,
        out_dir,
        concurrency=concurrency,
        class_filter=class_filter,
        limit=limit,
        repeats_override=repeats_override,
        progress=progress,
        stream=stream,
    )


__all__ = [
    "DEFAULT_CONCURRENCY",
    "DEFAULT_RETRIES",
    "DEFAULT_TIMEOUT",
    "RunError",
    "build_run_id",
    "effective_repeats",
    "execute_probe",
    "probe_sort_key",
    "run_from_paths",
    "run_suite",
    "select_probes",
    "sha256_text",
    "utc_now",
]
