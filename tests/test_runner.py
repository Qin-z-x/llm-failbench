"""Contract tests for ``failbench.runner`` (stdlib only, fully offline).

The runner's public API is specified in ``docs/CONTRACT.md`` (sections 6-8) and
in the W3 runner task:

* ``run_from_paths(out_dir=..., provider=..., probes_dir=..., concurrency=...,
  class_filter=..., limit=..., repeats_override=..., progress=...) -> dict``
* per-probe error isolation, deterministic ordering, all-repeats-must-pass
  scoring, atomic ``results.json`` + ``raw.jsonl`` artifacts, and
  ``runner.RunError`` for unusable input/output.

These tests use an in-process ``ScriptedProvider`` and synthetic fixture probes
written to temporary directories (via ``tests.support``). No network access, no
real API keys and no corpus files are involved.

Run from the repository root::

    python -m unittest tests.test_runner -v
"""

import contextlib
import io
import json
import pathlib
import tempfile
import threading
import time
import unittest

from failbench import runner
from failbench.providers.base import Provider, ProviderError, ProviderResponse
from tests import support

# ---------------------------------------------------------------------------
# Contract constants (kept local so the test does not depend on runner internals)
# ---------------------------------------------------------------------------

STATUSES = ("pass", "fail", "error")
SEVERITIES = ("critical", "high", "medium", "low")
PROMPT_ROLES = ("system", "user", "assistant")

RESULTS_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "provider",
        "model",
        "base_url",
        "suite_version",
        "started_at",
        "finished_at",
        "environment",
        "config",
        "counts",
        "by_class",
        "probes",
    }
)
PROBE_KEYS = frozenset(
    {
        "probe_id",
        "class",
        "title",
        "severity",
        "status",
        "reason",
        "latency_ms",
        "tokens",
        "response_sha256",
        "response_excerpt",
        "attempts",
    }
)
ATTEMPT_KEYS = frozenset({"index", "status", "reason", "response_sha256", "latency_ms"})
COUNT_KEYS = frozenset({"probes", "pass", "fail", "error"})
BY_CLASS_KEYS = frozenset({"total", "pass", "fail", "error", "pass_rate"})
RAW_KEYS = frozenset(
    {"probe_id", "attempt", "request", "response", "error", "latency_ms", "timestamp"}
)
RESPONSE_KEYS = frozenset({"text", "prompt_tokens", "completion_tokens"})
TOKEN_KEYS = frozenset({"prompt", "completion"})
CONFIG_KEYS = frozenset({"temperature", "max_tokens", "concurrency", "repeats"})
ENVIRONMENT_KEYS = frozenset({"python", "platform"})

_HEX = frozenset("0123456789abcdef")
_DIGITS = frozenset("0123456789")
#: Authoritative failure-class order from ``failbench.schema.CLASSES`` (exposed
#: through ``tests.support`` so this test imports only the allowed modules).
CLASS_ORDER = {name: index for index, name in enumerate(support.CLASSES)}
DEFAULT_MESSAGES = [{"role": "user", "content": "Reply with the single word OK."}]


# ---------------------------------------------------------------------------
# Small stdlib-only shape helpers
# ---------------------------------------------------------------------------

def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha256_hex(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in _HEX for char in value)
    )


def _is_utc_timestamp(value):
    """True for an ISO-8601 UTC timestamp ending in Z (fraction optional)."""
    if not isinstance(value, str) or len(value) < 20 or not value.endswith("Z"):
        return False
    core = value[:-1]
    if "." in core:
        core, _, fraction = core.partition(".")
        if not fraction or any(char not in _DIGITS for char in fraction):
            return False
    if len(core) != 19:
        return False
    separators = {4: "-", 7: "-", 10: "T", 13: ":", 16: ":"}
    for index, expected in separators.items():
        if core[index] != expected:
            return False
    digits = "".join(
        char for index, char in enumerate(core) if index not in separators
    )
    return len(digits) == 14 and all(char in _DIGITS for char in digits)


def _assert_run_id(testcase, run_id, provider_name):
    """Assert ``run_id`` matches ``^\\d{8}T\\d{6}Z-<provider name>$``."""
    testcase.assertIsInstance(run_id, str)
    suffix = "-" + provider_name
    testcase.assertTrue(
        run_id.endswith(suffix),
        "run_id {0!r} must end with {1!r}".format(run_id, suffix),
    )
    stamp = run_id[: -len(suffix)]
    testcase.assertEqual(len(stamp), 16, "run_id timestamp must be YYYYMMDDTHHMMSS")
    testcase.assertEqual(stamp[8], "T", "run_id date/time separator")
    testcase.assertEqual(stamp[15], "Z", "run_id must use UTC (trailing Z)")
    digits = stamp[:8] + stamp[9:15]
    testcase.assertTrue(
        all(char in _DIGITS for char in digits),
        "run_id date/time must be digits: {0!r}".format(run_id),
    )


# ---------------------------------------------------------------------------
# Scripted in-process providers
# ---------------------------------------------------------------------------

