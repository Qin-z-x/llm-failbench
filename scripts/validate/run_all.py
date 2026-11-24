#!/usr/bin/env python3
"""Offline QA orchestrator for the FailBench repository (stdlib only).

Runs the fixed offline sequence and prints an ASCII summary table:

    CONTRACT -> UNITTEST -> CLI_VALIDATE -> DEMO_RUN -> DETERMINISM
    -> REPORT -> SITE_SANITY -> GATE_DEMO_VS_RERUN -> ROOT_FILES

Rules of engagement:

* No network access of any kind; ``scripts/validate/check_links.py`` is never
  invoked from here.
* Every child process runs from the repository root with ``PYTHONPATH``
  containing the root and ``PYTHONIOENCODING=utf-8``, so Windows PowerShell
  and ``ubuntu-latest`` CI behave the same.
* A partially built repository is handled gracefully. When the corpus is
  incomplete (fewer than 8 probes or evidence records for any class) or
  ``--allow-incomplete`` is given, missing artifacts are SKIP with an
  explanatory detail; in strict mode they are FAIL. Subprocess timeouts,
  missing files, invalid JSON and import errors never raise a traceback.
* Exit status is 0 iff no step reported FAIL (SKIP and WARN are non-failing).

Usage::

    python scripts/validate/run_all.py [--root PATH] [--allow-incomplete] [--keep]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIN_ITEMS_PER_CLASS = 8
BLOB_LIMIT = 4000
DETAIL_LIMIT = 120
SITE_MAX_BYTES = 3 * 1024 * 1024
ALLOWED_STATUSES = ("pass", "fail", "error")
CONTRACT_TIMEOUT, UNITTEST_TIMEOUT, CLI_TIMEOUT, DEMO_TIMEOUT, GATE_TIMEOUT = 300, 300, 180, 300, 120
HONESTY_MARKER = "No live model endpoint was available during this build"
MOCK_MARKER = "mock provider"

REQUIRED_ROOT_FILES: Tuple[str, ...] = (
    "README.md", "docs/CONTRACT.md", "LICENSE", "failbench/schema.py", "pyproject.toml",
)
REMOTE_SCRIPT_RE = re.compile(r"""<script[^>]*\bsrc\s*=\s*["']https?://""", re.IGNORECASE)
REMOTE_LINK_RE = re.compile(r"""<link[^>]*\bhref\s*=\s*["']https?://""", re.IGNORECASE)

# Evidence that a module/subcommand simply does not exist yet (not a real failure).
UNIMPLEMENTED_MARKERS: Tuple[str, ...] = (
    "no module named failbench", "no module named 'failbench", "invalid choice",
    "unrecognized arguments", "unrecognized option", "unknown command",
    "invalid command", "no such command",
)
STRICT_FLAG_MARKERS: Tuple[str, ...] = (
    "unrecognized arguments", "unrecognized option", "invalid option",
    "no such option", "unknown option", "unknown argument",
)


# ---------------------------------------------------------------------------
# Outcome types
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Outcome of one validation step."""

    step: str
    status: str  # PASS | FAIL | SKIP | WARN
    detail: str

    def __post_init__(self) -> None:
        self.detail = " ".join(str(self.detail).split())


class Context:
    """Mutable state shared by the validation steps."""

    def __init__(self, root: Path, env: Dict[str, str], corpus_incomplete: bool,
                 explicit_allow_incomplete: bool, corpus_detail: str, tmp_dir: Path) -> None:
        self.root = root
        self.env = env
        self.corpus_incomplete = corpus_incomplete
        self.explicit_allow_incomplete = explicit_allow_incomplete
        self.lenient = corpus_incomplete or explicit_allow_incomplete
        self.corpus_detail = corpus_detail
        self.tmp_dir = tmp_dir
        self.results_a: Optional[Path] = None
        self.results_b: Optional[Path] = None
        self.site_index: Optional[Path] = None

    def skip_or_fail(self, step: str, detail: str) -> StepResult:
        """Start from SKIP in lenient mode; FAIL in strict mode."""
        return StepResult(step, "SKIP" if self.lenient else "FAIL", detail)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clip(text: str, limit: int = DETAIL_LIMIT) -> str:
    """Collapse whitespace and truncate to ``limit`` characters."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 3].rstrip() + "..."


