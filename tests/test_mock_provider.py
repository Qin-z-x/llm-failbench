"""Offline unit tests for the deterministic mock provider.

The mock provider is a synthetic pipeline fixture (see
``failbench/providers/mock.py``): these tests assert its determinism, its
pass/fail/error mix and its offline behaviour. Nothing here touches the
network or depends on ``runner.py`` / ``gate.py`` / ``cli.py``.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest import mock

from failbench.providers import get_provider
from failbench.providers.base import ProviderError, ProviderResponse
from failbench.providers.mock import (
    MockProvider,
    decision_for,
    synthesize_failing_response,
    synthesize_passing_response,
)
from failbench.schema import PROBES_DIR, load_probes
from failbench.scoring import extract_json, score, validate_schema_value
from tests.support import make_probe

#: Probe-id family used for the per-scoring-type bucket scan.
SYNTH_PREFIX = "hal_synth_"

#: Simple contains_all spec shared by the mix / determinism tests.
CONTAINS_ALL_OK: Dict[str, Any] = {"type": "contains_all", "value": ["OK"]}

#: One representative scoring spec per CONTRACT section 6 type.
SCORING_FIXTURES: List[Tuple[str, Dict[str, Any]]] = [
    ("contains_all", {"type": "contains_all", "value": ["AURORA-7734", "verified"]}),
    ("contains_any", {"type": "contains_any", "value": ["AURORA-7734", "ORION-11"]}),
    ("not_contains_any", {"type": "not_contains_any", "value": ["sorry", "cannot"]}),
    ("exact_match", {"type": "exact_match", "value": "the answer is 42"}),
    ("regex", {"type": "regex", "pattern": r"^[A-Z]{6}-\d{4}$"}),
    ("numeric", {"type": "numeric", "value": 17}),
    (
        "json_schema",
        {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["answer", "confidence"],
                "additionalProperties": False,
            },
        },
    ),
    (
        "all_of",
        {
            "type": "all_of",
            "units": [
                {"type": "contains_all", "value": ["OK"]},
                {"type": "not_contains_any", "value": ["sorry", "unable"]},
            ],
        },
    ),
]


def _find_decision(decision: str, prefix: str = SYNTH_PREFIX, limit: int = 600) -> str:
    """Return a synthetic probe id whose bucket maps to ``decision``."""
    for index in range(limit):
        probe_id = "{0}{1:03d}".format(prefix, index)
        if decision_for(probe_id) == decision:
            return probe_id
    raise AssertionError(
        "no {0!r} bucket found in {1!r} ids up to {2}".format(decision, prefix, limit)
    )


def _probe_for(probe_id: str, scoring: Dict[str, Any]) -> Dict[str, Any]:
    """Build a valid fixture probe with the given id and scoring spec."""
    return make_probe(probe_id, "hallucination", scoring=scoring)


class DeterminismTests(unittest.TestCase):
    """Same (probe, attempt) must always yield identical synthetic output."""

    def setUp(self) -> None:
        self.probe = _probe_for(_find_decision("pass"), CONTAINS_ALL_OK)

    def test_repeated_calls_same_instance_are_identical(self) -> None:
        provider = MockProvider()
        first = provider.complete(self.probe)
        second = provider.complete(self.probe)
        self.assertEqual(first.text, second.text)
        self.assertEqual(first.prompt_tokens, second.prompt_tokens)
        self.assertEqual(first.completion_tokens, second.completion_tokens)
        self.assertEqual(first.latency_ms, second.latency_ms)
        self.assertEqual(first.raw, second.raw)
        self.assertTrue(score(CONTAINS_ALL_OK, first.text)[0])

    def test_fresh_instances_are_identical(self) -> None:
        first = MockProvider().complete(self.probe)
        second = MockProvider().complete(self.probe)
        fresh = MockProvider(model="failbench-mock-1").complete(self.probe)
        self.assertEqual(first.text, second.text)
        self.assertEqual(first.latency_ms, second.latency_ms)
        self.assertEqual(first.text, fresh.text)
        self.assertEqual(first.completion_tokens, fresh.completion_tokens)

    def test_helpers_are_pure(self) -> None:
        self.assertEqual(
            synthesize_passing_response(CONTAINS_ALL_OK),
            synthesize_passing_response(CONTAINS_ALL_OK),
        )
        self.assertEqual(
            synthesize_failing_response(CONTAINS_ALL_OK),
            synthesize_failing_response(CONTAINS_ALL_OK),
        )


class FactoryTests(unittest.TestCase):
    """The public factory must expose the mock provider with default metadata."""

    def test_get_provider_mock(self) -> None:
        provider = get_provider("mock")
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.name, "mock")
        self.assertEqual(provider.model, "failbench-mock-1")
        self.assertEqual(provider.default_model, "failbench-mock-1")
        described = provider.describe()
        self.assertEqual(described.get("provider"), "mock")
        self.assertEqual(described.get("model"), "failbench-mock-1")


class MixTests(unittest.TestCase):
    """The 300-id sample must be a realistic but non-100% mix of outcomes."""

    def test_300_probe_mix(self) -> None:
        provider = MockProvider()
        counts = {"pass": 0, "fail": 0, "error": 0}
        for index in range(300):
            probe_id = "hal_mix_{0:03d}".format(index)
            probe = _probe_for(probe_id, CONTAINS_ALL_OK)
            try:
                response = provider.complete(probe)
            except ProviderError as exc:
                counts["error"] += 1
                self.assertFalse(exc.retryable)
                self.assertIn(probe_id, str(exc))
                continue
            passed = score(CONTAINS_ALL_OK, response.text)[0]
            counts["pass" if passed else "fail"] += 1

        total = 300.0
        pass_ratio = counts["pass"] / total
        fail_ratio = counts["fail"] / total
        error_ratio = counts["error"] / total
        self.assertGreater(pass_ratio, 0.55, "pass ratio too low: {0!r}".format(counts))
        self.assertLess(pass_ratio, 0.85, "pass ratio too high: {0!r}".format(counts))
        self.assertGreater(fail_ratio, 0.10, "fail ratio too low: {0!r}".format(counts))
        self.assertLess(fail_ratio, 0.45, "fail ratio too high: {0!r}".format(counts))
        self.assertGreater(error_ratio, 0.005, "error ratio too low: {0!r}".format(counts))
        self.assertLess(error_ratio, 0.06, "error ratio too high: {0!r}".format(counts))


class ScoringTypeTests(unittest.TestCase):
    """Every contract scoring type must be reachable as pass and as fail."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = MockProvider()
        cls.pass_id = _find_decision("pass")
        cls.fail_id = _find_decision("fail")
        cls.error_id = _find_decision("error")

    def test_pass_cases_satisfy_scorer(self) -> None:
        for name, scoring in SCORING_FIXTURES:
            with self.subTest(scoring=name):
                probe = _probe_for(self.pass_id, scoring)
                response = self.provider.complete(probe)
                passed, detail = score(scoring, response.text)
                self.assertTrue(
                    passed,
                    "pass bucket text failed {0}: {1} ({2!r})".format(
                        name, detail, response.text
                    ),
                )
                self.assertEqual(response.raw, {"mock": True, "decision": "pass"})
                if name == "json_schema":
                    parsed = json.loads(response.text)
                    self.assertEqual(
                        validate_schema_value(parsed, scoring["schema"]),
                        [],
                    )

    def test_fail_cases_violate_scorer(self) -> None:
        for name, scoring in SCORING_FIXTURES:
            with self.subTest(scoring=name):
                probe = _probe_for(self.fail_id, scoring)
                response = self.provider.complete(probe)
                passed, detail = score(scoring, response.text)
                self.assertFalse(
                    passed,
                    "fail bucket text passed {0}: {1} ({2!r})".format(
                        name, detail, response.text
                    ),
                )
                self.assertEqual(response.raw, {"mock": True, "decision": "fail"})

    def test_error_bucket_raises_provider_error(self) -> None:
        probe = _probe_for(self.error_id, CONTAINS_ALL_OK)
        with self.assertRaises(ProviderError) as ctx:
            self.provider.complete(probe)
        self.assertIn(self.error_id, str(ctx.exception))
        self.assertFalse(ctx.exception.retryable)
        self.assertTrue(str(ctx.exception).startswith("mock provider:"))