class ScriptedProvider(Provider):
    """Deterministic provider driven by a probe-id -> response-text mapping.

    ``texts`` values may be ``str`` (reused for every repeat) and may also be
    keyed by ``(probe_id, attempt)`` tuples for per-repeat behaviour.
    ``fail_ids`` raise a retryable :class:`ProviderError`; ``crash_ids`` raise a
    plain ``ValueError`` (an unexpected provider bug that must be isolated).
    """

    name = "scripted"
    default_model = "scripted-1"

    def __init__(self, texts=None, *, fail_ids=(), crash_ids=(), model=None, **options):
        Provider.__init__(self, model=model, **options)
        self.texts = dict(texts or {})
        self.fail_ids = set(fail_ids)
        self.crash_ids = set(crash_ids)
        self.calls = []
        self._lock = threading.Lock()

    def text_for(self, probe_id, attempt):
        per_attempt = self.texts.get((probe_id, attempt))
        if per_attempt is not None:
            return per_attempt
        return self.texts.get(probe_id, "OK")

    def complete(self, probe, attempt=0):
        probe_id = str(probe.get("id"))
        with self._lock:
            self.calls.append((probe_id, int(attempt)))
        if probe_id in self.crash_ids:
            raise ValueError(
                "simulated unexpected crash for probe {0}".format(probe_id)
            )
        if probe_id in self.fail_ids:
            raise ProviderError(
                "simulated provider outage for probe {0}".format(probe_id),
                retryable=True,
            )
        return ProviderResponse(
            text=self.text_for(probe_id, int(attempt)),
            prompt_tokens=3,
            completion_tokens=2,
            latency_ms=1,
            # Never persisted into artifacts; used by the no-secrets test.
            raw={"api_key": self.get_option("api_key"), "probe_id": probe_id},
        )


class CountingProvider(ScriptedProvider):
    """Scripted provider that records the maximum number of overlapping calls."""

    def __init__(self, *args, delay=0.02, **options):
        ScriptedProvider.__init__(self, *args, **options)
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self._count_lock = threading.Lock()

    def complete(self, probe, attempt=0):
        with self._count_lock:
            self.active += 1
            if self.active > self.max_active:
                self.max_active = self.active
        try:
            # Hold the "call" open so concurrent workers demonstrably overlap.
            time.sleep(self.delay)
            return ScriptedProvider.complete(self, probe, attempt=attempt)
        finally:
            with self._count_lock:
                self.active -= 1


# ---------------------------------------------------------------------------
# Shared assertions / helpers
# ---------------------------------------------------------------------------

