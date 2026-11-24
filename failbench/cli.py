"""FailBench command-line interface (stdlib only).

The supported invocation from a checkout is ``python -m failbench``; the
``failbench`` console entry point declared in ``pyproject.toml`` calls
:func:`main` as well.

Commands (CONTRACT section 8)
-----------------------------
``list``, ``validate``, ``run``, ``replay``, ``report`` and ``gate``.

Exit codes
----------
* ``0`` -- success (a run whose probes fail is still a successful run).
* ``1`` -- run/validation/replay failure, gate regressions, or report failure.
* ``2`` -- usage or configuration error (unknown provider/class, missing
  required path or API key, bad ``--limit``/``--concurrency``/...).
* ``3`` -- unexpected internal error (one-line message, never a traceback).
* ``130`` -- interrupted (Ctrl-C).

Design notes
------------
* Only the standard library is used. Every command works offline except
  ``run --provider openai``, which talks to an OpenAI-compatible endpoint.
* Sibling modules (``runner``, ``gate``, ``replay``, ``providers``, ``report``)
  are imported lazily inside their handlers so ``--help``, ``list`` and
  ``validate`` keep working even when a module is missing or still being
  written concurrently.
* The CLI never reads or prints API key values. It only ever passes the *name*
  of the environment variable that holds the key (``--api-key-env``).
* ``list`` on an empty corpus is informational rather than a usage error, so it
  prints a message and exits ``0`` (documented choice; the contract does not
  require an error there).
* Advanced, testing-friendly options are marked ``(advanced)`` in help output.
  Their defaults reproduce exactly the documented CONTRACT commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Exit codes (see module docstring)
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3
EXIT_INTERRUPTED = 130

#: Human-readable provider names used in help/epilog text.
PROVIDER_NAMES = "mock, openai, replay"

#: Aliases accepted for provider names (resolved before validation).
_PROVIDER_ALIASES: Dict[str, str] = {
    "fake": "mock",
    "openai-compatible": "openai",
    "openai_compatible": "openai",
    "openai-compat": "openai",
    "compatible": "openai",
    "recorded": "replay",
}

_EPILOG = """\
examples:
  python -m failbench list
  python -m failbench list --class hallucination --json
  python -m failbench validate --strict
  python -m failbench run --provider mock --demo --out results/demo
  python -m failbench run --provider openai --base-url https://api.openai.com/v1 \\
      --api-key-env OPENAI_API_KEY --model gpt-4o-mini --out results/run1
  python -m failbench replay --results results/run1
  python -m failbench report --results results/run1 --out site
  python -m failbench gate --baseline results/base/results.json \\
      --current results/run1/results.json

exit codes: 0 success, 1 failure/regressions, 2 usage or configuration error,
3 internal error, 130 interrupted.
"""

_RUN_EPILOG = """\
examples:
  # offline demo: deterministic mock provider, no network, no API key
  python -m failbench run --provider mock --demo --out results/demo

  # any OpenAI-compatible /chat/completions endpoint (key read from env var)
  python -m failbench run --provider openai --base-url https://api.openai.com/v1 \\
      --api-key-env OPENAI_API_KEY --model gpt-4o-mini --out results/run1 \\
      --concurrency 4

  # replay a recorded run without network
  python -m failbench run --provider replay --results results/run1 \\
      --out results/run1-again

A run exits 0 when the suite completed, regardless of how many probes passed:
probe-level failures are the measurement, not a CLI error.
"""

_MAX_LIST_TITLE = 64
_MAX_LIST_SCORING = 32


# ---------------------------------------------------------------------------
# Small output helpers (no ANSI colors anywhere)
# ---------------------------------------------------------------------------

def _configure_output_streams() -> None:
    """Make ``stdout``/``stderr`` tolerant of unencodable characters.

    Probe titles legitimately contain non-Latin scripts (Arabic-Indic digits,
    CJK, emoji-free symbols, ...). When output is redirected, Windows Python may
    pick the locale code page (e.g. ``gbk``/``cp936``) for ``sys.stdout``, and a
    single unencodable code point would otherwise abort the command with
    ``UnicodeEncodeError``. Keeping the stream's encoding (no mojibake on a real
    console) and replacing only unencodable characters keeps the CLI robust.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # e.g. StringIO in embedded use
            continue
        try:
            reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):  # pragma: no cover - odd streams
            continue


