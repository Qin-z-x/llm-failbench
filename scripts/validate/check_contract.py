#!/usr/bin/env python3
"""Strict contract gate for the FailBench repository (checks C1-C10).

Usage::

    python scripts/validate/check_contract.py                  # strict (default)
    python scripts/validate/check_contract.py --allow-incomplete
    python scripts/validate/check_contract.py --root PATH

Checks (details in docs/CONTRACT.md): C1 schema.validate_all() zero errors;
C2 every class has >= 8 probes and >= 8 evidence records; C3 probe/evidence ids
are unique; C4 no placeholder text in committed deliverables (docs/ and tests/
exempt; example.* matched case-insensitively, uppercase PLACEHOLDER/TODO:/XXX
markers matched literally); C5 no secret-like values in tracked text files (masked output only);
C6 results/demo/results.json matches CONTRACT section 7; C7 site/index.html is
self-contained, < 3MB and states the mock-provider honesty note; C8
docs/RESULTS.md carries the honesty sentence and the demo counts; C9 README.md
explains the mock provider and lists runnable commands; C10 all probe JSON and
evidence JSONL content parses as UTF-8 JSON objects.

Exit code 0 only when no check FAILs. Strict is the default; with
``--allow-incomplete`` missing-data checks (C2, C6-C10) become WARN while schema
errors, duplicates, placeholders, secrets, content violations and parse errors
always FAIL. If both --strict and --allow-incomplete are passed, strict wins.
Stdlib only; plain ASCII output (no ANSI colors) for CI readability.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]  # <root>/scripts/validate/check_contract.py

# --- constants -------------------------------------------------------------
MIN_PER_CLASS = 8
HONESTY_SENTENCE = "No live model endpoint was available during this build"
ALLOWED_RESULT_STATUSES = ("pass", "fail", "error")
MAX_SITE_BYTES = 3 * 1024 * 1024  # "< 3MB" per the gate specification
DEMO_RESULTS_REL = Path("results") / "demo" / "results.json"
SITE_INDEX_REL = Path("site") / "index.html"
RESULTS_DOC_REL = Path("docs") / "RESULTS.md"
README_REL = Path("README.md")

# Walk exclusions. `_scratch` may hold a portable toolchain and is never scanned.
# `.svg` is deliberately absent from binaries: SVG is text and must be scanned.
SKIP_DIR_NAMES = {".git", "_scratch", "__pycache__", ".venv", "node_modules"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".zip", ".gz", ".whl",
                   ".pyc", ".pdf", ".7z", ".tar", ".bz2", ".xz", ".exe", ".dll", ".so",
                   ".dylib", ".bin", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3",
                   ".mp4", ".mov", ".jar", ".class", ".o", ".a"}
MAX_SCAN_BYTES = 4 * 1024 * 1024  # skip absurdly large "text" files
CHECKER_REL = Path("scripts") / "validate" / "check_contract.py"  # embeds patterns below

# C4 placeholders. Two case rules, matching the documented intent (the gate
# spec lists the markers as uppercase literals):
#  * placeholder *data* -- example.com / example.org / "lorem ipsum" -- is
#    matched case-insensitively.
#  * unfinished-content *markers* -- PLACEHOLDER, TODO:, XXX -- are matched
#    exactly as specified (uppercase). This deliberately avoids false positives
#    on legitimate prose ("replace every placeholder"), GitHub issue-form
#    `placeholder:` YAML keys, and HTML `placeholder=` input attributes.
PLACEHOLDER_DATA_RE = re.compile(r"example\.com|example\.org|lorem\s+ipsum", re.IGNORECASE)
PLACEHOLDER_MARKER_RE = re.compile(r"PLACEHOLDER|TODO:|XXX")
# Files whose stated purpose is to detect placeholder-looking values: their own
# pattern constants are not unfinished content. Keep this list tiny and
# justified (documented in docs/reviews/QA_REPORT.md).
PLACEHOLDER_SCAN_EXEMPT_FILES = frozenset({"scripts/evidence/verify_provenance.py"})
# C5 secrets: (label, compiled pattern, group index holding the secret value).
# Prefixes are assembled from parts so this file does not read as fake credentials.
_SECRET_KEY_PREFIX = "s" + "k" + "-"
SECRET_PATTERNS = (
    ("openai-style API key", re.compile(_SECRET_KEY_PREFIX + r"[A-Za-z0-9]{16,}"), 0),
    ("GitHub classic token", re.compile(r"ghp" + r"_[A-Za-z0-9]{20,}"), 0),
    ("GitHub fine-grained token", re.compile(r"github" + r"_pat_[A-Za-z0-9_]{20,}"), 0),
    ("AWS access key id", re.compile(r"AKIA" + r"[0-9A-Z]{16}"), 0),
    ("api_key assignment", re.compile(r"""api_key\s*=\s*["']([A-Za-z0-9_\-]{12,})["']"""), 1),
)
PLACEHOLDER_MARKERS = ("YOUR", "REDACTED", "EXAMPLE", "CHANGEME", "XXX")


