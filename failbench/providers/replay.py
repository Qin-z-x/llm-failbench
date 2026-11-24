"""Offline replay of recorded FailBench runs (stdlib only).

Replays the ``raw.jsonl`` file written by :mod:`failbench.runner` (CONTRACT
sections 7-8) so a completed run can be re-scored or audited with **no network
access and no API key**. Two entry points are provided:

* :class:`ReplayProvider` - re-executes the recorded attempts through the normal
  provider interface, so ``python -m failbench run --provider replay`` can replay
  a run through the real runner (e.g. to diff against the original results).
* :func:`replay_recorded` - re-scores a whole recorded run directly, without the
  runner, producing a contract-shaped results document that
  :func:`write_replay_results` persists atomically. This is the path used by
  ``python -m failbench replay --results <run dir>``.

Only recorded assistant text, token counts and latency are copied into replay
artifacts. Recorded request fields are never copied (they could in principle
contain headers or credentials).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import failbench
from failbench.schema import CLASSES
from failbench.scoring import score

from .base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    ProviderResponse,
)

__all__ = [
    "ReplayError",
    "ReplayProvider",
    "compare_statuses",
    "group_attempts",
    "load_raw_records",
    "replay_recorded",
    "resolve_raw_path",
    "write_replay_results",
]

RAW_FILENAME = "raw.jsonl"
RESULTS_FILENAME = "results.json"
REPLAY_FILENAME = "replay-results.json"

MISSING_PROBE_REASON = "probe record not found in current probes/ corpus"
_MAX_REASON = 300
_MAX_EXCERPT = 500


class ReplayError(Exception):
    """Unreadable or structurally invalid recorded run data."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_text(text: str) -> str:
    """Hex SHA-256 of ``text`` encoded as UTF-8 (never raises on str)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short(text: Any, limit: int) -> str:
    """Collapse newlines and truncate to ``limit`` characters."""
    value = "" if text is None else str(text)
    value = value.replace("\r", " ").replace("\n", " ")
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "\u2026"


def _safe_int(value: Any) -> int:
    """Best-effort non-negative int coercion (never raises)."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _response_text(record: Dict[str, Any]) -> str:
    """Assistant text recorded for one attempt (``""`` when absent/null)."""
    response = record.get("response")
    if not isinstance(response, dict):
        return ""
    text = response.get("text")
    if text is None:
        return ""
    return text if isinstance(text, str) else str(text)


def _response_tokens(record: Dict[str, Any], key: str) -> int:
    response = record.get("response")
    if not isinstance(response, dict):
        return 0
    return _safe_int(response.get(key, 0))