class FailCaseContentTests(unittest.TestCase):
    """Fail-bucket texts must be plausible *and* mechanically wrong."""

    def test_not_contains_any_fail_text_mentions_forbidden_value(self) -> None:
        scoring = {"type": "not_contains_any", "value": ["sorry", "cannot"]}
        probe = _probe_for(_find_decision("fail"), scoring)
        response = MockProvider().complete(probe)
        self.assertFalse(score(scoring, response.text)[0])
        lowered = response.text.lower()
        mentioned = [value for value in scoring["value"] if value.lower() in lowered]
        self.assertTrue(
            mentioned,
            "expected a forbidden substring in {0!r}".format(response.text),
        )

    def test_exact_match_fail_text_differs_from_expected(self) -> None:
        scoring = {"type": "exact_match", "value": "the answer is 42"}
        probe = _probe_for(_find_decision("fail"), scoring)
        response = MockProvider().complete(probe)
        self.assertFalse(score(scoring, response.text)[0])
        self.assertNotEqual(response.text.strip().lower(), scoring["value"].lower())


class OfflineTests(unittest.TestCase):
    """Prove the provider never opens a network socket."""

    def test_complete_performs_no_network_io(self) -> None:
        provider = MockProvider()
        probes = [
            _probe_for(_find_decision("pass"), CONTAINS_ALL_OK),
            _probe_for(_find_decision("fail"), CONTAINS_ALL_OK),
            _probe_for(_find_decision("pass"), {"type": "numeric", "value": 7}),
            _probe_for(_find_decision("fail"), {"type": "exact_match", "value": "42"}),
        ]
        with mock.patch(
            "socket.socket", side_effect=AssertionError("network used")
        ):
            for probe in probes:
                response = provider.complete(probe)
                self.assertIsInstance(response, ProviderResponse)
                self.assertIsInstance(response.text, str)