def _print(message: str = "") -> None:
    print(message)


def _print_err(message: str) -> None:
    print(message, file=sys.stderr)


def _truncate(value: Any, width: int) -> str:
    """Collapse whitespace and clip ``value`` to ``width`` characters."""
    text = " ".join(str(value if value is not None else "").split())
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _redact(provider: Any, message: Any) -> str:
    """Best-effort secret scrubbing of an exception message via the provider."""
    text = str(message)
    if provider is None:
        return text
    redact = getattr(provider, "redact", None)
    if not callable(redact):
        return text
    try:
        cleaned = redact(text)
    except Exception:  # pragma: no cover - defensive, redaction must not crash
        return text
    return text if cleaned is None else str(cleaned)


class UsageError(Exception):
    """Post-argparse usage/configuration problem; mapped to exit code 2."""


# ---------------------------------------------------------------------------
# list helpers
# ---------------------------------------------------------------------------

def _summarize_scoring(scoring: Any, width: int = _MAX_LIST_SCORING) -> str:
    """Compact one-line description of a probe's scoring spec."""
    if not isinstance(scoring, dict):
        return _truncate(scoring, width)
    stype = str(scoring.get("type") or "?")
    suffix = ""
    if stype in ("contains_all", "contains_any", "not_contains_any"):
        values = scoring.get("value")
        if isinstance(values, list):
            suffix = ": " + ", ".join(str(item) for item in values)
    elif stype == "exact_match":
        suffix = ": " + str(scoring.get("value"))
    elif stype == "regex":
        suffix = ": " + str(scoring.get("pattern"))
    elif stype == "numeric":
        suffix = ": " + str(scoring.get("value"))
        if scoring.get("tolerance") is not None:
            suffix += " +/- " + str(scoring.get("tolerance"))
    elif stype == "all_of":
        units = scoring.get("units")
        if isinstance(units, list):
            suffix = " ({0} unit(s))".format(len(units))
    return _truncate(stype + suffix, width)


def _print_probe_table(probes: Sequence[Dict[str, Any]]) -> None:
    """Print a readable fixed-width probe table."""
    headers = ["ID", "CLASS", "SEVERITY", "SCORING", "REPEATS", "TITLE"]
    rows: List[List[str]] = []
    for probe in probes:
        rows.append(
            [
                _truncate(probe.get("id"), 28),
                _truncate(probe.get("class"), 24),
                _truncate(probe.get("severity"), 10),
                _summarize_scoring(probe.get("scoring")),
                _truncate(probe.get("repeats"), 7),
                _truncate(probe.get("title"), _MAX_LIST_TITLE),
            ]
        )
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    _print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))).rstrip())
    _print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        _print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------

_PATH_EXTENSIONS = (
    ".html",
    ".htm",
    ".md",
    ".json",
    ".jsonl",
    ".svg",
    ".png",
    ".css",
    ".js",
    ".csv",
    ".txt",
)


def _looks_like_path(text: str) -> bool:
    value = text.strip()
    if not value or "\n" in value:
        return False
    lowered = value.lower()
    if lowered.endswith(_PATH_EXTENSIONS):
        return True
    if value.startswith(("http://", "https://")):
        return False
    return "/" in value or "\\" in value


def _iter_report_outputs(payload: Any) -> List[Tuple[str, str]]:
    """Flatten a render() summary dict into ``(key, string)`` pairs."""
    outputs: List[Tuple[str, str]] = []

    def walk(value: Any, key: str) -> None:
        if isinstance(value, dict):
            for child in sorted(value, key=lambda item: str(item)):
                walk(value[child], str(child))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item, key)
        elif isinstance(value, (str, Path)):
            text = str(value).strip()
            if text:
                outputs.append((key, text))

    walk(payload, "")
    return outputs


# ---------------------------------------------------------------------------
# Provider / options helpers
# ---------------------------------------------------------------------------

def _provider_config_message(exc: BaseException, args: Optional[argparse.Namespace] = None) -> str:
    """Build a safe, secret-free provider configuration error message."""
    message = "provider configuration error: {0}".format(_redact(None, exc))
    env_name = getattr(args, "api_key_env", None) if args is not None else None
    if isinstance(env_name, str) and env_name and env_name not in message:
        # Only the variable *name* is ever handled/printed, never the value.
        message += " (api key environment variable: {0})".format(env_name)
    return message