def _attempt_index(value: Any) -> Optional[int]:
    """Return ``value`` as an attempt index, or ``None`` when invalid."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


# ---------------------------------------------------------------------------
# Loading recorded data
# ---------------------------------------------------------------------------

def resolve_raw_path(results: Any) -> Path:
    """Resolve a results directory or a ``raw.jsonl`` path to the raw file.

    ``results`` may be a :class:`pathlib.Path` or string pointing at a run
    directory containing ``raw.jsonl`` or directly at a ``raw.jsonl`` file.
    Raises :class:`ReplayError` when no such file can be found.
    """
    if results is None:
        raise ReplayError(
            "no raw.jsonl found under None "
            "(pass a results directory or a raw.jsonl path)"
        )
    path = Path(results)
    if path.is_dir():
        candidate = path / RAW_FILENAME
        if candidate.is_file():
            return candidate
        raise ReplayError("no raw.jsonl found under {0}".format(path))
    if path.is_file():
        return path
    raise ReplayError("no raw.jsonl found under {0}".format(path))


def load_raw_records(results: Any) -> List[Dict[str, Any]]:
    """Read every recorded attempt from a run directory or raw file.

    Blank lines are skipped. Records are returned in file order. Raises
    :class:`ReplayError` for unreadable files, invalid JSON (with ``path:line``)
    and structurally invalid records. Recorded request fields are parsed but
    never used by replay artifacts.
    """
    path = resolve_raw_path(results)
    records: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ReplayError(
                        "{0}:{1}: invalid JSON: {2}".format(path, lineno, exc)
                    ) from exc
                if not isinstance(data, dict):
                    raise ReplayError(
                        "{0}:{1}: raw record must be a JSON object".format(path, lineno)
                    )
                probe_id = data.get("probe_id")
                if not isinstance(probe_id, str) or not probe_id:
                    raise ReplayError(
                        "{0}:{1}: probe_id must be a non-empty string".format(
                            path, lineno
                        )
                    )
                if _attempt_index(data.get("attempt")) is None:
                    raise ReplayError(
                        "{0}:{1}: attempt must be a non-negative integer".format(
                            path, lineno
                        )
                    )
                records.append(data)
    except OSError as exc:
        raise ReplayError("{0}: cannot read raw.jsonl: {1}".format(path, exc)) from exc
    except UnicodeDecodeError as exc:  # pragma: no cover - corrupt non-UTF-8 file
        raise ReplayError(
            "{0}: raw.jsonl is not valid UTF-8: {1}".format(path, exc)
        ) from exc
    return records


def group_attempts(
    records: Iterable[Dict[str, Any]],
) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """Group records as ``probe_id -> attempt index -> record``.

    If the same ``(probe_id, attempt)`` pair appears more than once the later
    record wins (a re-written attempt supersedes the older one).
    """
    grouped: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            raise ReplayError(
                "invalid raw record at position {0}: expected an object".format(position)
            )
        probe_id = record.get("probe_id")
        if not isinstance(probe_id, str) or not probe_id:
            raise ReplayError(
                "invalid raw record at position {0}: probe_id must be a non-empty string".format(
                    position
                )
            )
        attempt = _attempt_index(record.get("attempt"))
        if attempt is None:
            raise ReplayError(
                "invalid raw record at position {0}: attempt must be a non-negative integer".format(
                    position
                )
            )
        grouped.setdefault(probe_id, {})[attempt] = record
    return grouped


def _read_sibling_model(raw_path: Path) -> Optional[str]:
    """Best-effort read of ``model`` from ``results.json`` next to the raw file."""
    candidate = raw_path.parent / RESULTS_FILENAME
    if not candidate.is_file():
        return None
    try:
        with open(candidate, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict):
        model = data.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return None


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class ReplayProvider(Provider):
    """Provider that replays recorded ``raw.jsonl`` attempts instead of calling a model.

    Fully offline: constructing and using this provider never opens a socket and
    never needs an API key. Requested probes/attempts that were not recorded, and
    attempts whose recorded ``error`` is not null, raise :class:`ProviderError`
    (the runner then records them as ``status: "error"``, never as a scoring
    ``fail``).
    """

    name = "replay"
    default_model = "replay-recorded"

    def __init__(
        self,
        results: Any = None,
        raw_path: Any = None,
        model: Optional[str] = None,
        **options: Any,
    ) -> None:
        source = raw_path if raw_path is not None else results
        if source is None or (isinstance(source, str) and not source.strip()):
            raise ProviderConfigError(
                "replay provider requires results=<run dir> or raw_path=<raw.jsonl path>"
            )
        resolved = resolve_raw_path(source)
        self.raw_path: Path = resolved
        self.source: str = str(resolved)
        self.records: List[Dict[str, Any]] = load_raw_records(resolved)
        self.attempts: Dict[str, Dict[int, Dict[str, Any]]] = group_attempts(
            self.records
        )
        if model is None:
            model = _read_sibling_model(resolved)
        super().__init__(model=model, **options)

    # -- interface ---------------------------------------------------------
    def complete(
        self, probe: Dict[str, Any], attempt: int = 0
    ) -> ProviderResponse:
        """Return the recorded response for ``probe`` at repeat ``attempt``."""
        probe_id = probe.get("id") if isinstance(probe, dict) else None
        if not isinstance(probe_id, str) or not probe_id:
            raise ProviderError(
                "replay: probe record has no 'id'; cannot look up a recorded attempt",
                retryable=False,
            )
        recorded = self.attempts.get(probe_id, {}).get(attempt)
        if recorded is None:
            raise ProviderError(
                "replay: no recorded attempt {0} for probe {1} in {2}".format(
                    attempt, probe_id, self.source
                ),
                retryable=False,
            )
        error = recorded.get("error")
        if error is not None:
            raise ProviderError(
                "replay: recorded error for probe {0} attempt {1}: {2}".format(
                    probe_id, attempt, error
                ),
                retryable=False,
            )
        response = recorded.get("response")
        if not isinstance(response, dict):
            raise ProviderError(
                "replay: no recorded response for probe {0} attempt {1} in {2}".format(
                    probe_id, attempt, self.source
                ),
                retryable=False,
            )
        text = response.get("text")
        return ProviderResponse(
            text="" if text is None else str(text),
            prompt_tokens=response.get("prompt_tokens", 0),
            completion_tokens=response.get("completion_tokens", 0),
            latency_ms=recorded.get("latency_ms", 0),
            raw={"replayed": True, "source": self.source},
        )

    def describe(self) -> Dict[str, Any]:
        """Metadata recorded in replay results (never secrets)."""
        return {
            "provider": self.name,
            "model": self.model,
            "base_url": None,
            "results": self.source,
        }


# ---------------------------------------------------------------------------
# Offline re-scoring without the runner
# ---------------------------------------------------------------------------

def _probe_class(probe: Any) -> str:
    """Return the probe's failure class, or ``"unknown"`` when unusable."""
    cls = probe.get("class") if isinstance(probe, dict) else None
    if isinstance(cls, str) and cls in CLASSES:
        return cls
    return "unknown"