class RunnerContractTest(unittest.TestCase):
    # -- fixture plumbing ---------------------------------------------------
    def write_probes(self, tmp_root, name, probes):
        return support.write_probes(
            pathlib.Path(tmp_root) / ("probes_" + name), probes
        )

    def new_out_dir(self, tmp_root, name):
        out_dir = pathlib.Path(tmp_root) / name
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def run_with(self, out_dir, probes_dir, provider, **options):
        options.setdefault("progress", False)
        options.setdefault("concurrency", 2)
        return runner.run_from_paths(
            out_dir=out_dir,
            provider=provider,
            probes_dir=probes_dir,
            **options
        )

    def make_run(self, tmp_root, probes, provider, name="out", **options):
        probes_dir = self.write_probes(tmp_root, name, probes)
        out_dir = self.new_out_dir(tmp_root, name)
        results = self.run_with(out_dir, probes_dir, provider, **options)
        return results, out_dir, probes_dir

    def read_artifacts(self, out_dir):
        out = pathlib.Path(out_dir)
        results_path = out / "results.json"
        raw_path = out / "raw.jsonl"
        self.assertTrue(results_path.is_file(), "missing results.json")
        self.assertTrue(raw_path.is_file(), "missing raw.jsonl")
        doc = json.loads(results_path.read_text(encoding="utf-8"))
        lines = [
            json.loads(line)
            for line in raw_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return doc, lines

    def assert_no_temp_leftovers(self, out_dir):
        leftovers = [
            str(path)
            for path in pathlib.Path(out_dir).rglob("*")
            if ".tmp" in path.name.lower()
        ]
        self.assertEqual(leftovers, [], "atomic writes left temp files behind")

    # -- results.json contract ---------------------------------------------
    def assert_results_contract(self, doc, provider_name="scripted", model_name="scripted-1"):
        self.assertIsInstance(doc, dict)
        self.assertEqual(set(doc.keys()), RESULTS_KEYS)

        self.assertIs(type(doc["schema"]), int)
        self.assertEqual(doc["schema"], 1)
        _assert_run_id(self, doc["run_id"], provider_name)
        self.assertEqual(doc["provider"], provider_name)
        self.assertEqual(doc["model"], model_name)
        self.assertTrue(
            doc["base_url"] is None or isinstance(doc["base_url"], str),
            "base_url must be a string or null",
        )
        self.assertEqual(doc["suite_version"], "0.1.0")

        for field in ("started_at", "finished_at"):
            self.assertTrue(
                _is_utc_timestamp(doc[field]),
                "{0} must be a UTC ISO timestamp ending in Z, got {1!r}".format(
                    field, doc[field]
                ),
            )
        self.assertLessEqual(
            doc["started_at"], doc["finished_at"], "started_at must be <= finished_at"
        )

        environment = doc["environment"]
        self.assertIsInstance(environment, dict)
        self.assertEqual(set(environment.keys()), ENVIRONMENT_KEYS)
        self.assertTrue(
            isinstance(environment["python"], str) and environment["python"].strip()
        )
        self.assertTrue(
            isinstance(environment["platform"], str) and environment["platform"].strip()
        )

        config = doc["config"]
        self.assertIsInstance(config, dict)
        self.assertEqual(set(config.keys()), CONFIG_KEYS)
        self.assertIsInstance(config["temperature"], (int, float))
        self.assertFalse(isinstance(config["temperature"], bool))
        self.assertTrue(0 <= config["temperature"] <= 2)
        self.assertTrue(_is_int(config["max_tokens"]) and config["max_tokens"] >= 1)
        self.assertTrue(_is_int(config["concurrency"]) and config["concurrency"] >= 1)
        self.assertTrue(_is_int(config["repeats"]) and config["repeats"] >= 1)

        self.assertIsInstance(doc["probes"], list)
        self.assert_counts_and_by_class(doc)
        self.assert_probe_contract(doc["probes"])
        self.assert_probe_order(doc)

    def assert_counts_and_by_class(self, doc):
        probes = doc["probes"]
        counts = doc["counts"]
        self.assertIsInstance(counts, dict)
        self.assertEqual(set(counts.keys()), COUNT_KEYS)
        for key in COUNT_KEYS:
            self.assertTrue(_is_int(counts[key]), "counts.{0} must be int".format(key))
            self.assertGreaterEqual(counts[key], 0)
        self.assertEqual(counts["probes"], len(probes))
        self.assertEqual(
            counts["pass"] + counts["fail"] + counts["error"], counts["probes"]
        )

        tallies = {"pass": 0, "fail": 0, "error": 0}
        expected = {}
        for entry in probes:
            self.assertIn(entry["status"], STATUSES)
            tallies[entry["status"]] += 1
            bucket = expected.setdefault(
                entry["class"], {"total": 0, "pass": 0, "fail": 0, "error": 0}
            )
            bucket["total"] += 1
            bucket[entry["status"]] += 1
        self.assertEqual(
            {key: counts[key] for key in ("pass", "fail", "error")}, tallies
        )

        by_class = doc["by_class"]
        self.assertIsInstance(by_class, dict)
        self.assertEqual(set(by_class.keys()), set(expected.keys()))
        for cls, expected_bucket in expected.items():
            bucket = by_class[cls]
            self.assertIsInstance(bucket, dict)
            self.assertEqual(set(bucket.keys()), BY_CLASS_KEYS)
            for key in ("total", "pass", "fail", "error"):
                self.assertTrue(
                    _is_int(bucket[key]), "by_class.{0}.{1} must be int".format(cls, key)
                )
                self.assertEqual(bucket[key], expected_bucket[key])
            self.assertEqual(
                bucket["total"], bucket["pass"] + bucket["fail"] + bucket["error"]
            )
            self.assertIsInstance(bucket["pass_rate"], float)
            self.assertGreaterEqual(bucket["pass_rate"], 0.0)
            self.assertLessEqual(bucket["pass_rate"], 1.0)
            self.assertEqual(
                bucket["pass_rate"],
                round(bucket["pass"] / bucket["total"], 4)
                if bucket["total"]
                else 0.0,
            )

    def assert_probe_contract(self, probes):
        seen = set()
        for entry in probes:
            self.check_probe_entry(entry)
            self.assertNotIn(
                entry["probe_id"], seen, "duplicate probe_id in results.probes"
            )
            seen.add(entry["probe_id"])

    def check_probe_entry(self, entry, expected_repeats=None):
        self.assertIsInstance(entry, dict)
        self.assertEqual(set(entry.keys()), PROBE_KEYS)
        self.assertIsInstance(entry["probe_id"], str)
        self.assertTrue(entry["probe_id"])
        self.assertIn(entry["class"], support.CLASSES)
        self.assertIsInstance(entry["title"], str)
        self.assertTrue(entry["title"])
        self.assertIn(entry["severity"], SEVERITIES)
        self.assertIn(entry["status"], STATUSES)
        self.assertIsInstance(entry["reason"], str)
        self.assertTrue(entry["reason"].strip(), "reason must be non-empty")
        self.assertTrue(_is_int(entry["latency_ms"]))
        self.assertGreaterEqual(entry["latency_ms"], 0)

        tokens = entry["tokens"]
        self.assertIsInstance(tokens, dict)
        self.assertEqual(set(tokens.keys()), TOKEN_KEYS)
        for key in TOKEN_KEYS:
            self.assertTrue(_is_int(tokens[key]), "tokens.{0} must be int".format(key))
            self.assertGreaterEqual(tokens[key], 0)

        self.assertTrue(
            _is_sha256_hex(entry["response_sha256"]),
            "response_sha256 must be 64 lowercase hex chars",
        )
        excerpt = entry["response_excerpt"]
        self.assertIsInstance(excerpt, str)
        self.assertLessEqual(len(excerpt), 500)

        attempts = entry["attempts"]
        self.assertIsInstance(attempts, list)
        self.assertTrue(attempts, "attempts must be non-empty")
        if expected_repeats is not None:
            self.assertEqual(len(attempts), expected_repeats)
        for index, attempt in enumerate(attempts):
            self.assertIsInstance(attempt, dict)
            self.assertEqual(set(attempt.keys()), ATTEMPT_KEYS)
            self.assertEqual(attempt["index"], index)
            self.assertIn(attempt["status"], STATUSES)
            self.assertIsInstance(attempt["reason"], str)
            self.assertTrue(attempt["reason"].strip(), "attempt reason must be non-empty")
            self.assertTrue(_is_sha256_hex(attempt["response_sha256"]))
            self.assertTrue(_is_int(attempt["latency_ms"]))
            self.assertGreaterEqual(attempt["latency_ms"], 0)

        attempt_statuses = [attempt["status"] for attempt in attempts]
        if entry["status"] == "pass":
            self.assertTrue(
                all(status == "pass" for status in attempt_statuses),
                "a passing probe may not contain failing/erroring attempts: "
                "{0!r}".format(attempt_statuses),
            )
        elif entry["status"] == "fail":
            self.assertIn(
                "fail", attempt_statuses, "failing probe needs a failing attempt"
            )
            self.assertNotIn(
                "error", attempt_statuses, "any error attempt must make status error"
            )
        else:  # error
            self.assertIn(
                "error", attempt_statuses, "error probe needs an erroring attempt"
            )

    def assert_probe_order(self, doc):
        probes = doc["probes"]
        class_by_id = {entry["probe_id"]: entry["class"] for entry in probes}
        ids = [entry["probe_id"] for entry in probes]
        expected = sorted(
            ids,
            key=lambda probe_id: (CLASS_ORDER[class_by_id[probe_id]], probe_id),
        )
        self.assertEqual(ids, expected, "probes must be sorted by (class order, probe_id)")

    # -- raw.jsonl contract -------------------------------------------------
    def assert_raw_contract(self, doc, lines, expected_model=None):
        total_attempts = sum(len(entry["attempts"]) for entry in doc["probes"])
        self.assertEqual(len(lines), total_attempts, "raw.jsonl must hold one line per attempt")
        probe_ids = {entry["probe_id"] for entry in doc["probes"]}
        attempts_by_probe = {}
        self.assertIsInstance(lines, list)
        for line in lines:
            self.assertIsInstance(line, dict)
            self.assertEqual(set(line.keys()), RAW_KEYS)
            self.assertIn(line["probe_id"], probe_ids)
            self.assertTrue(_is_int(line["attempt"]))
            self.assertGreaterEqual(line["attempt"], 0)
            attempts_by_probe.setdefault(line["probe_id"], []).append(line["attempt"])

            request = line["request"]
            self.assertIsInstance(request, dict)
            for key in ("model", "messages", "params"):
                self.assertIn(key, request, "raw request is missing {0!r}".format(key))
            self.assertIsInstance(request["model"], str)
            if expected_model is not None:
                self.assertEqual(request["model"], expected_model)
            self.assertIsInstance(request["messages"], list)
            self.assertTrue(request["messages"])
            for message in request["messages"]:
                self.assertIsInstance(message, dict)
                self.assertIn(message.get("role"), PROMPT_ROLES)
                self.assertIsInstance(message.get("content"), str)
            self.assertIsInstance(request["params"], dict)
            self.assertIn("temperature", request["params"])
            self.assertIn("max_tokens", request["params"])
            request_text = json.dumps(request).lower()
            self.assertNotIn("api_key", request_text)
            self.assertNotIn("sk-", request_text)

            if line["error"] is None:
                response = line["response"]
                self.assertIsInstance(response, dict)
                self.assertEqual(set(response.keys()), RESPONSE_KEYS)
                self.assertIsInstance(response["text"], str)
                self.assertTrue(_is_int(response["prompt_tokens"]))
                self.assertGreaterEqual(response["prompt_tokens"], 0)
                self.assertTrue(_is_int(response["completion_tokens"]))
                self.assertGreaterEqual(response["completion_tokens"], 0)
            else:
                self.assertIsNone(
                    line["response"], "errored attempt must have response null"
                )
                self.assertIsInstance(line["error"], str)
                self.assertTrue(line["error"].strip())

            self.assertTrue(_is_int(line["latency_ms"]))
            self.assertGreaterEqual(line["latency_ms"], 0)
            self.assertIsInstance(line["timestamp"], str)
            self.assertTrue(line["timestamp"].strip())

        for entry in doc["probes"]:
            self.assertEqual(
                sorted(attempts_by_probe.get(entry["probe_id"], [])),
                list(range(len(entry["attempts"]))),
                "raw attempts for {0!r} must be 0..repeats-1".format(entry["probe_id"]),
            )

    # ------------------------------------------------------------------
    # Case 1: end-to-end schema contract
    # ------------------------------------------------------------------
    def test_end_to_end_results_and_raw_contract(self):
        probes = [
            support.make_probe(
                "hal_exact_01",
                "hallucination",
                scoring={"type": "exact_match", "value": "OK"},
            ),
            support.make_probe(
                "if_contains_01",
                "instruction_following",
                scoring={"type": "contains_all", "value": ["alpha", "beta"]},
            ),
            support.make_probe(
                "ctx_regex_01",
                "context_retrieval",
                repeats=2,
                scoring={"type": "regex", "pattern": r"AURORA-\d{4}"},
            ),
            support.make_probe(
                "rea_numeric_01",
                "reasoning_consistency",
                scoring={"type": "numeric", "value": 391},
            ),
            support.make_probe(
                "str_json_01",
                "structured_output",
                scoring={
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                        "required": ["name", "count"],
                        "additionalProperties": False,
                    },
                },
            ),
            support.make_probe(
                "ml_notcontains_01",
                "multilingual",
                scoring={"type": "not_contains_any", "value": ["sorry", "error"]},
            ),
            support.make_probe(
                "syc_exact_02",
                "sycophancy",
                scoring={"type": "exact_match", "value": "disagree"},
            ),
            support.make_probe(
                "det_repeat_02",
                "determinism_calibration",
                repeats=2,
                scoring={"type": "contains_all", "value": ["42"]},
            ),
        ]
        provider = ScriptedProvider(
            {
                "hal_exact_01": "OK",
                "if_contains_01": "alpha and beta are present",
                "ctx_regex_01": "The access code is AURORA-7734.",
                "rea_numeric_01": "The answer is 391.",
                "str_json_01": '{"name": "gadget", "count": 2}',
                "ml_notcontains_01": "bonjour le monde",
                "syc_exact_02": "I agree with you completely.",
                "det_repeat_02": "token 42 detected",
            }
        )
        expected_status = {
            "hal_exact_01": "pass",
            "if_contains_01": "pass",
            "ctx_regex_01": "pass",
            "rea_numeric_01": "pass",
            "str_json_01": "pass",
            "ml_notcontains_01": "pass",
            "syc_exact_02": "fail",
            "det_repeat_02": "pass",
        }
        expected_order = [
            "hal_exact_01",
            "if_contains_01",
            "ctx_regex_01",
            "rea_numeric_01",
            "syc_exact_02",
            "str_json_01",
            "ml_notcontains_01",
            "det_repeat_02",
        ]

        with tempfile.TemporaryDirectory() as tmp:
            results, out_dir, _probes_dir = self.make_run(
                tmp, probes, provider, name="e2e", concurrency=2
            )
            doc, lines = self.read_artifacts(out_dir)

            # returned dict is exactly what was persisted
            self.assertEqual(doc, results)
            self.assert_results_contract(doc)
            self.assertEqual(doc["counts"], {"probes": 8, "pass": 7, "fail": 1, "error": 0})
            self.assertEqual(doc["config"]["concurrency"], 2)
            self.assertIsNone(doc["base_url"])
            self.assertLessEqual(doc["started_at"], doc["finished_at"])

            entries = {}
            for probe in probes:
                entry = next(
                    item for item in doc["probes"] if item["probe_id"] == probe["id"]
                )
                entries[probe["id"]] = entry
                self.check_probe_entry(entry, expected_repeats=probe["repeats"])
                self.assertEqual(entry["class"], probe["class"])
                self.assertEqual(entry["title"], probe["title"])
                self.assertEqual(entry["severity"], probe["severity"])
                self.assertEqual(entry["status"], expected_status[probe["id"]])
            self.assertEqual([p["probe_id"] for p in doc["probes"]], expected_order)

            # raw.jsonl: one line per attempt, no temp leftovers
            self.assertEqual(len(lines), 10)
            self.assert_raw_contract(doc, lines, expected_model="scripted-1")
            for line in lines:
                self.assertEqual(line["request"]["messages"], DEFAULT_MESSAGES)
            self.assert_no_temp_leftovers(out_dir)

    # ------------------------------------------------------------------
    # Case 2: bounded concurrency
    # ------------------------------------------------------------------
    def test_concurrency_is_bounded(self):
        probes = support.make_all_class_probes()[:8]
        provider = CountingProvider()
        with tempfile.TemporaryDirectory() as tmp:
            results, out_dir, _probes_dir = self.make_run(
                tmp, probes, provider, name="concurrency", concurrency=4
            )
            doc, lines = self.read_artifacts(out_dir)
            self.assertEqual(doc["config"]["concurrency"], 4)
            self.assertGreaterEqual(
                provider.max_active,
                2,
                "expected overlapping provider calls (max_active={0})".format(
                    provider.max_active
                ),
            )
            self.assertLessEqual(
                provider.max_active,
                4,
                "runner exceeded the requested concurrency: max_active={0}".format(
                    provider.max_active
                ),
            )
            self.assertEqual(len(provider.calls), 8)
            self.assertEqual(
                doc["counts"], {"probes": 8, "pass": 8, "fail": 0, "error": 0}
            )
            self.assertEqual({p["status"] for p in doc["probes"]}, {"pass"})
            self.assert_results_contract(doc)
            self.assert_raw_contract(doc, lines, expected_model="scripted-1")

    # ------------------------------------------------------------------
    # Case 3: per-probe error isolation
    # ------------------------------------------------------------------
    def test_error_isolation_per_probe(self):
        probes = [
            support.make_probe(
                "hal_iso_pass_01",
                "hallucination",
                scoring={"type": "exact_match", "value": "OK"},
            ),
            support.make_probe(
                "if_iso_pass_01",
                "instruction_following",
                scoring={"type": "exact_match", "value": "OK"},
            ),
            support.make_probe(
                "ctx_iso_pass_01",
                "context_retrieval",
                scoring={"type": "exact_match", "value": "OK"},
            ),
            support.make_probe(
                "rea_iso_err_01",
                "reasoning_consistency",
                scoring={"type": "exact_match", "value": "OK"},
            ),
            support.make_probe(
                "syc_iso_crash_01",
                "sycophancy",
                scoring={"type": "exact_match", "value": "OK"},
            ),
        ]
        provider = ScriptedProvider(
            fail_ids=["rea_iso_err_01"], crash_ids=["syc_iso_crash_01"]
        )
        with tempfile.TemporaryDirectory() as tmp:
            # Must not raise: a provider exception is isolated to its probe.
            results, out_dir, _probes_dir = self.make_run(
                tmp, probes, provider, name="isolation"
            )
            doc, lines = self.read_artifacts(out_dir)
            self.assertEqual(doc, results)
            self.assertEqual(doc["counts"], {"probes": 5, "pass": 3, "fail": 0, "error": 2})
            self.assert_results_contract(doc)

            entries = {entry["probe_id"]: entry for entry in doc["probes"]}
            for probe_id, expected in (
                ("hal_iso_pass_01", "pass"),
                ("if_iso_pass_01", "pass"),
                ("ctx_iso_pass_01", "pass"),
                ("rea_iso_err_01", "error"),
                ("syc_iso_crash_01", "error"),
            ):
                self.assertEqual(entries[probe_id]["status"], expected)

            # the recorded reason must mention the concrete provider failure
            self.assertIn("outage", entries["rea_iso_err_01"]["reason"].lower())
            self.assertIn("crash", entries["syc_iso_crash_01"]["reason"].lower())
            for probe_id in ("rea_iso_err_01", "syc_iso_crash_01"):
                attempts = entries[probe_id]["attempts"]
                self.assertEqual(len(attempts), 1)
                self.assertEqual(attempts[0]["status"], "error")

            # raw.jsonl records the errors explicitly; responses stay null
            self.assert_raw_contract(doc, lines, expected_model="scripted-1")
            self.assertEqual(len(lines), 5)
            error_lines = [line for line in lines if line["error"] is not None]
            self.assertEqual(len(error_lines), 2)
            self.assertEqual(
                {line["probe_id"] for line in error_lines},
                {"rea_iso_err_01", "syc_iso_crash_01"},
            )

    # ------------------------------------------------------------------
    # Case 4: repeats and repeats_override
    # ------------------------------------------------------------------
    def test_repeats_and_repeats_override(self):
        probes = [
            support.make_probe(
                "rea_repeat_01",
                "reasoning_consistency",
                repeats=2,
                scoring={"type": "exact_match", "value": "OK"},
            ),
            support.make_probe(
                "ml_single_01",
                "multilingual",
                repeats=1,
                scoring={"type": "exact_match", "value": "OK"},
            ),
        ]
        provider = ScriptedProvider(
            {
                "ml_single_01": "OK",
                ("ml_single_01", 1): "NO",
                ("rea_repeat_01", 0): "OK",
                ("rea_repeat_01", 1): "NO",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            probes_dir = self.write_probes(tmp, "repeats", probes)

            # A) no override: repeats come from each probe; ALL repeats must pass
            doc_a = self.run_with(self.new_out_dir(tmp, "rep_a"), probes_dir, provider)
            entries_a = {entry["probe_id"]: entry for entry in doc_a["probes"]}
            rea_a = entries_a["rea_repeat_01"]
            self.assertEqual(rea_a["status"], "fail")
            self.assertEqual(len(rea_a["attempts"]), 2)
            self.assertEqual(
                [attempt["status"] for attempt in rea_a["attempts"]], ["pass", "fail"]
            )
            ml_a = entries_a["ml_single_01"]
            self.assertEqual(ml_a["status"], "pass")
            self.assertEqual(len(ml_a["attempts"]), 1)
            self.assertEqual(doc_a["counts"], {"probes": 2, "pass": 1, "fail": 1, "error": 0})
            raw_a = self.read_artifacts(self.new_out_dir(tmp, "rep_a"))[1]
            self.assertEqual(len(raw_a), 3)

            # B) override=1: every probe runs exactly one attempt
            doc_b = self.run_with(
                self.new_out_dir(tmp, "rep_b"), probes_dir, provider, repeats_override=1
            )
            entries_b = {entry["probe_id"]: entry for entry in doc_b["probes"]}
            self.assertEqual(entries_b["rea_repeat_01"]["status"], "pass")
            self.assertEqual(len(entries_b["rea_repeat_01"]["attempts"]), 1)
            self.assertEqual(entries_b["ml_single_01"]["status"], "pass")
            self.assertEqual(len(entries_b["ml_single_01"]["attempts"]), 1)
            self.assertEqual(doc_b["config"]["repeats"], 1)
            self.assertEqual(doc_b["counts"], {"probes": 2, "pass": 2, "fail": 0, "error": 0})

            # C) override=2 also extends a repeats=1 probe to two attempts
            doc_c = self.run_with(
                self.new_out_dir(tmp, "rep_c"), probes_dir, provider, repeats_override=2
            )
            entries_c = {entry["probe_id"]: entry for entry in doc_c["probes"]}
            ml_c = entries_c["ml_single_01"]
            self.assertEqual(len(ml_c["attempts"]), 2)
            self.assertEqual(ml_c["status"], "fail")
            self.assertEqual(
                [attempt["status"] for attempt in ml_c["attempts"]], ["pass", "fail"]
            )
            rea_c = entries_c["rea_repeat_01"]
            self.assertEqual(len(rea_c["attempts"]), 2)
            self.assertEqual(rea_c["status"], "fail")
            self.assertEqual(doc_c["counts"], {"probes": 2, "pass": 0, "fail": 2, "error": 0})

    # ------------------------------------------------------------------
    # Case 5: mixed statuses and by_class pass rates
    # ------------------------------------------------------------------
    def test_status_mixing_and_pass_rate(self):
        probes = [
            support.make_probe(
                "hal_mix_01", "hallucination", scoring={"type": "exact_match", "value": "OK"}
            ),
            support.make_probe(
                "hal_mix_02", "hallucination", scoring={"type": "exact_match", "value": "OK"}
            ),
            support.make_probe(
                "hal_mix_03", "hallucination", scoring={"type": "exact_match", "value": "OK"}
            ),
            support.make_probe(
                "ctx_mix_01", "context_retrieval", scoring={"type": "exact_match", "value": "OK"}
            ),
            support.make_probe(
                "ctx_mix_02", "context_retrieval", scoring={"type": "exact_match", "value": "OK"}
            ),
        ]
        provider = ScriptedProvider(
            {
                "hal_mix_01": "OK",
                "hal_mix_02": "definitely not",
                "hal_mix_03": "OK",
                "ctx_mix_01": "OK",
                "ctx_mix_02": "wrong answer",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            results, out_dir, _probes_dir = self.make_run(
                tmp, probes, provider, name="mixing"
            )
            doc, _lines = self.read_artifacts(out_dir)
            self.assertEqual(doc, results)
            self.assertEqual(doc["counts"], {"probes": 5, "pass": 3, "fail": 2, "error": 0})
            statuses = {entry["probe_id"]: entry["status"] for entry in doc["probes"]}
            self.assertEqual(
                statuses,
                {
                    "hal_mix_01": "pass",
                    "hal_mix_02": "fail",
                    "hal_mix_03": "pass",
                    "ctx_mix_01": "pass",
                    "ctx_mix_02": "fail",
                },
            )
            self.assertEqual(
                doc["by_class"]["hallucination"],
                {
                    "total": 3,
                    "pass": 2,
                    "fail": 1,
                    "error": 0,
                    "pass_rate": round(2 / 3, 4),
                },
            )
            self.assertEqual(
                doc["by_class"]["context_retrieval"],
                {
                    "total": 2,
                    "pass": 1,
                    "fail": 1,
                    "error": 0,
                    "pass_rate": 0.5,
                },
            )
            self.assert_results_contract(doc)

    # ------------------------------------------------------------------
    # Case 6: class filter, limit and RunError cases
    # ------------------------------------------------------------------
    def test_class_filter_limit_and_run_errors(self):
        probes = support.make_all_class_probes()
        provider = ScriptedProvider()
        with tempfile.TemporaryDirectory() as tmp:
            probes_dir = self.write_probes(tmp, "filters", probes)

            filtered = self.run_with(
                self.new_out_dir(tmp, "filtered"),
                probes_dir,
                provider,
                class_filter="hallucination",
            )
            self.assertEqual(len(filtered["probes"]), 1)
            self.assertEqual(filtered["probes"][0]["probe_id"], "hal_fixture_01")
            self.assertEqual({entry["class"] for entry in filtered["probes"]}, {"hallucination"})
            self.assertEqual(filtered["counts"]["probes"], 1)
            self.assert_results_contract(filtered)

            limited = self.run_with(
                self.new_out_dir(tmp, "limited"), probes_dir, provider, limit=3
            )
            self.assertEqual(len(limited["probes"]), 3)
            self.assertEqual(limited["counts"]["probes"], 3)
            self.assert_results_contract(limited)

            unknown_dir = self.new_out_dir(tmp, "unknown_filter")
            with self.assertRaises(runner.RunError) as caught:
                self.run_with(
                    unknown_dir, probes_dir, provider, class_filter="not_a_real_class"
                )
            self.assertIn("class", str(caught.exception).lower())

            empty_probes = pathlib.Path(tmp) / "empty_probes"
            empty_probes.mkdir()
            empty_out = self.new_out_dir(tmp, "empty")
            with self.assertRaises(runner.RunError):
                self.run_with(empty_out, empty_probes, provider)

    def test_unwritable_output_raises_run_error(self):
        probes = [
            support.make_probe(
                "hal_out_01", "hallucination", scoring={"type": "exact_match", "value": "OK"}
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            probes_dir = self.write_probes(tmp, "unwritable", probes)
            blocked = pathlib.Path(tmp) / "not_a_directory"
            blocked.write_text("this path is a regular file\n", encoding="utf-8")
            with self.assertRaises(runner.RunError):
                runner.run_from_paths(
                    out_dir=blocked,
                    provider=ScriptedProvider(),
                    probes_dir=probes_dir,
                    progress=False,
                )

    # ------------------------------------------------------------------
    # Case 7: determinism + recorded metadata
    # ------------------------------------------------------------------
    def test_determinism_and_metadata(self):
        probes = support.make_all_class_probes()[:5]
        provider = ScriptedProvider()
        with tempfile.TemporaryDirectory() as tmp:
            probes_dir = self.write_probes(tmp, "determinism", probes)
            doc_a = self.run_with(
                self.new_out_dir(tmp, "det_a"), probes_dir, provider, concurrency=2
            )
            doc_b = self.run_with(
                self.new_out_dir(tmp, "det_b"), probes_dir, provider, concurrency=2
            )

            def fingerprint(doc):
                return {
                    entry["probe_id"]: (entry["status"], entry["response_sha256"])
                    for entry in doc["probes"]
                }

            self.assertEqual(fingerprint(doc_a), fingerprint(doc_b))
            for doc in (doc_a, doc_b):
                self.assert_results_contract(doc)
                _assert_run_id(self, doc["run_id"], "scripted")
                self.assertEqual(doc["run_id"].split("-", 1)[1], "scripted")
                self.assertEqual(doc["suite_version"], "0.1.0")
                self.assertEqual(doc["provider"], "scripted")
                self.assertEqual(doc["model"], "scripted-1")
                self.assertTrue(_is_utc_timestamp(doc["started_at"]))
                self.assertTrue(_is_utc_timestamp(doc["finished_at"]))
                self.assertTrue(doc["environment"]["python"])
                self.assertTrue(doc["environment"]["platform"])
            self.assertEqual(
                doc_a["counts"], {"probes": 5, "pass": 5, "fail": 0, "error": 0}
            )

    # ------------------------------------------------------------------
    # Case 8: no secret material in artifacts
    # ------------------------------------------------------------------
    def test_no_secret_material_in_artifacts(self):
        probes = support.make_all_class_probes()[:3]
        dummy_key = "sk-" + "DUMMYKEY0123456789abcdef"
        provider = ScriptedProvider(api_key=dummy_key)
        provider.api_key = dummy_key  # also attach as an attribute
        with tempfile.TemporaryDirectory() as tmp:
            results, out_dir, _probes_dir = self.make_run(
                tmp, probes, provider, name="secrets"
            )
            results_text = (pathlib.Path(out_dir) / "results.json").read_text(
                encoding="utf-8"
            )
            raw_text = (pathlib.Path(out_dir) / "raw.jsonl").read_text(encoding="utf-8")
            for text in (
                results_text,
                raw_text,
                json.dumps(results, ensure_ascii=False),
            ):
                lowered = text.lower()
                self.assertNotIn("sk-", lowered)
                self.assertNotIn("api_key", lowered)
                self.assertNotIn("dummykey", lowered)
            self.assert_results_contract(results)

    # ------------------------------------------------------------------
    # Case 9: progress output
    # ------------------------------------------------------------------
    def test_progress_output(self):
        probes = support.make_all_class_probes()[:5]
        provider = ScriptedProvider()
        with tempfile.TemporaryDirectory() as tmp:
            probes_dir = self.write_probes(tmp, "progress", probes)

            loud_buffer = io.StringIO()
            with contextlib.redirect_stdout(loud_buffer):
                loud_doc = self.run_with(
                    self.new_out_dir(tmp, "loud"),
                    probes_dir,
                    provider,
                    concurrency=2,
                    progress=True,
                )
            loud_output = loud_buffer.getvalue()
            self.assertTrue(
                loud_output.strip(),
                "progress=True must print a progress/summary to stdout",
            )
            lowered = loud_output.lower()
            summary_tokens = (
                "results.json",
                "probes",
                "pass",
                "fail",
                "summar",
                "wrote",
                "writ",
            )
            self.assertTrue(
                any(token in lowered for token in summary_tokens),
                "progress output lacks a summary token: {0!r}".format(loud_output[:300]),
            )
            self.assertEqual(loud_doc["counts"]["probes"], 5)

            quiet_buffer = io.StringIO()
            with contextlib.redirect_stdout(quiet_buffer):
                quiet_doc = self.run_with(
                    self.new_out_dir(tmp, "quiet"), probes_dir, provider, progress=False
                )
            quiet_output = quiet_buffer.getvalue()
            self.assertEqual(quiet_doc["counts"]["probes"], 5)
            # progress=False is "quiet-ish": it may still be non-empty, but it
            # must not be noisier than the progress=True run.
            self.assertLessEqual(len(quiet_output), len(loud_output))


if __name__ == "__main__":
    unittest.main()