def _resolve_provider(name: str, args: argparse.Namespace) -> Any:
    """Construct the provider selected on the command line.

    Raises ``ProviderConfigError`` for an unknown provider or bad configuration
    and ``UsageError`` when a required option (``--results``) is missing.
    """
    from .providers import (  # noqa: F401  (ProviderConfigError raised by callee)
        ProviderConfigError,
        available_providers,
        get_provider,
    )

    requested = str(name or "").strip()
    key = requested.lower()
    canonical = _PROVIDER_ALIASES.get(key, key)
    valid = [str(item) for item in available_providers()]
    if canonical not in valid:
        raise ProviderConfigError(
            "unknown provider {0!r}; expected one of: {1}".format(
                requested, ", ".join(valid)
            )
        )

    options: Dict[str, Any] = {}
    if canonical == "mock":
        if args.model:
            options["model"] = args.model
    elif canonical == "replay":
        if not args.results:
            raise UsageError(
                "the replay provider requires --results PATH "
                "(a results directory or a raw.jsonl file)"
            )
        options["results"] = Path(args.results)
    else:  # openai
        if args.base_url:
            options["base_url"] = args.base_url
        if args.api_key_env:
            options["api_key_env"] = args.api_key_env
        if args.model:
            options["model"] = args.model
        if args.timeout is not None:
            options["timeout"] = float(args.timeout)
        if args.retries is not None:
            options["retries"] = int(args.retries)
    return get_provider(canonical, **options)


def _validate_run_numbers(args: argparse.Namespace) -> None:
    """Reject out-of-range numeric options with exit code 2."""
    if args.concurrency is None or int(args.concurrency) < 1:
        raise UsageError(
            "--concurrency must be a positive integer (got {0})".format(args.concurrency)
        )
    if args.limit is not None and int(args.limit) < 1:
        raise UsageError("--limit must be a positive integer (got {0})".format(args.limit))
    if args.repeats is not None and not (1 <= int(args.repeats) <= 5):
        raise UsageError("--repeats must be an integer in [1, 5] (got {0})".format(args.repeats))
    if args.timeout is not None and float(args.timeout) <= 0:
        raise UsageError("--timeout must be a positive number of seconds")
    if args.retries is not None and int(args.retries) < 0:
        raise UsageError("--retries must be a non-negative integer")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_list(args: argparse.Namespace) -> int:
    """List probes, optionally filtered by failure class."""
    from .schema import CLASSES, load_probes

    probes_root = Path(args.probes_dir) if args.probes_dir else None
    try:
        probes = load_probes(probes_root)
    except ValueError as exc:
        _print_err("error: {0}".format(exc))
        return EXIT_FAILURE
    except OSError as exc:
        _print_err("error: could not read probes: {0}".format(exc))
        return EXIT_FAILURE

    selected: List[Dict[str, Any]] = probes
    if args.class_filter:
        if args.class_filter not in CLASSES:
            _print_err(
                "unknown class {0!r}; expected one of: {1}".format(
                    args.class_filter, ", ".join(CLASSES)
                )
            )
            return EXIT_USAGE
        selected = [probe for probe in probes if probe.get("class") == args.class_filter]

    if not selected:
        label = str(probes_root) if probes_root is not None else "probes/"
        if not probes:
            # Listing an empty corpus is informational, not a usage error.
            _print_err("no probes found under {0}".format(label))
        else:
            _print_err("no probes found in class {0}".format(args.class_filter))
        if args.json:
            _print(json.dumps([], indent=2))
        _print("0 probe(s) in 0 class(es)")
        return EXIT_OK

    if args.json:
        clean = [
            {key: value for key, value in probe.items() if not str(key).startswith("_")}
            for probe in selected
        ]
        _print(json.dumps(clean, indent=2, ensure_ascii=True, default=str))
        return EXIT_OK

    _print_probe_table(selected)
    class_count = len(
        {
            probe.get("class")
            for probe in selected
            if probe.get("class") in CLASSES
        }
    )
    _print("{0} probe(s) in {1} class(es)".format(len(selected), class_count))
    return EXIT_OK