def _probe_status_map(document: Any) -> Dict[str, str]:
    """Map probe_id -> status from a results document (tolerates junk)."""
    statuses: Dict[str, str] = {}
    if not isinstance(document, dict):
        return statuses
    probes = document.get("probes")
    if not isinstance(probes, list):
        return statuses
    for entry in probes:
        if not isinstance(entry, dict):
            continue
        probe_id = entry.get("probe_id")
        if not isinstance(probe_id, str) or not probe_id:
            continue
        status = entry.get("status")
        statuses.setdefault(probe_id, status if isinstance(status, str) else "unknown")
    return statuses


def compare_statuses(replayed: Dict[str, Any], original: Dict[str, Any]) -> Dict[str, Any]:
    """Compare per-probe statuses between a replayed and an original results doc.

    Returns the ``compared_to`` structure used in replay results. Missing or
    malformed keys are tolerated. ``matched`` counts probe ids present in both
    documents whose status agrees; ``missing_in_original`` lists probes that were
    replayed but were not in the original run and ``missing_in_replay`` the
    reverse. All lists are sorted by probe id for deterministic output.
    """
    original_doc = original if isinstance(original, dict) else {}
    replayed_statuses = _probe_status_map(replayed)
    original_statuses = _probe_status_map(original_doc)

    replay_ids = set(replayed_statuses)
    original_ids = set(original_statuses)
    matched = 0
    mismatched: List[Dict[str, str]] = []
    for probe_id in sorted(replay_ids & original_ids):
        replayed_status = replayed_statuses[probe_id]
        original_status = original_statuses[probe_id]
        if replayed_status == original_status:
            matched += 1
        else:
            mismatched.append(
                {
                    "probe_id": probe_id,
                    "original_status": original_status,
                    "replayed_status": replayed_status,
                }
            )

    run_id = original_doc.get("run_id")
    return {
        "run_id": run_id if isinstance(run_id, str) else "",
        "matched": matched,
        "mismatched": mismatched,
        "missing_in_original": sorted(replay_ids - original_ids),
        "missing_in_replay": sorted(original_ids - replay_ids),
    }