# --- helpers ---------------------------------------------------------------
def _is_int(value: object) -> bool:
    """Return True for real integers only (bool is not an integer here)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _summarize(items: list[str], limit: int = 6, width: int = 400) -> str:
    """Join the first ``limit`` items with '; ', note omissions, then truncate."""
    shown = "; ".join(items[:limit]) + (f"; (+{len(items) - limit} more)" if len(items) > limit else "")
    return shown if len(shown) <= width else shown[: max(width - 3, 0)] + "..."


def _rel(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` with forward slashes."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:  # pragma: no cover - defensive; paths come from a walk
        return path.as_posix()


def _read_text_file(path: Path) -> str | None:
    """Read ``path`` as strict UTF-8 text; None means binary/unreadable/oversized."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > MAX_SCAN_BYTES:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _looks_like_placeholder_value(value: str) -> bool:
    """True for placeholder-shaped secret matches (a marker inside, or all-uppercase).

    Deliberate consequence, mandated by the gate spec: an AWS-style ``AKIA...``
    token is uppercase by convention and is therefore treated as placeholder-like.
    """
    if any(marker in value.upper() for marker in PLACEHOLDER_MARKERS):
        return True
    letters = [char for char in value if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def _mask_secret(value: str) -> str:
    """Mask the middle of a secret so it is never printed in full."""
    if len(value) <= 2:
        return "*" * len(value)
    if len(value) <= 8:
        return value[0] + "*" * (len(value) - 2) + value[-1]
    keep = min(4, len(value) // 4)
    return value[:keep] + "*" * min(len(value) - 2 * keep, 16) + value[-keep:]


# --- contract checker ------------------------------------------------------
class ContractChecker:
    """Run checks C1-C10 against one repository root, one PASS/FAIL/WARN line each."""

    def __init__(self, root: Path, allow_incomplete: bool) -> None:
        self.root = root
        self.allow_incomplete = allow_incomplete
        self.checks = self.passed = self.failures = self.warnings = 0
        self.schema = self.report = None  # set by C1; reused by C2/C6
        self._demo_state = "unchecked"    # missing | invalid | ok | unverified (C6)
        self._demo_results = None         # parsed demo JSON, reused by C8

    def _emit(self, status: str, code: str, message: str, extra_warning: bool = False) -> None:
        """Print one check line and update the counters."""
        self.checks += 1
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failures += 1
        elif status == "WARN":
            self.warnings += 1
        self.warnings += int(extra_warning)
        print(f"{status} [{code}] {message}")

    def _missing(self, code: str, message: str) -> None:
        """Report a missing data artifact: FAIL in strict mode, WARN when incomplete."""
        self._emit("WARN" if self.allow_incomplete else "FAIL", code,
                   message + (" [allow-incomplete]" if self.allow_incomplete else ""))

    # -- walking / loading helpers -----------------------------------------
    def _iter_probe_files(self) -> list[tuple[str, Path]]:
        """Return (relative path, path) for probe JSON files, sorted."""
        base = self.root / "probes"
        if not base.is_dir():
            return []
        paths = sorted(p for p in base.rglob("*.json") if p.is_file() and not p.name.startswith("_"))
        return [(_rel(path, self.root), path) for path in paths]

    def _iter_evidence_files(self) -> list[tuple[str, Path]]:
        """Return (relative path, path) for evidence JSONL files, sorted."""
        base = self.root / "data" / "evidence"
        return [(_rel(p, self.root), p) for p in sorted(base.glob("*.jsonl"))] if base.is_dir() else []

    def _iter_scanned_files(self, exclude_top: tuple[str, ...] = ()) -> list[tuple[str, str]]:
        """Collect (relative path, UTF-8 text) for scannable text files.

        ``exclude_top`` names top-level dirs to skip entirely (C4 exempts docs/ and tests/).
        """
        excluded = {name.lower() for name in exclude_top}
        collected: list[tuple[str, str]] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d.lower() not in SKIP_DIR_NAMES)
            rel_dir = Path(os.path.relpath(dirpath, self.root))
            parts = () if rel_dir == Path(".") else rel_dir.parts
            if excluded and parts and parts[0].lower() in excluded:
                dirnames[:] = []
                continue
            for name in sorted(filenames):
                rel = Path(*parts, name).as_posix() if parts else name
                if rel.lower() == CHECKER_REL.as_posix().lower():
                    continue
                if Path(name).suffix.lower() in BINARY_SUFFIXES:
                    continue
                text = _read_text_file(Path(dirpath) / name)
                if text is not None:
                    collected.append((rel, text))
        return collected

    @staticmethod
    def _quiet_json(path: Path):
        """Load a JSON file, returning None for unreadable/invalid content."""
        text = _read_text_file(path)
        try:
            return json.loads(text) if text is not None else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _evidence_records(path: Path):
        """Yield (line number, object) for each parseable evidence JSONL line."""
        for lineno, line in enumerate((_read_text_file(path) or "").splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                continue  # C1/C10 report parse errors
            if isinstance(data, dict):
                yield lineno, data

    def _known_demo_counts(self) -> dict[str, int] | None:
        """Return the four validated integer demo counts, or None when unavailable."""
        counts = self._demo_results.get("counts") if isinstance(self._demo_results, dict) else None
        if not isinstance(counts, dict):
            return None
        values = {field: counts.get(field) for field in ("probes", "pass", "fail", "error")}
        return values if all(_is_int(v) and v >= 0 for v in values.values()) else None

    # -- C1: schema validation ---------------------------------------------
    def check_c1(self) -> None:
        """C1: failbench.schema.validate_all() reports zero errors."""
        root_str = str(self.root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        try:
            from failbench import schema as schema_module
            report = schema_module.validate_all()
        except Exception as exc:  # noqa: BLE001 - any load failure is a gate failure
            self._emit("FAIL", "C1", f"schema validation: cannot load/validate "
                                     f"failbench.schema from {root_str}: {type(exc).__name__}: {exc}")
            return
        self.schema, self.report = schema_module, report
        errors = list(report.get("errors") or [])
        probes, evidence = report.get("probe_count", 0), report.get("evidence_count", 0)
        if errors:
            self._emit("FAIL", "C1", f"schema validation: {len(errors)} error(s) (probes={probes}, "
                                     f"evidence={evidence}): {_summarize(errors)}")
        else:
            self._emit("PASS", "C1", f"schema validation: 0 errors (probes={probes}, evidence={evidence})")

    # -- C2: per-class coverage --------------------------------------------
    def check_c2(self) -> None:
        """C2: every class has >= 8 probes and >= 8 evidence records."""
        if self.schema is None or self.report is None:
            self._emit("FAIL", "C2", "per-class counts: cannot verify (failbench.schema unavailable, see C1)")
            return
        probes = self.report.get("probe_by_class") or {}
        evidence = self.report.get("evidence_by_class") or {}
        classes = list(self.schema.CLASSES)
        offenders = [f"{name}: probes={probes.get(name, 0) or 0}/{MIN_PER_CLASS}, "
                     f"evidence={evidence.get(name, 0) or 0}/{MIN_PER_CLASS}"
                     for name in classes
                     if (probes.get(name, 0) or 0) < MIN_PER_CLASS
                     or (evidence.get(name, 0) or 0) < MIN_PER_CLASS]
        if offenders:
            self._missing("C2", f"per-class coverage below minimum in {len(offenders)}/"
                                f"{len(classes)} classes: {_summarize(offenders)}")
        else:
            self._emit("PASS", "C2", f"per-class counts: all {len(classes)} classes have >= "
                                     f"{MIN_PER_CLASS} probes and >= {MIN_PER_CLASS} evidence records")

    # -- C3: unique ids ----------------------------------------------------
    def check_c3(self) -> None:
        """C3: probe ids and evidence ids are unique across the corpus."""
        probe_locations: dict[str, list[str]] = {}
        for rel, path in self._iter_probe_files():
            data = self._quiet_json(path)
            if isinstance(data, dict) and isinstance(data.get("id"), str):
                probe_locations.setdefault(data["id"], []).append(rel)
        evidence_locations: dict[str, list[str]] = {}
        for rel, path in self._iter_evidence_files():
            for lineno, data in self._evidence_records(path):
                if isinstance(data.get("id"), str):
                    evidence_locations.setdefault(data["id"], []).append(f"{rel}:{lineno}")
        dup_probes = {rid: locs for rid, locs in probe_locations.items() if len(locs) > 1}
        dup_evidence = {rid: locs for rid, locs in evidence_locations.items() if len(locs) > 1}
        if not dup_probes and not dup_evidence:
            self._emit("PASS", "C3", f"unique ids: {len(probe_locations)} probe ids and "
                                     f"{len(evidence_locations)} evidence ids are unique")
            return
        details = [f"probe id {rid} in {', '.join(locs[:3])}" for rid, locs in list(dup_probes.items())[:4]]
        details += [f"evidence id {rid} in {', '.join(locs[:3])}" for rid, locs in list(dup_evidence.items())[:4]]
        self._emit("FAIL", "C3", f"unique ids: {len(dup_probes) + len(dup_evidence)} duplicate id(s): "
                                 f"{_summarize(details)}")

    # -- C4: placeholder scan ----------------------------------------------
    def check_c4(self) -> None:
        """C4: no placeholder text in committed deliverables."""
        hits, scanned, exempted = [], 0, 0
        for rel, text in self._iter_scanned_files(exclude_top=("docs", "tests")):
            if rel in PLACEHOLDER_SCAN_EXEMPT_FILES:
                exempted += 1
                continue
            scanned += 1
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern in (PLACEHOLDER_DATA_RE, PLACEHOLDER_MARKER_RE):
                    for match in pattern.finditer(line):
                        hits.append(f"{rel}:{lineno}: {match.group(0)}")
        note = f" ({exempted} detector file(s) exempted)" if exempted else ""
        if hits:
            self._emit("FAIL", "C4", f"placeholder text found in committed deliverables: {_summarize(hits)}")
        else:
            self._emit("PASS", "C4", f"placeholder scan: no placeholder patterns in {scanned} text files{note}")

    # -- C5: secret scan ---------------------------------------------------
    def check_c5(self) -> None:
        """C5: no secret-like values in tracked text files (masked output).

        Uses the same walk as C4 (tests/ fixtures stay exempt) but no longer
        exempts docs/, so leaked-looking values in docs are still caught.
        """
        hits, scanned = [], 0
        for rel, text in self._iter_scanned_files(exclude_top=("tests",)):
            scanned += 1
            for lineno, line in enumerate(text.splitlines(), 1):
                for label, pattern, group in SECRET_PATTERNS:
                    for match in pattern.finditer(line):
                        value = match.group(group)
                        if value and not _looks_like_placeholder_value(value):
                            hits.append(f"{rel}:{lineno}: {label}: {_mask_secret(value)}")
        if hits:
            self._emit("FAIL", "C5", f"secret-like values found in tracked files: {_summarize(hits)}")
        else:
            self._emit("PASS", "C5", f"secret scan: no secret-like values in {scanned} text files")

    # -- C6: demo results --------------------------------------------------
    def _validate_demo_results(self, data: dict) -> list[str]:
        """Validate results/demo/results.json against CONTRACT section 7."""
        problems: list[str] = []

        def bad(message: str) -> None:
            problems.append(message)

        if not _is_int(data.get("schema")) or data.get("schema") != 1:
            bad(f"schema must be integer 1, got {data.get('schema')!r}")
        for field in ("run_id", "suite_version"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                bad(f"{field} must be a non-empty string")
        provider = data.get("provider")
        if not isinstance(provider, str) or not provider:
            bad("provider must be a non-empty string")
        elif provider != "mock":
            bad(f"committed demo provider must be 'mock', got {provider!r}")

        counts = data.get("counts")
        count_values: dict[str, int] = {}
        if not isinstance(counts, dict):
            bad("counts must be an object")
        else:
            for field in ("probes", "pass", "fail", "error"):
                value = counts.get(field)
                if _is_int(value) and value >= 0:
                    count_values[field] = value
                else:
                    bad(f"counts.{field} must be a non-negative integer")
            if len(count_values) == 4 and (count_values["pass"] + count_values["fail"]
                                           + count_values["error"] != count_values["probes"]):
                bad("counts.pass + counts.fail + counts.error must equal counts.probes")

        probes = data.get("probes")
        statuses: list[str] = []
        if not isinstance(probes, list):
            bad("probes must be a list")
        else:
            if "probes" in count_values and count_values["probes"] != len(probes):
                bad(f"counts.probes ({count_values['probes']}) must equal len(probes) ({len(probes)})")
            for index, item in enumerate(probes):
                prefix = f"probes[{index}]"
                if not isinstance(item, dict):
                    bad(f"{prefix} must be an object")
                    continue
                for field in ("probe_id", "reason", "response_sha256"):
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        bad(f"{prefix}.{field} must be a non-empty string")
                if item.get("class") not in self.schema.CLASSES:
                    bad(f"{prefix}.class {item.get('class')!r} is not in failbench.schema.CLASSES")
                if item.get("status") in ALLOWED_RESULT_STATUSES:
                    statuses.append(item["status"])
                else:
                    bad(f"{prefix}.status must be one of pass|fail|error")
            if len(statuses) == len(probes) and len(count_values) == 4:
                for status in ALLOWED_RESULT_STATUSES:
                    actual = statuses.count(status)
                    if count_values[status] != actual:
                        bad(f"counts.{status} is {count_values[status]} but probes have {actual}")

        by_class = data.get("by_class")
        if by_class is not None:
            if not isinstance(by_class, dict):
                bad("by_class must be an object")
            else:
                total = 0
                for name, entry in by_class.items():
                    fields = ("total", "pass", "fail", "error")
                    values = {f: entry.get(f) for f in fields} if isinstance(entry, dict) else {}
                    if len(values) < 4 or not all(_is_int(v) and v >= 0 for v in values.values()):
                        bad(f"by_class.{name} must be an object with non-negative integer "
                            f"{'/'.join(fields)}")
                    else:
                        total += values["total"]
                        if values["pass"] + values["fail"] + values["error"] != values["total"]:
                            bad(f"by_class.{name} pass+fail+error must equal total")
                if "probes" in count_values and total != count_values["probes"]:
                    bad(f"sum of by_class totals ({total}) must equal counts.probes ({count_values['probes']})")
        return problems

    def check_c6(self) -> None:
        """C6: results/demo/results.json exists and matches CONTRACT section 7."""
        rel = DEMO_RESULTS_REL.as_posix()
        path = self.root / DEMO_RESULTS_REL
        if not path.is_file():
            self._demo_state = "missing"
            self._missing("C6", f"missing required demo results file: {rel}")
            return
        try:
            data = json.loads(path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._demo_state = "invalid"
            self._emit("FAIL", "C6", f"cannot parse {rel}: {type(exc).__name__}: {exc}")
            return
        self._demo_results = data
        if self.schema is None:
            self._demo_state = "unverified"
            self._emit("FAIL", "C6", f"cannot verify {rel}: failbench.schema unavailable (see C1)")
            return
        if not isinstance(data, dict):
            self._demo_state = "invalid"
            self._emit("FAIL", "C6", f"{rel}: top-level JSON value must be an object")
            return
        problems = self._validate_demo_results(data)
        if problems:
            self._demo_state = "invalid"
            self._emit("FAIL", "C6", f"{rel}: {_summarize(problems)}")
        else:
            self._demo_state = "ok"
            c = data["counts"]
            self._emit("PASS", "C6", f"demo results valid: provider={data['provider']}, "
                                     f"probes={c['probes']} pass={c['pass']} fail={c['fail']} "
                                     f"error={c['error']}")

    # -- C7: static site honesty -------------------------------------------
    def check_c7(self) -> None:
        """C7: site/index.html is self-contained, < 3MB and honest."""
        rel = SITE_INDEX_REL.as_posix()
        path = self.root / SITE_INDEX_REL
        if not path.is_file():
            self._missing("C7", f"missing required static dashboard: {rel}")
            return
        text = _read_text_file(path)
        if text is None:
            self._emit("FAIL", "C7", f"cannot read {rel} as UTF-8 text")
            return
        size = path.stat().st_size
        problems = []
        if size >= MAX_SITE_BYTES:
            problems.append(f"file size {size} bytes must be < {MAX_SITE_BYTES} bytes (3MB)")
        if HONESTY_SENTENCE not in text:
            problems.append("missing honesty marker text")
        if "mock provider" not in text:
            problems.append("missing 'mock provider' label")
        external = [label for label, pattern in (
            ('external <script src="http...">', r"""<script\b[^>]*\bsrc\s*=\s*["']?\s*https?://"""),
            ('external <link href="http...">', r"""<link\b[^>]*\bhref\s*=\s*["']?\s*https?://"""),
            ("fetch(", r"fetch\("),
            ("XMLHttpRequest", r"XMLHttpRequest"),
        ) if re.search(pattern, text)]
        if external:
            problems.append("external resource loading/network API: " + ", ".join(external))
        if problems:
            self._emit("FAIL", "C7", f"{rel}: {_summarize(problems)}")
        else:
            self._emit("PASS", "C7", f"site is self-contained and honest: {rel} "
                                     f"({size} bytes, honesty markers present)")

    # -- C8: RESULTS.md honesty + counts -----------------------------------
    def check_c8(self) -> None:
        """C8: docs/RESULTS.md honesty sentence and numbers match the demo run."""
        rel = RESULTS_DOC_REL.as_posix()
        path = self.root / RESULTS_DOC_REL
        if not path.is_file():
            self._missing("C8", f"missing required results document: {rel}")
            return
        text = _read_text_file(path)
        if text is None:
            self._emit("FAIL", "C8", f"cannot read {rel} as UTF-8 text")
            return
        problems = []
        if HONESTY_SENTENCE not in text:
            problems.append("missing required honesty sentence: " + HONESTY_SENTENCE)
        unavailable_note = ""
        counts = self._known_demo_counts()
        demo_rel = DEMO_RESULTS_REL.as_posix()
        if counts is None:
            if self._demo_state == "missing":
                message = f"cannot cross-check counts: {demo_rel} is missing (see C6)"
                if self.allow_incomplete:
                    unavailable_note = message
                else:
                    problems.append(message)
            elif self._demo_state == "unverified":
                problems.append("cannot cross-check counts: failbench.schema unavailable (see C1)")
            else:
                problems.append(f"cannot cross-check counts: {demo_rel} is invalid (see C6)")
        else:
            missing_tokens = [f"{field}={value}" for field, value in counts.items()
                              if not re.search(rf"\b{value}\b", text)]
            if missing_tokens:
                problems.append("demo counts missing as standalone tokens in RESULTS.md: "
                                + ", ".join(missing_tokens))
        pass_rate_note = ""
        if re.search(r"(?i)pass\s*rate", text) or re.search(r"\d+(?:\.\d+)?\s*%", text):
            pass_rate_note = "pass-rate/percentage present; derived values are display-only"
        if problems:
            self._emit("FAIL", "C8", f"{rel}: {_summarize(problems)}")
        elif unavailable_note:
            self._emit("WARN", "C8", f"{rel}: {unavailable_note}"
                                     + (f"; note: {pass_rate_note}" if pass_rate_note else "")
                                     + " [allow-incomplete]")
        else:
            self._emit("PASS", "C8", f"{rel}: honesty sentence present and demo counts "
                                     f"(probes={counts['probes']} pass={counts['pass']} "
                                     f"fail={counts['fail']} error={counts['error']}) found as tokens"
                                     + (f"; note: {pass_rate_note}" if pass_rate_note else ""),
                       extra_warning=bool(pass_rate_note))

    # -- C9: README honesty + commands -------------------------------------
    def check_c9(self) -> None:
        """C9: README.md explains the mock provider and lists runnable commands."""
        rel = README_REL.as_posix()
        path = self.root / README_REL
        if not path.is_file():
            self._missing("C9", f"missing required README: {rel}")
            return
        text = _read_text_file(path)
        if text is None:
            self._emit("FAIL", "C9", f"cannot read {rel} as UTF-8 text")
            return
        lower = text.lower()
        problems = []
        if "mock" not in lower or not ("demo" in lower or "provider" in lower):
            problems.append("missing mock-provider honesty note (need 'mock' plus 'demo' or 'provider')")
        problems += [f"missing runnable command: {command}" for command in
                     ("python -m failbench run", "python -m failbench validate")
                     if command not in text]
        if problems:
            self._emit("FAIL", "C9", f"{rel}: {_summarize(problems)}")
        else:
            self._emit("PASS", "C9", "README explains the mock provider and lists runnable CLI commands")

    # -- C10: JSON parse gate ----------------------------------------------
    def check_c10(self) -> None:
        """C10: all probe JSON files and evidence JSONL lines parse as UTF-8 objects."""
        probes_dir = self.root / "probes"
        evidence_dir = self.root / "data" / "evidence"
        missing_dirs = [name for name, base in (("probes/", probes_dir),
                                                ("data/evidence/", evidence_dir))
                        if not base.is_dir()]
        parse_errors: list[str] = []
        probe_files = evidence_records = 0
        probe_paths = probes_dir.rglob("*.json") if probes_dir.is_dir() else ()
        # Underscore-prefixed files (e.g. probes/_index.json) are not probe files;
        # failbench.schema skips them, so skip them here too (C1 counts then agree).
        probe_paths = [item for item in probe_paths
                       if item.is_file() and not item.name.startswith("_")]
        for path in sorted(probe_paths):
            rel = _rel(path, self.root)
            try:
                data = json.loads(path.read_bytes().decode("utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                parse_errors.append(f"{rel}: {type(exc).__name__}: {exc}")
                continue
            except json.JSONDecodeError as exc:
                parse_errors.append(f"{rel}:{exc.lineno}: invalid JSON: {exc.msg}")
                continue
            probe_files += 1
            if not isinstance(data, dict):
                parse_errors.append(f"{rel}: top-level JSON value must be an object")
        evidence_paths = evidence_dir.glob("*.jsonl") if evidence_dir.is_dir() else ()
        for path in sorted(item for item in evidence_paths if item.is_file()):
            rel = _rel(path, self.root)
            text = _read_text_file(path)
            if text is None:
                parse_errors.append(f"{rel}: unreadable or not valid UTF-8 text")
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    parse_errors.append(f"{rel}:{lineno}: invalid JSON: {exc.msg}")
                    continue
                evidence_records += 1
                if not isinstance(record, dict):
                    parse_errors.append(f"{rel}:{lineno}: evidence record must be an object")
        if parse_errors:
            self._emit("FAIL", "C10", f"JSON parse errors: {len(parse_errors)} (parsed {probe_files} "
                                      f"probe files, {evidence_records} evidence records): "
                                      f"{_summarize(parse_errors)}")
        elif missing_dirs:
            self._missing("C10", f"missing input directorie(s): {', '.join(missing_dirs)}")
        else:
            self._emit("PASS", "C10", f"parsed {probe_files} probe JSON files and "
                                      f"{evidence_records} evidence JSONL records without error")

    # -- orchestration -----------------------------------------------------
    def run(self) -> int:
        """Run all checks in order and print the summary; return an exit code."""
        if not self.root.is_dir():
            self._emit("FAIL", "C1", f"repo root not found: {self.root}")
            self._finish()
            return 1
        checks = (self.check_c1, self.check_c2, self.check_c3, self.check_c4, self.check_c5,
                  self.check_c6, self.check_c7, self.check_c8, self.check_c9, self.check_c10)
        for index, check in enumerate(checks, 1):
            try:
                check()
            except Exception as exc:  # noqa: BLE001 - a gate must never traceback
                self._emit("FAIL", f"C{index}", f"internal error in C{index}: "
                                                f"{type(exc).__name__}: {exc}")
        self._finish()
        return 0 if self.failures == 0 else 1

    def _finish(self) -> None:
        """Print the summary counts and the final CONTRACT verdict line."""
        corpus = ""
        if self.report is not None:
            corpus = (f"; probes={self.report.get('probe_count', 0)}"
                      f", evidence={self.report.get('evidence_count', 0)}")
        print(f"SUMMARY: checks={self.checks}, pass={self.passed}, "
              f"warn={self.warnings}, fail={self.failures}{corpus}")
        print(f"CONTRACT: {'FAIL' if self.failures else 'PASS'} "
              f"({self.failures} failures, {self.warnings} warnings)")


# --- CLI -------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """Entry point: parse arguments, run the gate, return the exit code."""
    parser = argparse.ArgumentParser(
        prog="check_contract.py",
        description=("Strict FailBench contract gate (checks C1-C10 from docs/CONTRACT.md). "
                     "Strict mode is the default; --strict is accepted for explicitness. "
                     "When both --strict and --allow-incomplete are given, strict wins."),
    )
    parser.add_argument("--strict", action="store_true",
                        help="treat missing data artifacts as failures (default)")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="downgrade missing data artifacts to WARN for early-stage runs")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help=f"repository root to check (default: {DEFAULT_ROOT})")
    args = parser.parse_args(argv)
    # Never traceback on paths/messages the active console encoding cannot show.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    checker = ContractChecker(args.root.expanduser().resolve(),
                              args.allow_incomplete and not args.strict)
    try:
        return checker.run()
    except Exception as exc:  # noqa: BLE001 - last-resort guard, never traceback
        print(f"FAIL [C0] unexpected gate failure: {type(exc).__name__}: {exc}")
        print("CONTRACT: FAIL (1 failures, 0 warnings)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