def last_line(*blobs: str) -> str:
    """Return the last non-empty line from the first blob that has one."""
    for blob in blobs:
        for line in reversed((blob or "").splitlines()):
            if line.strip():
                return clip(line)
    return "no output captured"


def as_text(value: Any) -> str:
    """Best-effort conversion of captured subprocess output to text."""
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def repo_env(root: Path) -> Dict[str, str]:
    """Environment for child processes: repo root on PYTHONPATH, UTF-8 output."""
    env = dict(os.environ)
    parts = [str(root)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return env


def run_command(args: Sequence[str], ctx: Context,
                timeout: int) -> Tuple[Optional[int], str, str, Optional[str]]:
    """Run ``python <args>`` from the repo root; return (rc, stdout, stderr, problem)."""
    try:
        proc = subprocess.run(
            [sys.executable, *args], cwd=str(ctx.root), env=ctx.env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return None, as_text(exc.stdout), as_text(exc.stderr), f"timed out after {timeout}s"
    except OSError as exc:  # interpreter missing, permissions, ...
        return None, "", "", f"could not start subprocess: {exc}"
    return proc.returncode, proc.stdout or "", proc.stderr or "", None


def print_step_start(index: int, total: int, name: str) -> None:
    print()
    print(f"[{index}/{total}] {name}", flush=True)


def print_capture(stdout: str, stderr: str) -> None:
    """Print captured child output indented under the current step."""
    for label, blob in (("stdout", stdout), ("stderr", stderr)):
        text = (blob or "").rstrip()
        if not text:
            continue
        truncated = len(text) > BLOB_LIMIT
        suffix = f" (last {BLOB_LIMIT} chars)" if truncated else ""
        if truncated:
            text = text[-BLOB_LIMIT:]
        print(f"    {label}{suffix}:")
        for line in text.splitlines():
            print("      " + line)


def print_table(results: Sequence[StepResult]) -> None:
    """Print the final ASCII summary table."""
    name_w = max([len("STEP")] + [len(r.step) for r in results])
    status_w = max([len("RESULT")] + [len(r.status) for r in results])
    detail_w = max([len("DETAIL")] + [min(len(r.detail), DETAIL_LIMIT) for r in results])
    border = f"+-{'-' * name_w}-+-{'-' * status_w}-+-{'-' * detail_w}-+"
    print(border)
    print(f"| {'STEP':<{name_w}} | {'RESULT':<{status_w}} | {'DETAIL':<{detail_w}} |")
    print(border)
    for r in results:
        detail = r.detail if len(r.detail) <= detail_w else r.detail[: detail_w - 3].rstrip() + "..."
        print(f"| {r.step:<{name_w}} | {r.status:<{status_w}} | {detail:<{detail_w}} |")
    print(border)


def cli_availability(root: Path) -> Tuple[bool, str]:
    """Whether ``python -m failbench`` has a chance of working."""
    if (root / "failbench" / "__main__.py").is_file() or (root / "failbench" / "cli.py").is_file():
        return True, ""
    return False, "failbench CLI is not implemented yet (missing failbench/__main__.py and cli.py)"


def looks_cli_unimplemented(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in UNIMPLEMENTED_MARKERS)


def looks_strict_unsupported(text: str) -> bool:
    lower = (text or "").lower()
    return "--strict" in lower and any(marker in lower for marker in STRICT_FLAG_MARKERS)


def find_results_json(run_dir: Path) -> Optional[Path]:
    """Locate a run's results.json, tolerating one nested run directory."""
    direct = run_dir / "results.json"
    if direct.is_file():
        return direct
    nested = sorted(run_dir.rglob("results.json")) if run_dir.is_dir() else []
    return nested[0] if nested else None


def load_results_json(path: Path) -> Dict[str, Any]:
    """Load results.json and require an object at the top level."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value is not an object")
    return data


def count_of(mapping: Any, key: str) -> int:
    """Read an integer count from an untrusted mapping."""
    try:
        return int(mapping.get(key, 0) or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def corpus_status(root: Path) -> Tuple[bool, str]:
    """Return ``(complete, detail)`` using ``failbench.schema.validate_all()``.

    Any import/shape problem is treated as "incomplete" (never raised): the
    suite must survive a half-built tree.
    """
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        from failbench import schema  # imported lazily on purpose

        report = schema.validate_all()
        classes = list(getattr(schema, "CLASSES", {}) or {})
        if not classes:
            return False, "failbench.schema exposes no failure classes; assuming incomplete corpus"
        probe_counts = report.get("probe_by_class") or {}
        evidence_counts = report.get("evidence_by_class") or {}
        short = [cls for cls in classes
                 if count_of(probe_counts, cls) < MIN_ITEMS_PER_CLASS
                 or count_of(evidence_counts, cls) < MIN_ITEMS_PER_CLASS]
        probe_total, evidence_total = count_of(report, "probe_count"), count_of(report, "evidence_count")
        if short:
            return False, (f"corpus incomplete: {len(short)}/{len(classes)} classes below "
                           f"{MIN_ITEMS_PER_CLASS} probes or {MIN_ITEMS_PER_CLASS} evidence "
                           f"({probe_total} probes, {evidence_total} evidence)")
        return True, (f"corpus complete: {probe_total} probes and {evidence_total} evidence "
                      f"across {len(classes)} classes")
    except Exception as exc:  # ImportError, syntax error, unexpected report shape
        return False, (f"could not evaluate corpus completeness "
                       f"({type(exc).__name__}: {clip(str(exc), 100)}); assuming incomplete")


# ---------------------------------------------------------------------------
# Step 1: CONTRACT
# ---------------------------------------------------------------------------

def step_contract(ctx: Context) -> StepResult:
    step = "CONTRACT"
    script = ctx.root / "scripts" / "validate" / "check_contract.py"
    if not script.is_file():
        return StepResult(step, "FAIL", "scripts/validate/check_contract.py is missing; contract gate cannot run")
    args: List[str] = [str(script)]
    if ctx.lenient:
        args.append("--allow-incomplete")
        print("    $ python scripts/validate/check_contract.py --allow-incomplete")
    else:
        print("    $ python scripts/validate/check_contract.py")
    rc, out, err, problem = run_command(args, ctx, CONTRACT_TIMEOUT)
    print_capture(out, err)
    if problem is not None:
        return StepResult(step, "FAIL", f"check_contract.py {problem}")
    if rc != 0:
        return StepResult(step, "FAIL", f"check_contract.py exited {rc}: {last_line(err, out)}")
    if ctx.corpus_incomplete and not ctx.explicit_allow_incomplete:
        return StepResult(step, "WARN", f"contract gate passed with --allow-incomplete ({ctx.corpus_detail})")
    label = "explicit --allow-incomplete" if ctx.lenient else "strict, complete corpus"
    return StepResult(step, "PASS", f"contract gate passed ({label})")


# ---------------------------------------------------------------------------
# Step 2: UNITTEST
# ---------------------------------------------------------------------------

def step_unittest(ctx: Context) -> StepResult:
    step = "UNITTEST"
    tests_dir = ctx.root / "tests"
    test_files = sorted(tests_dir.rglob("test_*.py")) if tests_dir.is_dir() else []
    if not test_files:
        return ctx.skip_or_fail(step, "tests/ directory is missing or contains no test_*.py modules yet")
    print("    $ python -m unittest discover -s tests -t . -v")
    rc, out, err, problem = run_command(
        ["-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], ctx, UNITTEST_TIMEOUT)
    print_capture(out, err)
    if problem is not None:
        return StepResult(step, "FAIL", f"unit tests {problem}")
    if rc == 0:
        return StepResult(step, "PASS", f"unittest discover OK ({len(test_files)} test module(s))")
    return StepResult(step, "FAIL", f"unittest discover failed with exit code {rc}: {last_line(err, out)}")


# ---------------------------------------------------------------------------
# Step 3: CLI_VALIDATE
# ---------------------------------------------------------------------------

def step_cli_validate(ctx: Context) -> StepResult:
    step = "CLI_VALIDATE"
    available, why = cli_availability(ctx.root)
    if not available:
        return ctx.skip_or_fail(step, why)
    print("    $ python -m failbench validate --strict")
    rc, out, err, problem = run_command(["-m", "failbench", "validate", "--strict"], ctx, CLI_TIMEOUT)
    print_capture(out, err)
    if problem is not None:
        return StepResult(step, "FAIL", f"CLI validate {problem}")
    combined = f"{out}\n{err}"
    if rc == 0:
        return StepResult(step, "PASS", "validate --strict returned 0")
    if looks_strict_unsupported(combined):
        print("    retrying once without --strict (flag not supported yet)")
        rc2, out2, err2, problem2 = run_command(["-m", "failbench", "validate"], ctx, CLI_TIMEOUT)
        print_capture(out2, err2)
        if problem2 is not None:
            return StepResult(step, "FAIL", f"CLI validate retry {problem2}")
        if rc2 == 0:
            return StepResult(step, "WARN", "validate passed without --strict (--strict flag is not supported yet)")
        return StepResult(step, "FAIL", f"validate failed without --strict as well (exit {rc2}): {last_line(err2, out2)}")
    if looks_cli_unimplemented(combined):
        return ctx.skip_or_fail(step, f"`validate` subcommand is not implemented yet: {last_line(err, out)}")
    return StepResult(step, "FAIL", f"validate --strict exited {rc}: {last_line(err, out)}")


# ---------------------------------------------------------------------------
# Step 4: DEMO_RUN
# ---------------------------------------------------------------------------

def step_demo_run(ctx: Context) -> StepResult:
    step = "DEMO_RUN"
    available, why = cli_availability(ctx.root)
    if not available:
        return ctx.skip_or_fail(step, why)
    problems: List[str] = []
    for out_dir, label in ((ctx.tmp_dir / "demo1", "A"), (ctx.tmp_dir / "demo2", "B")):
        print(f"    $ python -m failbench run --provider mock --demo --out {out_dir}")
        rc, out, err, problem = run_command(
            ["-m", "failbench", "run", "--provider", "mock", "--demo", "--out", str(out_dir)],
            ctx, DEMO_TIMEOUT)
        print_capture(out, err)
        if problem is not None:
            problems.append(f"run {label} {problem}")
            continue
        if rc != 0:
            if looks_cli_unimplemented(f"{out}\n{err}"):
                return ctx.skip_or_fail(step, f"`run` subcommand is not runnable yet: {last_line(err, out)}")
            problems.append(f"run {label} exited {rc}: {last_line(err, out)}")
            continue
        found = find_results_json(out_dir)
        if found is None:
            problems.append(f"run {label} exited 0 but wrote no results.json")
        elif label == "A":
            ctx.results_a = found
        else:
            ctx.results_b = found
    if problems:
        return StepResult(step, "FAIL", "; ".join(problems))
    if ctx.results_a is None or ctx.results_b is None:  # defensive
        return StepResult(step, "FAIL", "mock demo runs completed but results.json could not be located")
    return StepResult(step, "PASS", "two mock demo runs exited 0 and wrote results.json")


# ---------------------------------------------------------------------------
# Step 5: DETERMINISM
# ---------------------------------------------------------------------------

def probe_map(probes: Any) -> Tuple[Dict[str, Tuple[Optional[str], Optional[str]]], int, int]:
    """Map probe_id -> (status, response_sha256); return (mapping, usable, duplicates)."""
    mapping: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    if not isinstance(probes, list):
        return mapping, 0, 0
    usable = duplicates = 0
    for item in probes:
        if not isinstance(item, dict):
            continue
        probe_id = item.get("probe_id")
        if not isinstance(probe_id, str) or not probe_id:
            continue
        usable += 1
        if probe_id in mapping:
            duplicates += 1
            continue
        status, sha = item.get("status"), item.get("response_sha256")
        mapping[probe_id] = (status if isinstance(status, str) else None,
                             sha if isinstance(sha, str) else None)
    return mapping, usable, duplicates


def check_results_shape(run: Dict[str, Any]) -> List[str]:
    """Basic results.json contract checks (docs/CONTRACT.md section 7)."""
    problems: List[str] = []
    if run.get("schema") != 1:
        problems.append(f"schema={run.get('schema')!r} (expected 1)")
    if run.get("provider") != "mock":
        problems.append(f"provider={run.get('provider')!r} (expected 'mock')")
    probes, counts = run.get("probes"), run.get("counts")
    if not isinstance(counts, dict):
        problems.append("counts is missing or not an object")
    elif not isinstance(probes, list):
        problems.append("probes is missing or not a list")
    elif counts.get("probes") != len(probes):
        problems.append(f"counts.probes={counts.get('probes')!r} but len(probes)={len(probes)}")
    if isinstance(probes, list):
        bad = sorted({repr(item.get("status")) for item in probes
                      if isinstance(item, dict) and item.get("status") not in ALLOWED_STATUSES})
        if bad:
            problems.append("invalid probe status(es): " + ", ".join(bad[:3]))
        if any(not isinstance(item, dict) for item in probes):
            problems.append("some probe entries are not objects")
    return problems


def compare_runs(run_a: Dict[str, Any],
                 run_b: Dict[str, Any]) -> Tuple[List[str], int, int]:
    """Compare two demo runs; return (problems, probes_missing_sha, shared_probe_count)."""
    problems: List[str] = []
    counts_a = run_a.get("counts") if isinstance(run_a.get("counts"), dict) else {}
    counts_b = run_b.get("counts") if isinstance(run_b.get("counts"), dict) else {}
    if counts_a != counts_b:
        for key in sorted(set(counts_a) | set(counts_b)):
            if counts_a.get(key) != counts_b.get(key):
                problems.append(f"counts.{key}: {counts_a.get(key)!r} != {counts_b.get(key)!r}")
    probes_a = run_a.get("probes") if isinstance(run_a.get("probes"), list) else []
    probes_b = run_b.get("probes") if isinstance(run_b.get("probes"), list) else []
    map_a, usable_a, dups_a = probe_map(probes_a)
    map_b, usable_b, dups_b = probe_map(probes_b)
    if usable_a != len(probes_a):
        problems.append(f"{len(probes_a) - usable_a} probe entry(ies) in run A lack a usable probe_id")
    if usable_b != len(probes_b):
        problems.append(f"{len(probes_b) - usable_b} probe entry(ies) in run B lack a usable probe_id")
    if dups_a or dups_b:
        problems.append(f"duplicate probe_id(s): run A={dups_a}, run B={dups_b}")
    only_a, only_b = sorted(set(map_a) - set(map_b)), sorted(set(map_b) - set(map_a))
    if only_a:
        problems.append("probes only in run A: " + ", ".join(only_a[:5]) + (" ..." if len(only_a) > 5 else ""))
    if only_b:
        problems.append("probes only in run B: " + ", ".join(only_b[:5]) + (" ..." if len(only_b) > 5 else ""))
    shared = set(map_a) & set(map_b)
    differing = sorted(pid for pid in shared if map_a[pid] != map_b[pid])
    if differing:
        problems.append(f"{len(differing)} probe(s) differ on (status, response_sha256): "
                        + ", ".join(differing[:5]) + (" ..." if len(differing) > 5 else ""))
    missing_sha = sum(1 for pid in shared if map_a[pid][1] is None or map_b[pid][1] is None)
    return problems, missing_sha, len(shared)


def step_determinism(ctx: Context) -> StepResult:
    step = "DETERMINISM"
    if not (ctx.results_a and ctx.results_a.is_file() and ctx.results_b and ctx.results_b.is_file()):
        return StepResult(step, "SKIP", "demo results unavailable (blocked by DEMO_RUN)")
    print(f"    run A: {ctx.results_a}")
    print(f"    run B: {ctx.results_b}")
    try:
        run_a = load_results_json(ctx.results_a)
        run_b = load_results_json(ctx.results_b)
    except (OSError, ValueError) as exc:
        return StepResult(step, "FAIL", f"cannot read demo results: {clip(str(exc))}")
    problems = check_results_shape(run_a) + check_results_shape(run_b)
    compare_problems, missing_sha, probe_count = compare_runs(run_a, run_b)
    problems.extend(compare_problems)
    if problems:
        return StepResult(step, "FAIL", f"{len(problems)} issue(s): " + "; ".join(problems))
    counts = run_a.get("counts") or {}
    detail = (f"identical across {probe_count} probes (pass={counts.get('pass')}, "
              f"fail={counts.get('fail')}, error={counts.get('error')}); results.json shape OK")
    if missing_sha:
        return StepResult(step, "WARN", detail + f"; response_sha256 missing for {missing_sha} probe(s)")
    return StepResult(step, "PASS", detail)


# ---------------------------------------------------------------------------
# Step 6: REPORT
# ---------------------------------------------------------------------------

def step_report(ctx: Context) -> StepResult:
    step = "REPORT"
    if not (ctx.results_a and ctx.results_a.is_file()):
        return StepResult(step, "SKIP", "demo results unavailable (blocked by DEMO_RUN)")
    available, why = cli_availability(ctx.root)
    if not available:
        return ctx.skip_or_fail(step, why)
    run_dir, site_dir = ctx.results_a.parent, ctx.tmp_dir / "site"
    # Keep the QA run read-only with respect to committed artifacts: the report
    # generator's default would rewrite docs/RESULTS.md in the work tree. Render
    # the Markdown companion into the temp dir instead; the committed
    # docs/RESULTS.md is separately cross-checked by check_contract.py (C8).
    temp_md = ctx.tmp_dir / "RESULTS.md"
    print(f"    $ python -m failbench report --results {run_dir} --out {site_dir} "
          f"--results-md {temp_md}")
    args = ["-m", "failbench", "report", "--results", str(run_dir), "--out", str(site_dir),
            "--results-md", str(temp_md)]
    rc, out, err, problem = run_command(args, ctx, CLI_TIMEOUT)
    if rc != 0 and ("unrecognized arguments" in f"{out}\n{err}"
                    or "no such option" in f"{out}\n{err}".lower()):
        # Older report CLI without --results-md: retry and accept the side effect.
        print("    note: report CLI lacks --results-md; retrying without it")
        rc, out, err, problem = run_command(
            ["-m", "failbench", "report", "--results", str(run_dir), "--out", str(site_dir)],
            ctx, CLI_TIMEOUT)
    print_capture(out, err)
    if problem is not None:
        return StepResult(step, "FAIL", f"CLI report {problem}")
    if rc != 0:
        if looks_cli_unimplemented(f"{out}\n{err}"):
            return ctx.skip_or_fail(step, f"`report` subcommand is not implemented yet: {last_line(err, out)}")
        return StepResult(step, "FAIL", f"report exited {rc}: {last_line(err, out)}")
    index = site_dir / "index.html"
    if not index.is_file():
        nested = sorted(site_dir.rglob("index.html")) if site_dir.is_dir() else []
        if not nested:
            return StepResult(step, "FAIL", "report exited 0 but site/index.html was not generated")
        index = nested[0]
    ctx.site_index = index
    return StepResult(step, "PASS", f"generated {index.name} ({index.stat().st_size} bytes)")


# ---------------------------------------------------------------------------
# Step 7: SITE_SANITY
# ---------------------------------------------------------------------------

def step_site_sanity(ctx: Context) -> StepResult:
    step = "SITE_SANITY"
    if ctx.site_index is None or not ctx.site_index.is_file():
        return ctx.skip_or_fail(step, "site/index.html was not generated (blocked by REPORT)")
    try:
        raw = ctx.site_index.read_bytes()
        text = raw.decode("utf-8", "replace")
    except OSError as exc:
        return StepResult(step, "FAIL", f"cannot read {ctx.site_index.name}: {clip(str(exc))}")
    problems: List[str] = []
    if HONESTY_MARKER not in text:
        problems.append(f"missing honesty marker {HONESTY_MARKER!r}")
    if MOCK_MARKER not in text and MOCK_MARKER.lower() not in text.lower():
        problems.append("missing mock-provider disclosure ('mock provider')")
    if REMOTE_SCRIPT_RE.search(text):
        problems.append('remote <script src="http..."> reference found')
    if REMOTE_LINK_RE.search(text):
        problems.append('remote <link href="http..."> reference found')
    if "fetch(" in text:
        problems.append("fetch( call found")
    if "XMLHttpRequest" in text:
        problems.append("XMLHttpRequest reference found")
    if len(raw) >= SITE_MAX_BYTES:
        problems.append(f"size {len(raw)} bytes is >= 3 MB")
    if problems:
        return StepResult(step, "FAIL", "; ".join(problems))
    return StepResult(step, "PASS", f"{len(raw)} bytes; honesty markers present; no remote script/link/fetch/XHR")


# ---------------------------------------------------------------------------
# Step 8: GATE_DEMO_VS_RERUN
# ---------------------------------------------------------------------------

def step_gate(ctx: Context) -> StepResult:
    step = "GATE_DEMO_VS_RERUN"
    if not (ctx.results_a and ctx.results_a.is_file() and ctx.results_b and ctx.results_b.is_file()):
        return StepResult(step, "SKIP", "demo results unavailable (blocked by DEMO_RUN)")
    available, why = cli_availability(ctx.root)
    if not available:
        return ctx.skip_or_fail(step, why)
    print(f"    $ python -m failbench gate --baseline {ctx.results_a} --current {ctx.results_b}")
    rc, out, err, problem = run_command(
        ["-m", "failbench", "gate", "--baseline", str(ctx.results_a), "--current", str(ctx.results_b)],
        ctx, GATE_TIMEOUT)
    print_capture(out, err)
    if problem is not None:
        return StepResult(step, "FAIL", f"CLI gate {problem}")
    if rc == 0:
        return StepResult(step, "PASS", "gate reports no regressions between demo run A and re-run B")
    if looks_cli_unimplemented(f"{out}\n{err}"):
        return ctx.skip_or_fail(step, f"`gate` subcommand is not implemented yet: {last_line(err, out)}")
    return StepResult(step, "FAIL", f"gate exited {rc}: {last_line(err, out)}")


# ---------------------------------------------------------------------------
# Step 9: ROOT_FILES
# ---------------------------------------------------------------------------

def step_root_files(ctx: Context) -> StepResult:
    step = "ROOT_FILES"
    missing = [rel for rel in REQUIRED_ROOT_FILES if not (ctx.root / rel).is_file()]
    if not missing:
        return StepResult(step, "PASS", f"all {len(REQUIRED_ROOT_FILES)} required root files present")
    return StepResult(step, "WARN" if ctx.lenient else "FAIL",
                      "missing root file(s): " + ", ".join(missing))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

STEPS: Tuple[Tuple[str, Any], ...] = (
    ("CONTRACT", step_contract),
    ("UNITTEST", step_unittest),
    ("CLI_VALIDATE", step_cli_validate),
    ("DEMO_RUN", step_demo_run),
    ("DETERMINISM", step_determinism),
    ("REPORT", step_report),
    ("SITE_SANITY", step_site_sanity),
    ("GATE_DEMO_VS_RERUN", step_gate),
    ("ROOT_FILES", step_root_files),
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FailBench offline QA orchestrator (stdlib only, never uses the network).")
    parser.add_argument("--root", type=Path, default=None,
                        help="repository root (default: two directories above this script)")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="treat a missing/incomplete corpus as SKIP instead of FAIL")
    parser.add_argument("--keep", action="store_true",
                        help="keep the temporary demo directory after the run")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Never crash while printing captured child output that contains characters
    # the active console encoding cannot represent (legacy Windows codepages).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    args = parse_args(argv)
    # Never pollute the repository with fresh __pycache__ artifacts from this process.
    sys.dont_write_bytecode = True
    root = Path(args.root).resolve() if args.root is not None else Path(__file__).resolve().parents[2]
    if not root.is_dir():
        print(f"ERROR: repository root does not exist: {root}")
        return 2

    complete, corpus_detail = corpus_status(root)
    explicit = bool(args.allow_incomplete)
    if explicit:
        mode = "lenient (explicit --allow-incomplete)"
    elif not complete:
        mode = "lenient (auto: incomplete corpus)"
    else:
        mode = "strict (complete corpus)"

    print("FailBench offline validation suite")
    print(f"  root   : {root}")
    print(f"  python : {sys.version.split()[0]} ({sys.executable})")
    print(f"  mode   : {mode}")
    print(f"  corpus : {corpus_detail}")

    env = repo_env(root)
    tmp_dir = Path(tempfile.mkdtemp(prefix="failbench-qa-"))
    ctx = Context(root, env, not complete, explicit, corpus_detail, tmp_dir)
    print(f"  temp   : {tmp_dir}")

    results: List[StepResult] = []
    try:
        for index, (name, step_fn) in enumerate(STEPS, 1):
            print_step_start(index, len(STEPS), name)
            try:
                result = step_fn(ctx)
            except Exception as exc:  # a step bug must never traceback
                result = StepResult(name, "FAIL", f"internal error: {type(exc).__name__}: {exc}")
            results.append(result)
            print(f"    -> {result.status}: {result.detail}")
    finally:
        if args.keep:
            print()
            print(f"Kept temp dir: {tmp_dir}")
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            if tmp_dir.exists():
                print(f"warning: could not completely remove temp dir: {tmp_dir}")

    print()
    print("Validation summary:")
    print_table(results)

    passed = sum(1 for r in results if r.status in ("PASS", "WARN"))
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    warned = sum(1 for r in results if r.status == "WARN")
    print(f"RESULT: {'FAIL' if failed else 'PASS'} ({passed} passed, {failed} failed, {skipped} skipped)")
    if warned:
        print(f"Note: {warned} passing step(s) reported warnings (see table).")
    if failed:
        print("Failing steps: " + ", ".join(r.step for r in results if r.status == "FAIL"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