def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate the probe corpus and (optionally) the evidence atlas."""
    from .schema import validate_all

    probes_root = Path(args.probes_dir) if args.probes_dir else None
    evidence_root = Path(args.evidence_dir) if args.evidence_dir else None
    try:
        report = validate_all(probes_root=probes_root, evidence_root=evidence_root)
    except ValueError as exc:
        _print_err("error: {0}".format(exc))
        return EXIT_FAILURE
    except OSError as exc:
        _print_err("error: could not validate corpus: {0}".format(exc))
        return EXIT_FAILURE

    errors = list(report.get("errors") or [])
    warnings = list(report.get("warnings") or [])
    strict_failure = bool(args.strict and warnings)

    if args.json:
        _print(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True, default=str))
    else:
        for error in errors:
            _print("ERROR: {0}".format(error))
        for warning in warnings:
            _print("WARN: {0}".format(warning))
        if errors:
            _print("FAILED: {0} error(s)".format(len(errors)))
        else:
            _print(
                "OK: {0} probes, {1} evidence records, 0 errors".format(
                    int(report.get("probe_count") or 0),
                    int(report.get("evidence_count") or 0),
                )
            )
            if strict_failure:
                _print(
                    "STRICT: {0} warning(s) treated as errors".format(len(warnings))
                )

    if errors:
        return EXIT_FAILURE
    if strict_failure:
        return EXIT_FAILURE
    return EXIT_OK


def _cmd_run(args: argparse.Namespace) -> int:
    """Run the probe suite against a provider and write results artifacts."""
    _validate_run_numbers(args)

    provider_name = str(args.provider or "").strip() or "mock"
    if args.demo:
        if provider_name.lower() not in ("mock", "fake"):
            _print_err(
                "note: --demo uses the deterministic mock provider; "
                "ignoring --provider {0}".format(provider_name)
            )
            provider_name = "mock"
        out_arg = args.out or "results/demo"
    else:
        out_arg = args.out or "results/run"
    out_dir = Path(out_arg)

    from .providers import ProviderConfigError

    try:
        provider = _resolve_provider(provider_name, args)
    except UsageError:
        raise
    except ProviderConfigError as exc:
        _print_err(_provider_config_message(exc, args))
        return EXIT_USAGE
    except ImportError as exc:
        _print_err("run unavailable: provider module is missing: {0}".format(exc))
        return EXIT_FAILURE

    try:
        from .runner import RunError, run_from_paths
    except ImportError as exc:
        _print_err(
            "run unavailable: failbench/runner.py is not present yet "
            "(W3 deliverable): {0}".format(exc)
        )
        return EXIT_FAILURE

    probes_dir = Path(args.probes_dir) if args.probes_dir else None
    try:
        results = run_from_paths(
            out_dir=out_dir,
            provider=provider,
            probes_dir=probes_dir,
            concurrency=args.concurrency,
            class_filter=args.class_filter,
            limit=args.limit,
            repeats_override=args.repeats,
            progress=not args.quiet,
        )
    except RunError as exc:
        _print_err("run failed: {0}".format(_redact(provider, exc)))
        return EXIT_FAILURE
    except ProviderConfigError as exc:
        _print_err(_provider_config_message(exc, args))
        return EXIT_USAGE
    except ValueError as exc:
        _print_err("run failed: {0}".format(_redact(provider, exc)))
        return EXIT_FAILURE
    except OSError as exc:
        _print_err("run failed: could not write results: {0}".format(_redact(provider, exc)))
        return EXIT_FAILURE

    if not isinstance(results, dict):
        _print_err("run failed: runner returned an unexpected result")
        return EXIT_FAILURE
    _print("results: {0}".format(out_dir / "results.json"))
    return EXIT_OK


def _load_original_results(results_path: Path) -> Optional[Dict[str, Any]]:
    """Best-effort load of ``<results>/results.json`` for replay comparison."""
    if not results_path.is_dir():
        return None
    candidate = results_path / "results.json"
    if not candidate.is_file():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _print_replay_comparison(payload: Dict[str, Any]) -> None:
    """Print the optional ``compared_to`` summary of a replay payload.

    The replay module reports status comparisons as
    ``{"matched": int, "mismatched": [{probe_id, original_status,
    replayed_status}], "missing_in_original": [...], "missing_in_replay": [...]}``;
    the extraction below also tolerates similar shapes from other versions.
    """
    compared = payload.get("compared_to")
    if not compared:
        return
    if not isinstance(compared, dict):
        _print("compared to original results: {0}".format(compared))
        return

    matched: Optional[int] = None
    total: Optional[int] = None
    mismatches: List[Tuple[str, str, str]] = []
    for key in ("matched", "match", "matched_count", "same", "statuses_match"):
        value = compared.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            matched = value
            break
    for key in ("total", "count", "probes", "compared"):
        value = compared.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            total = value
            break
    for key in ("mismatches", "mismatched", "differences", "changed", "status_mismatches"):
        value = compared.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    probe_id = item.get("probe_id") or item.get("id") or "?"
                    mismatches.append(
                        (
                            str(probe_id),
                            str(item.get("original_status") or "?"),
                            str(item.get("replayed_status") or "?"),
                        )
                    )
                else:
                    mismatches.append((str(item), "?", "?"))
            break

    if matched is None:
        _print(
            "compared to original results: {0}".format(
                json.dumps(compared, sort_keys=True, ensure_ascii=False, default=str)
            )
        )
        return
    if total is None:
        total = matched + len(mismatches)
    _print("statuses match original: {0}/{1}".format(matched, total))
    for probe_id, original_status, replayed_status in mismatches:
        _print(
            "  status mismatch: {0} ({1} -> {2})".format(
                probe_id, original_status, replayed_status
            )
        )


def _import_replay_module() -> Any:
    """Import the replay implementation module.

    CONTRACT section 2 places the implementation in
    :mod:`failbench.providers.replay`; some task briefs refer to a top-level
    ``failbench.replay`` alias. Prefer the top-level module when it exists, fall
    back to the contract location otherwise. Both paths are guarded with a
    broad ``ImportError`` catch because ``from . import replay`` raises
    ``ImportError`` (not ``ModuleNotFoundError``) when the name does not exist.
    """
    try:
        from . import replay as replay_module

        return replay_module
    except ImportError:
        pass
    from .providers import replay as replay_module

    return replay_module


def _cmd_replay(args: argparse.Namespace) -> int:
    """Re-score recorded responses from ``raw.jsonl`` without any network."""
    results_path = Path(args.results)
    if not results_path.exists():
        _print_err("replay error: results path not found: {0}".format(results_path))
        return EXIT_USAGE

    try:
        replay_mod = _import_replay_module()
        from .providers import ProviderConfigError
        from .schema import load_probes
    except ImportError as exc:
        _print_err(
            "replay unavailable: failbench/providers/replay.py is not present yet "
            "(W3 deliverable): {0}".format(exc)
        )
        return EXIT_FAILURE

    probes_root = Path(args.probes_dir) if args.probes_dir else None
    try:
        records = replay_mod.load_raw_records(results_path)
    except replay_mod.ReplayError as exc:
        _print_err("replay error: {0}".format(exc))
        return EXIT_FAILURE
    except OSError as exc:
        _print_err("replay error: could not read recorded results: {0}".format(exc))
        return EXIT_FAILURE

    try:
        probes = load_probes(probes_root)
    except ValueError as exc:
        _print_err("replay error: {0}".format(exc))
        return EXIT_FAILURE

    if not probes:
        label = str(probes_root) if probes_root is not None else "probes/"
        _print_err(
            "warning: no probes found under {0}; replay relies on recorded data only".format(
                label
            )
        )

    original = _load_original_results(results_path)
    try:
        payload = replay_mod.replay_recorded(records, probes, original)
    except ProviderConfigError as exc:
        _print_err(_provider_config_message(exc))
        return EXIT_USAGE
    except replay_mod.ReplayError as exc:
        _print_err("replay error: {0}".format(exc))
        return EXIT_FAILURE
    except (OSError, ValueError) as exc:
        _print_err("replay error: {0}".format(exc))
        return EXIT_FAILURE

    if not isinstance(payload, dict):
        _print_err("replay error: replay module returned an unexpected payload")
        return EXIT_FAILURE

    out_dir = Path(args.out) if args.out else (
        results_path if results_path.is_dir() else Path.cwd()
    )
    try:
        written = replay_mod.write_replay_results(payload, out_dir)
    except replay_mod.ReplayError as exc:
        _print_err("replay error: {0}".format(exc))
        return EXIT_FAILURE
    except OSError as exc:
        _print_err("replay error: could not write replay results: {0}".format(exc))
        return EXIT_FAILURE

    counts = payload.get("counts")
    if not isinstance(counts, dict):
        counts = {}
    try:
        total = int(counts.get("probes") or 0)
    except (TypeError, ValueError):
        total = 0
    passed = counts.get("pass", 0)
    failed = counts.get("fail", 0)
    errored = counts.get("error", 0)

    if args.json:
        _print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str))
    else:
        _print(
            "Replayed {0} probe(s): {1} pass, {2} fail, {3} error".format(
                total, passed, failed, errored
            )
        )
        _print("wrote {0}".format(written))
        _print_replay_comparison(payload)

    if total <= 0:
        _print_err("replay error: no probes were replayed (recorded results may be empty)")
        return EXIT_FAILURE
    return EXIT_OK


def _cmd_report(args: argparse.Namespace) -> int:
    """Generate the static report / dashboard (W4 module, called lazily)."""
    results_path = Path(args.results)
    if not results_path.exists():
        _print_err("report generation failed: results path not found: {0}".format(results_path))
        return EXIT_FAILURE
    if not results_path.is_dir() and results_path.name != "results.json":
        _print_err(
            "report generation failed: results path must be a run directory "
            "or a results.json file: {0}".format(results_path)
        )
        return EXIT_FAILURE

    try:
        from .report import render
    except ModuleNotFoundError as exc:
        missing = str(getattr(exc, "name", "") or "")
        if missing == "failbench.report" or missing.endswith(".report"):
            _print_err(
                "report generation unavailable: failbench/report.py is not present "
                "yet (W4 deliverable); the run artifacts under {0} are still valid.".format(
                    results_path
                )
            )
        else:
            _print_err("report generation failed: {0}".format(exc))
        return EXIT_FAILURE
    except ImportError as exc:
        _print_err("report generation failed: {0}".format(exc))
        return EXIT_FAILURE

    out_dir = Path(args.out)
    probes_dir = Path(args.probes_dir) if args.probes_dir else None
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
    results_md = Path(args.results_md) if args.results_md else None

    try:
        payload = render(
            results_path,
            out_dir,
            probes_dir=probes_dir,
            evidence_dir=evidence_dir,
            results_md_path=results_md,
        )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, never a traceback
        _print_err("report generation failed: {0}".format(exc))
        return EXIT_FAILURE

    printed = False
    for key, value in _iter_report_outputs(payload):
        lowered_key = key.lower()
        if lowered_key in ("results_path", "results", "input", "source"):
            # Never claim the input results document was written: render() only
            # reads it. This line is informational, not a write.
            _print("results: {0}".format(value))
            printed = True
        elif _looks_like_path(value):
            _print("wrote {0}".format(value))
            printed = True
        elif key:
            _print("{0}: {1}".format(key, value))
            printed = True
    if not printed:
        _print("report written to {0}".format(out_dir))
    return EXIT_OK


def _cmd_gate(args: argparse.Namespace) -> int:
    """Compare two results documents and fail on regressions."""
    baseline = Path(args.baseline)
    current = Path(args.current)
    for label, path in (("baseline", baseline), ("current", current)):
        if not path.exists():
            _print_err(
                "gate error: {0} results file not found: {1}".format(label, path)
            )
            return EXIT_USAGE

    try:
        from .gate import GateError, compare_files, format_report
    except ImportError as exc:
        _print_err(
            "gate unavailable: failbench/gate.py is not present yet "
            "(W3 deliverable): {0}".format(exc)
        )
        return EXIT_FAILURE

    try:
        comparison = compare_files(baseline, current)
    except GateError as exc:
        _print_err("gate error: {0}".format(exc))
        return EXIT_USAGE
    except (OSError, ValueError) as exc:
        _print_err("gate error: {0}".format(exc))
        return EXIT_USAGE

    if not isinstance(comparison, dict):
        _print_err("gate error: gate module returned an unexpected comparison")
        return EXIT_FAILURE

    if args.json:
        _print(json.dumps(comparison, indent=2, ensure_ascii=True, sort_keys=True, default=str))
    else:
        try:
            text = str(format_report(comparison))
        except GateError as exc:
            _print_err("gate error: {0}".format(exc))
            return EXIT_USAGE
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        sys.stdout.flush()

    return EXIT_FAILURE if comparison.get("has_regressions") else EXIT_OK


_HANDLERS = {
    "list": _cmd_list,
    "validate": _cmd_validate,
    "run": _cmd_run,
    "replay": _cmd_replay,
    "report": _cmd_report,
    "gate": _cmd_gate,
}


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the full ``python -m failbench`` argument parser."""
    # Single source of truth for the version string (failbench/__init__.py).
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="python -m failbench",
        description=(
            "FailBench: evidence-backed, judge-free failure probes for LLMs. "
            "Deterministic probes, mechanical scoring, no LLM judges."
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + __version__,
        help="print the FailBench version and exit",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", title="commands")

    # -- list ---------------------------------------------------------------
    list_parser = subparsers.add_parser(
        "list",
        help="list probes (optionally filtered by failure class)",
        description="List probes in the corpus as a table, or as JSON with --json.",
    )
    list_parser.add_argument(
        "--class",
        dest="class_filter",
        metavar="CLASS",
        help="only show probes in this failure class (e.g. hallucination)",
    )
    list_parser.add_argument(
        "--json", action="store_true", help="print a JSON array of probe records"
    )
    list_parser.add_argument(
        "--probes-dir",
        metavar="DIR",
        help="(advanced) probe corpus directory (default: probes/)",
    )

    # -- validate -----------------------------------------------------------
    validate_parser = subparsers.add_parser(
        "validate",
        help="validate the probe corpus and evidence atlas",
        description=(
            "Validate every probe and evidence record against the schema in "
            "docs/CONTRACT.md. Exits non-zero when errors are found."
        ),
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="treat validation warnings as errors",
    )
    validate_parser.add_argument(
        "--json", action="store_true", help="print the raw validation report as JSON"
    )
    validate_parser.add_argument(
        "--probes-dir",
        metavar="DIR",
        help="(advanced) probe corpus directory (default: probes/)",
    )
    validate_parser.add_argument(
        "--evidence-dir",
        metavar="DIR",
        help="(advanced) evidence atlas directory (default: data/evidence/)",
    )

    # -- run ----------------------------------------------------------------
    run_parser = subparsers.add_parser(
        "run",
        help="run the probe suite against a provider",
        description=(
            "Run probes against a provider and write results/<run_id>/results.json "
            "and raw.jsonl. A completed run exits 0 regardless of probe pass/fail "
            "counts; probe failures are the measurement."
        ),
        epilog=_RUN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument(
        "--provider",
        default="mock",
        metavar="NAME",
        help=(
            "provider to use: {0} (aliases: fake, openai-compatible, recorded); "
            "default: mock".format(PROVIDER_NAMES)
        ),
    )
    run_parser.add_argument(
        "--demo",
        action="store_true",
        help="offline demo: force the mock provider and default --out to results/demo",
    )
    run_parser.add_argument(
        "--out",
        metavar="DIR",
        help="output directory (default: results/demo with --demo, else results/run)",
    )
    run_parser.add_argument(
        "--base-url",
        metavar="URL",
        help="openai provider: base URL of the OpenAI-compatible /chat/completions endpoint",
    )
    run_parser.add_argument(
        "--api-key-env",
        metavar="VAR",
        help=(
            "openai provider: name of the environment variable holding the API key "
            "(the key value is never read or printed by the CLI itself)"
        ),
    )
    run_parser.add_argument(
        "--model", metavar="MODEL", help="model name to request (provider default otherwise)"
    )
    run_parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        metavar="N",
        help="number of probes to run in parallel (default: 4)",
    )
    run_parser.add_argument(
        "--class",
        dest="class_filter",
        metavar="CLASS",
        help="only run probes in this failure class",
    )
    run_parser.add_argument(
        "--limit", type=int, metavar="N", help="run at most N probes"
    )
    run_parser.add_argument(
        "--timeout",
        type=float,
        metavar="S",
        help="openai provider: per-request timeout in seconds",
    )
    run_parser.add_argument(
        "--retries",
        type=int,
        metavar="N",
        help="openai provider: number of retries for retryable failures",
    )
    run_parser.add_argument(
        "--results",
        metavar="PATH",
        help=(
            "(advanced) recorded results path for --provider replay "
            "(results directory or raw.jsonl file)"
        ),
    )
    run_parser.add_argument(
        "--probes-dir",
        metavar="DIR",
        help="(advanced) probe corpus directory (default: probes/)",
    )
    run_parser.add_argument(
        "--repeats",
        type=int,
        metavar="N",
        help="(advanced) override every probe's repeat count (1-5)",
    )
    run_parser.add_argument(
        "--quiet",
        action="store_true",
        help="(advanced) suppress runner progress output",
    )

    # -- replay -------------------------------------------------------------
    replay_parser = subparsers.add_parser(
        "replay",
        help="re-score recorded responses offline (no network)",
        description=(
            "Re-score the responses recorded in a results directory's raw.jsonl "
            "using the current probe corpus and scoring rules. Mismatches with the "
            "original statuses are reported as findings, not crashes."
        ),
    )
    replay_parser.add_argument(
        "--results",
        required=True,
        metavar="PATH",
        help="results directory (containing raw.jsonl) or raw.jsonl file",
    )
    replay_parser.add_argument(
        "--probes-dir",
        metavar="DIR",
        help="(advanced) probe corpus directory (default: probes/)",
    )
    replay_parser.add_argument(
        "--out",
        metavar="DIR",
        help="(advanced) output directory for replay-results.json "
        "(default: the results directory)",
    )
    replay_parser.add_argument(
        "--json", action="store_true", help="print the raw replay payload as JSON"
    )

    # -- report -------------------------------------------------------------
    report_parser = subparsers.add_parser(
        "report",
        help="generate the static report/dashboard from a results directory",
        description=(
            "Generate the self-contained static site (site/index.html) and the "
            "Markdown report from a results directory. Implemented by "
            "failbench/report.py; the CLI degrades gracefully when it is missing."
        ),
    )
    report_parser.add_argument(
        "--results", required=True, metavar="PATH", help="results directory to render"
    )
    report_parser.add_argument(
        "--out", required=True, metavar="DIR", help="output directory for the static site"
    )
    report_parser.add_argument(
        "--probes-dir",
        metavar="DIR",
        help="(advanced) probe corpus directory (default: probes/)",
    )
    report_parser.add_argument(
        "--evidence-dir",
        metavar="DIR",
        help="(advanced) evidence atlas directory (default: data/evidence/)",
    )
    report_parser.add_argument(
        "--results-md",
        metavar="PATH",
        help="(advanced) Markdown report output path (default: docs/RESULTS.md)",
    )

    # -- gate ---------------------------------------------------------------
    gate_parser = subparsers.add_parser(
        "gate",
        help="compare two results files and fail on regressions",
        description=(
            "Compare a baseline results document with a current one and print a "
            "regression report. Exits 1 when regressions are detected (pass -> "
            "fail/error, or fail -> error, or a probe disappears)."
        ),
    )
    gate_parser.add_argument(
        "--baseline", required=True, metavar="PATH", help="baseline results.json path"
    )
    gate_parser.add_argument(
        "--current", required=True, metavar="PATH", help="current results.json path"
    )
    gate_parser.add_argument(
        "--json", action="store_true", help="print the raw comparison as JSON"
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI. Returns the process exit code (never raises for user errors)."""
    # Must happen before argparse prints help: probe titles (and therefore
    # generated output) may contain characters the console code page lacks.
    _configure_output_streams()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    command = getattr(args, "command", None)
    if not command:
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    handler = _HANDLERS.get(str(command))
    if handler is None:  # pragma: no cover - argparse restricts the choices
        _print_err("unknown command: {0}".format(command))
        return EXIT_USAGE

    try:
        return int(handler(args))
    except KeyboardInterrupt:
        _print_err("interrupted")
        return EXIT_INTERRUPTED
    except UsageError as exc:
        _print_err(str(exc))
        return EXIT_USAGE
    except BrokenPipeError:  # pragma: no cover - output piped into a closed reader
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001 - never leak a traceback for user errors
        _print_err("internal error: {0}".format(exc))
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover - `python -m failbench.cli` convenience
    sys.exit(main())