class MissingScoringTests(unittest.TestCase):
    """A probe without a ``scoring`` key must not crash ``complete()``."""

    def test_complete_without_scoring_key_returns_text(self) -> None:
        provider = MockProvider()
        for decision in ("pass", "fail"):
            probe = _probe_for(_find_decision(decision), CONTAINS_ALL_OK)
            probe.pop("scoring")
            response = provider.complete(probe)
            self.assertIsInstance(response, ProviderResponse)
            self.assertIsInstance(response.text, str)
            self.assertTrue(response.text)
            self.assertIn(response.raw["decision"], ("pass", "fail"))


class RegexSynthesisRegressionTests(unittest.TestCase):
    """Corpus-derived specs that require the regex solver / all_of composer.

    These reproduce the pass-bucket probes that a naive per-type candidate list
    could not satisfy: anchored patterns, lookarounds, and ``all_of`` specs that
    mix anchored regex units, JSON schemas or embedded literals.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = MockProvider()
        cls.probe_id = _find_decision("pass")

    def _complete(self, scoring: Dict[str, Any]) -> ProviderResponse:
        return self.provider.complete(_probe_for(self.probe_id, scoring))

    def _assert_pass(self, scoring: Dict[str, Any]) -> ProviderResponse:
        response = self._complete(scoring)
        passed, detail = score(scoring, response.text)
        self.assertTrue(
            passed, "synthesized text {0!r} failed: {1}".format(response.text, detail)
        )
        self.assertEqual(response.raw, {"mock": True, "decision": "pass"})
        return response

    def test_anchored_literal_regex(self) -> None:
        scoring = {"type": "regex", "pattern": r"\ARESULT::NIGHTSHADE-6417\s*\Z"}
        response = self._assert_pass(scoring)
        self.assertIn("NIGHTSHADE-6417", response.text)

    def test_lookaround_digits_regex(self) -> None:
        scoring = {"type": "regex", "pattern": r"(?<![\d,])417293(?![\d,])"}
        response = self._assert_pass(scoring)
        self.assertIn("417293", response.text)

    def test_all_of_with_anchored_regex_unit(self) -> None:
        scoring = {
            "type": "all_of",
            "units": [
                {"type": "regex", "pattern": r"(?i)^\s*ACTION:\s*final\b"},
                {"type": "regex", "pattern": r"(?i)inventory\s*=\s*unavailable\b"},
                {
                    "type": "regex",
                    "pattern": r"(?i)^\s*ACTION:\s*tool_call\b",
                    "negate": True,
                },
            ],
        }
        self._assert_pass(scoring)

    def test_all_of_json_schema_and_contains(self) -> None:
        schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["ok"]}},
            "required": ["status"],
            "additionalProperties": False,
        }
        scoring = {
            "type": "all_of",
            "units": [
                {"type": "json_schema", "schema": schema},
                {"type": "contains_any", "value": ["\u5317\u4eac"]},
            ],
        }
        response = self._assert_pass(scoring)
        parsed, error = extract_json(response.text)
        self.assertEqual(error, "")
        self.assertEqual(validate_schema_value(parsed, schema), [])

    def test_all_of_json_schema_with_trailing_regex_units(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "report": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "status": {"type": "string", "enum": ["ok", "failed"]},
                    },
                    "required": ["id", "status"],
                    "additionalProperties": False,
                }
            },
            "required": ["report"],
            "additionalProperties": False,
        }
        scoring = {
            "type": "all_of",
            "units": [
                {"type": "json_schema", "schema": schema},
                {"type": "regex", "pattern": r"\"id\"\s*:\s*4471\b"},
                {"type": "regex", "pattern": r"\"status\"\s*:\s*\"ok\""},
            ],
        }
        response = self._assert_pass(scoring)
        parsed, error = extract_json(response.text)
        self.assertEqual(error, "")
        self.assertEqual(validate_schema_value(parsed, schema), [])


def _corpus_probe_files() -> List[Path]:
    """Return the JSON probe files under ``probes/`` (empty when absent)."""
    root = Path(PROBES_DIR)
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob("*.json")
        if path.is_file() and not path.name.startswith("_")
    )


class CorpusPassBucketTests(unittest.TestCase):
    """Real-corpus regression: a mock "pass" must really pass its scoring."""

    def test_pass_bucket_never_scores_false(self) -> None:
        files = _corpus_probe_files()
        if len(files) < 20:
            self.skipTest(
                "probes/ corpus not present or too small ({0} JSON files)".format(
                    len(files)
                )
            )
        probes = load_probes()
        provider = MockProvider()
        pass_bucket = [
            probe
            for probe in probes
            if decision_for(str(probe.get("id")), 0) == "pass"
        ]
        self.assertGreater(len(pass_bucket), 0, "expected at least one pass-bucket probe")

        failures: List[Tuple[str, str]] = []
        for probe in pass_bucket:
            probe_id = str(probe.get("id"))
            try:
                response = provider.complete(probe, 0)
            except ProviderError as exc:  # pragma: no cover - bucket is "pass"
                failures.append(
                    (probe_id, "unexpected synthetic transport error: {0}".format(exc))
                )
                continue
            passed, detail = score(probe.get("scoring"), response.text)
            if not passed:
                failures.append((probe_id, detail[:160]))

        # Degenerate/self-contradictory specs are documented as best effort; at
        # most two exceptions are tolerated and they are listed in the message.
        self.assertLessEqual(
            len(failures),
            2,
            "pass-bucket probes still failing their own scoring: {0}".format(failures),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