def _rate_bucket(passed: int, failed: int, errored: int) -> Dict[str, Any]:
    total = passed + failed + errored
    return {
        "total": total,
        "pass": passed,
        "fail": failed,
        "error": errored,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def _replay_run_id(original_run_id: Any) -> str:
    base = original_run_id.strip() if isinstance(original_run_id, str) else ""
    return "replay-{0}".format(base) if base else "replay"


def replay_recorded(
    records: Iterable[Dict[str, Any]],
    probes: Iterable[Dict[str, Any]],
    original_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Re-score recorded attempts offline into a contract-shaped results document.

    ``probes`` is a list of probe records (as returned by
    ``failbench.schema.load_probes``); each recorded attempt is scored with
    ``failbench.scoring.score(probe["scoring"], text)``. A probe passes only when
    **all** of its recorded repeats pass (mirroring ``score_probe_scoring``); any
    recorded error makes the probe an ``error``.

    Probes are emitted in ``failbench.schema.CLASSES`` order, then by probe id.
    Recorded probes that no longer exist in the probe corpus are reported as
    ``error`` entries; probes with no recorded attempt are omitted. When
    ``original_results`` contains a ``probes`` list the resulting statuses are
    compared against it and stored under ``compared_to``.
    """
    original = original_results if isinstance(original_results, dict) else {}

    probe_index: Dict[str, Dict[str, Any]] = {}
    for probe in probes or []:
        if not isinstance(probe, dict):
            continue
        probe_id = probe.get("id")
        if isinstance(probe_id, str) and probe_id and probe_id not in probe_index:
            probe_index[probe_id] = probe

    grouped = group_attempts(records or [])
    class_rank = {name: rank for rank, name in enumerate(CLASSES)}

    def _sort_key(item: Tuple[str, Dict[int, Dict[str, Any]]]) -> Tuple[int, str]:
        probe_id = item[0]
        return (class_rank.get(_probe_class(probe_index.get(probe_id)), len(CLASSES)), probe_id)

    entries: List[Dict[str, Any]] = []
    for probe_id, attempts in sorted(grouped.items(), key=_sort_key):
        indices = sorted(attempts)
        first_text = _response_text(attempts[indices[0]]) if indices else ""
        probe = probe_index.get(probe_id)

        attempt_entries: List[Dict[str, Any]] = []
        latency_total = 0
        prompt_total = 0
        completion_total = 0

        if probe is None:
            for index in indices:
                recorded = attempts[index]
                latency = _safe_int(recorded.get("latency_ms"))
                latency_total += latency
                prompt_total += _response_tokens(recorded, "prompt_tokens")
                completion_total += _response_tokens(recorded, "completion_tokens")
                attempt_entries.append(
                    {
                        "index": index,
                        "status": "error",
                        "reason": MISSING_PROBE_REASON,
                        "response_sha256": _sha256_text(_response_text(recorded)),
                        "latency_ms": latency,
                    }
                )
            entries.append(
                {
                    "probe_id": probe_id,
                    "class": "unknown",
                    "title": "(probe record missing)",
                    "severity": "unknown",
                    "status": "error",
                    "reason": MISSING_PROBE_REASON,
                    "latency_ms": latency_total,
                    "tokens": {"prompt": prompt_total, "completion": completion_total},
                    "response_sha256": _sha256_text(first_text),
                    "response_excerpt": first_text[:_MAX_EXCERPT],
                    "attempts": attempt_entries,
                }
            )
            continue

        statuses: List[str] = []
        for index in indices:
            recorded = attempts[index]
            text = _response_text(recorded)
            latency = _safe_int(recorded.get("latency_ms"))
            latency_total += latency
            prompt_total += _response_tokens(recorded, "prompt_tokens")
            completion_total += _response_tokens(recorded, "completion_tokens")
            error = recorded.get("error")
            if error is not None:
                status = "error"
                reason = _short("recorded error: {0}".format(error), _MAX_REASON)
            else:
                scoring_spec = probe.get("scoring")
                passed, detail = score(
                    scoring_spec if isinstance(scoring_spec, dict) else {}, text
                )
                status = "pass" if passed else "fail"
                reason = _short(detail, _MAX_REASON)
            statuses.append(status)
            attempt_entries.append(
                {
                    "index": index,
                    "status": status,
                    "reason": reason,
                    "response_sha256": _sha256_text(text),
                    "latency_ms": latency,
                }
            )

        if "error" in statuses:
            probe_status = "error"
        elif all(status == "pass" for status in statuses):
            probe_status = "pass"
        else:
            probe_status = "fail"

        top_reason = ""
        for entry in attempt_entries:
            if entry["status"] != "pass":
                top_reason = entry["reason"]
                break
        if not top_reason and attempt_entries:
            top_reason = attempt_entries[0]["reason"]

        title = probe.get("title")
        severity = probe.get("severity")
        entries.append(
            {
                "probe_id": probe_id,
                "class": _probe_class(probe),
                "title": title if isinstance(title, str) else "",
                "severity": severity if isinstance(severity, str) else "unknown",
                "status": probe_status,
                "reason": _short(top_reason, _MAX_REASON),
                "latency_ms": latency_total,
                "tokens": {"prompt": prompt_total, "completion": completion_total},
                "response_sha256": _sha256_text(first_text),
                "response_excerpt": first_text[:_MAX_EXCERPT],
                "attempts": attempt_entries,
            }
        )

    counts: Dict[str, int] = {"probes": len(entries), "pass": 0, "fail": 0, "error": 0}
    class_counts: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        status = entry["status"]
        counts[status] = counts.get(status, 0) + 1
        bucket = class_counts.setdefault(
            entry["class"], {"pass": 0, "fail": 0, "error": 0}
        )
        bucket[status] = bucket.get(status, 0) + 1

    by_class: Dict[str, Dict[str, Any]] = {}
    for cls in CLASSES:
        if cls in class_counts:
            counts_for_class = class_counts.pop(cls)
            by_class[cls] = _rate_bucket(
                counts_for_class.get("pass", 0),
                counts_for_class.get("fail", 0),
                counts_for_class.get("error", 0),
            )
    for cls in sorted(class_counts):
        counts_for_class = class_counts[cls]
        by_class[cls] = _rate_bucket(
            counts_for_class.get("pass", 0),
            counts_for_class.get("fail", 0),
            counts_for_class.get("error", 0),
        )

    now = _utc_now_iso()
    original_model = original.get("model")
    original_started = original.get("started_at")
    original_config = original.get("config")
    payload: Dict[str, Any] = {
        "schema": 1,
        "run_id": _replay_run_id(original.get("run_id")),
        "provider": "replay",
        "model": (
            original_model.strip()
            if isinstance(original_model, str) and original_model.strip()
            else ReplayProvider.default_model
        ),
        "base_url": None,
        "suite_version": failbench.__version__,
        "started_at": (
            original_started
            if isinstance(original_started, str) and original_started
            else now
        ),
        "finished_at": now,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
        },
        "config": dict(original_config) if isinstance(original_config, dict) else {},
        "counts": counts,
        "by_class": by_class,
        "probes": entries,
        "compared_to": None,
    }

    if isinstance(original.get("probes"), list):
        payload["compared_to"] = compare_statuses(payload, original)
    return payload


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_replay_results(
    payload: Dict[str, Any],
    out_dir: Any,
    filename: str = REPLAY_FILENAME,
) -> Path:
    """Atomically write ``payload`` as pretty JSON and return the written path.

    The directory is created when missing. The file is written to a temporary
    file in the same directory and then moved into place with ``os.replace`` so
    readers never observe a partially written replay artifact.
    """
    directory = Path(out_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReplayError(
            "{0}: cannot create replay output directory: {1}".format(directory, exc)
        ) from exc

    target = directory / filename
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    descriptor = -1
    temp_name: Optional[str] = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=".replay-", suffix=".tmp", dir=str(directory)
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, str(target))
        temp_name = None
        return target
    except OSError as exc:
        raise ReplayError(
            "{0}: cannot write replay results: {1}".format(target, exc)
        ) from exc
    finally:
        if descriptor != -1:  # pragma: no cover - fdopen failure path
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temp_name is not None:  # pragma: no cover - cleanup on failure
            try:
                os.unlink(temp_name)
            except OSError:
                pass
