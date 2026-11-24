"""Offline unit tests for ``failbench.providers.replay`` (stdlib only).

Every fixture lives in a temporary directory; no network, no API keys and no
runner imports are needed. Run from the repository root::

    python -m unittest tests.test_replay -v
"""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import failbench
from failbench.providers import get_provider
from failbench.providers.base import Provider, ProviderConfigError, ProviderError
from failbench.providers.replay import (
    ReplayError,
    ReplayProvider,
    compare_statuses,
    group_attempts,
    load_raw_records,
    replay_recorded,
    resolve_raw_path,
    write_replay_results,
)
from tests.support import make_probe, make_results_doc, write_json

SECRET = "sk-" + "fixture-secret-0000"


# ---------------------------------------------------------------------------
# Fixture builders (all synthetic, written only under a TemporaryDirectory)
# ---------------------------------------------------------------------------

def _record(
    probe_id: str,
    attempt: int,
    text: Any,
    latency_ms: int,
    *,
    error: Any = None,
    prompt_tokens: int = 12,
    completion_tokens: int = 3,
) -> Dict[str, Any]:
    """Build one CONTRACT-section-7 raw.jsonl record."""
    record: Dict[str, Any] = {
        "probe_id": probe_id,
        "attempt": attempt,
        "request": {
            "model": "fixture-model-1",
            "messages": [{"role": "user", "content": "Reply with the single word OK."}],
            "params": {"temperature": 0, "max_tokens": 64},
            # Deliberate credentials lookalike: replay must never copy requests.
            "headers": {"Authorization": "Bearer " + SECRET},
        },
        "response": None,
        "error": error,
        "latency_ms": latency_ms,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    if text is not None:
        record["response"] = {
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
    return record


def _write_raw(path: Path, records: List[Dict[str, Any]], blank_lines: bool = False) -> Path:
    """Write records as JSONL (optionally with blank lines between records)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for record in records:
        lines.append(json.dumps(record, ensure_ascii=False))
        if blank_lines:
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReplayFixtureCase(unittest.TestCase):
    """Shared fixture: a run dir with raw.jsonl plus a matching results.json.

    Probes: hallucination (repeats=2, both recorded "OK" -> pass), reasoning
    consistency (recorded "NO" -> fail), context retrieval (recorded error ->
    error) and a sycophancy probe with no recorded attempts at all.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.run_dir = self.tmp / "run1"
        self.raw_path = self.run_dir / "raw.jsonl"

        exact_ok = {"type": "exact_match", "value": "OK"}
        self.hal_probe = make_probe(
            "hal_fixture_01", "hallucination", repeats=2, scoring=exact_ok
        )
        self.rea_probe = make_probe(
            "rea_fixture_01", "reasoning_consistency", repeats=1, scoring=exact_ok
        )
        self.ctx_probe = make_probe(
            "ctx_fixture_01", "context_retrieval", repeats=1, scoring=exact_ok
        )
        self.unrecorded_probe = make_probe(
            "syc_fixture_01",
            "sycophancy",
            repeats=1,
            scoring={"type": "contains_all", "value": ["YES"]},
        )
        self.probes = [
            self.hal_probe,
            self.rea_probe,
            self.ctx_probe,
            self.unrecorded_probe,
        ]

        # Deliberately shuffled file order: replay must sort by class then attempt.
        self.records = [
            _record("rea_fixture_01", 0, "NO", 30, prompt_tokens=5, completion_tokens=2),
            _record("hal_fixture_01", 1, "OK", 20),
            _record(
                "ctx_fixture_01",
                0,
                None,
                40,
                error="connection reset by peer",
                prompt_tokens=0,
                completion_tokens=0,
            ),
            _record("hal_fixture_01", 0, "OK", 10),
        ]
        _write_raw(self.raw_path, self.records, blank_lines=True)

        self.original = make_results_doc(
            [
                {"probe_id": "hal_fixture_01", "class": "hallucination", "status": "pass"},
                {
                    "probe_id": "rea_fixture_01",
                    "class": "reasoning_consistency",
                    "status": "fail",
                },
                {
                    "probe_id": "ctx_fixture_01",
                    "class": "context_retrieval",
                    "status": "error",
                },
            ],
            run_id="20260101T000000Z-fixture",
            provider="mock",
            model="fixture-model-1",
        )
        write_json(self.run_dir / "results.json", self.original)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _ids(payload: Dict[str, Any]) -> List[str]:
        return [entry["probe_id"] for entry in payload["probes"]]

    @staticmethod
    def _by_id(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {entry["probe_id"]: entry for entry in payload["probes"]}


# ---------------------------------------------------------------------------
# Raw-path resolution, loading and grouping
# ---------------------------------------------------------------------------

class TestRawLoading(ReplayFixtureCase):
    def test_resolve_raw_path_directory_and_file(self) -> None:
        self.assertEqual(resolve_raw_path(self.run_dir), self.raw_path)
        self.assertEqual(resolve_raw_path(str(self.run_dir)), self.raw_path)
        self.assertEqual(resolve_raw_path(self.raw_path), self.raw_path)
        self.assertEqual(resolve_raw_path(str(self.raw_path)), self.raw_path)

    def test_missing_raw_jsonl_raises_replay_error(self) -> None:
        missing = self.tmp / "does-not-exist"
        with self.assertRaises(ReplayError) as ctx:
            resolve_raw_path(missing)
        message = str(ctx.exception)
        self.assertIn("no raw.jsonl found under", message)
        self.assertIn("does-not-exist", message)

        empty_dir = self.tmp / "empty-dir"
        empty_dir.mkdir()
        with self.assertRaises(ReplayError):
            resolve_raw_path(empty_dir)
        with self.assertRaises(ReplayError):
            load_raw_records(empty_dir)

    def test_load_raw_records_from_directory_and_file(self) -> None:
        from_dir = load_raw_records(self.run_dir)
        from_file = load_raw_records(str(self.raw_path))
        self.assertEqual(from_dir, from_file)
        self.assertEqual(len(from_dir), 4)
        self.assertEqual(
            [record["probe_id"] for record in from_dir],
            [
                "rea_fixture_01",
                "hal_fixture_01",
                "ctx_fixture_01",
                "hal_fixture_01",
            ],
        )
        self.assertIsNone(from_dir[0]["error"])
        self.assertEqual(from_dir[2]["error"], "connection reset by peer")
        self.assertIsNone(from_dir[2]["response"])

    def test_load_raw_records_rejects_malformed_json(self) -> None:
        bad_dir = self.tmp / "bad-json"
        bad_dir.mkdir()
        bad_raw = bad_dir / "raw.jsonl"
        bad_raw.write_text(
            '{"probe_id": "hal_fixture_01", "attempt": 0}\n'
            "{this is not json}\n",
            encoding="utf-8",
        )
        with self.assertRaises(ReplayError) as ctx:
            load_raw_records(bad_dir)
        message = str(ctx.exception)
        self.assertIn(str(bad_raw), message)
        self.assertIn(":2: invalid JSON", message)

    def test_load_raw_records_rejects_invalid_record_shapes(self) -> None:
        cases = [
            ("not-an-object", "[1, 2, 3]", "must be a JSON object"),
            (
                "bad-probe-id",
                json.dumps({"probe_id": 7, "attempt": 0}),
                "probe_id must be a non-empty string",
            ),
            (
                "bad-attempt",
                json.dumps({"probe_id": "hal_fixture_01", "attempt": "0"}),
                "attempt must be a non-negative integer",
            ),
            (
                "missing-attempt",
                json.dumps({"probe_id": "hal_fixture_01"}),
                "attempt must be a non-negative integer",
            ),
        ]
        for name, line, expected in cases:
            with self.subTest(case=name):
                directory = self.tmp / ("bad-" + name)
                directory.mkdir()
                (directory / "raw.jsonl").write_text(line + "\n", encoding="utf-8")
                with self.assertRaises(ReplayError) as ctx:
                    load_raw_records(directory)
                self.assertIn(expected, str(ctx.exception))

    def test_group_attempts_structure(self) -> None:
        grouped = group_attempts(self.records)
        self.assertEqual(
            sorted(grouped),
            ["ctx_fixture_01", "hal_fixture_01", "rea_fixture_01"],
        )
        self.assertEqual(sorted(grouped["hal_fixture_01"]), [0, 1])
        self.assertEqual(sorted(grouped["rea_fixture_01"]), [0])
        self.assertEqual(sorted(grouped["ctx_fixture_01"]), [0])
        self.assertIs(grouped["hal_fixture_01"][0], self.records[3])
        self.assertEqual(grouped["hal_fixture_01"][1]["latency_ms"], 20)


# ---------------------------------------------------------------------------
# ReplayProvider
# ---------------------------------------------------------------------------

class TestReplayProvider(ReplayFixtureCase):
    def test_reproduces_recorded_responses(self) -> None:
        provider = ReplayProvider(results=self.run_dir)
        self.assertIsInstance(provider, Provider)
        self.assertEqual(provider.name, "replay")
        self.assertEqual(provider.default_model, "replay-recorded")
        # Model comes from the sibling results.json when none was passed.
        self.assertEqual(provider.model, "fixture-model-1")
        self.assertEqual(provider.source, str(self.raw_path))

        first = provider.complete(self.hal_probe, attempt=0)
        self.assertEqual(first.text, "OK")
        self.assertEqual(first.prompt_tokens, 12)
        self.assertEqual(first.completion_tokens, 3)
        self.assertEqual(first.latency_ms, 10)
        self.assertEqual(
            first.raw, {"replayed": True, "source": str(self.raw_path)}
        )

        repeat = provider.complete(self.hal_probe, attempt=1)
        self.assertEqual(repeat.text, "OK")
        self.assertEqual(repeat.latency_ms, 20)

        rea = provider.complete(self.rea_probe)
        self.assertEqual(rea.text, "NO")
        self.assertEqual(rea.prompt_tokens, 5)

        self.assertEqual(
            provider.describe(),
            {
                "provider": "replay",
                "model": "fixture-model-1",
                "base_url": None,
                "results": str(self.raw_path),
            },
        )

    def test_raw_path_argument_and_model_fallbacks(self) -> None:
        explicit = ReplayProvider(raw_path=self.raw_path, model="explicit-model")
        self.assertEqual(explicit.source, str(self.raw_path))
        self.assertEqual(explicit.model, "explicit-model")
        self.assertEqual(explicit.complete(self.rea_probe).text, "NO")

        lonely_dir = self.tmp / "lonely-run"
        _write_raw(
            lonely_dir / "raw.jsonl",
            [_record("hal_fixture_01", 0, "OK", 5)],
        )
        lonely = ReplayProvider(results=lonely_dir)
        self.assertEqual(lonely.model, "replay-recorded")

    def test_requires_results_or_raw_path(self) -> None:
        with self.assertRaises(ProviderConfigError) as ctx:
            ReplayProvider()
        message = str(ctx.exception)
        self.assertIn("results=", message)
        self.assertIn("raw_path=", message)

        with self.assertRaises(ReplayError):
            ReplayProvider(results=self.tmp / "nope")

    def test_missing_attempt_and_recorded_error_raise_provider_error(self) -> None:
        provider = ReplayProvider(results=self.run_dir)

        with self.assertRaises(ProviderError) as ctx:
            provider.complete(self.unrecorded_probe)
        message = str(ctx.exception)
        self.assertIn("no recorded attempt 0", message)
        self.assertIn("syc_fixture_01", message)
        self.assertIn(provider.source, message)
        self.assertFalse(ctx.exception.retryable)

        with self.assertRaises(ProviderError) as ctx:
            provider.complete(self.hal_probe, attempt=9)
        self.assertIn("no recorded attempt 9", str(ctx.exception))
        self.assertFalse(ctx.exception.retryable)

        with self.assertRaises(ProviderError) as ctx:
            provider.complete(self.ctx_probe)
        message = str(ctx.exception)
        self.assertIn("recorded error", message)
        self.assertIn("ctx_fixture_01", message)
        self.assertIn("connection reset", message)
        self.assertFalse(ctx.exception.retryable)

    def test_record_without_response_or_error_raises_provider_error(self) -> None:
        weird_dir = self.tmp / "weird-run"
        _write_raw(
            weird_dir / "raw.jsonl",
            [_record("hal_fixture_01", 0, None, 5)],
        )
        provider = ReplayProvider(results=weird_dir)
        with self.assertRaises(ProviderError) as ctx:
            provider.complete(self.hal_probe)
        self.assertIn("no recorded response", str(ctx.exception))
        self.assertFalse(ctx.exception.retryable)

    def test_factory_returns_replay_provider(self) -> None:
        provider = get_provider("replay", results=str(self.run_dir))
        self.assertIsInstance(provider, ReplayProvider)
        self.assertEqual(provider.model, "fixture-model-1")
        alias = get_provider("recorded", results=self.run_dir)
        self.assertIsInstance(alias, ReplayProvider)

    def test_provider_does_not_copy_request_secrets(self) -> None:
        provider = ReplayProvider(results=self.run_dir)
        response = provider.complete(self.hal_probe)
        serialized = json.dumps(response.raw)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("Authorization", serialized)


# ---------------------------------------------------------------------------
# replay_recorded: statuses, counts, class stats, comparison
# ---------------------------------------------------------------------------

class TestReplayRecorded(ReplayFixtureCase):
    def _payload(self, **kwargs: Any) -> Dict[str, Any]:
        arguments: Dict[str, Any] = {
            "records": self.records,
            "probes": self.probes,
            "original_results": self.original,
        }
        arguments.update(kwargs)
        return replay_recorded(**arguments)

    def test_payload_document_structure(self) -> None:
        payload = self._payload()
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["run_id"], "replay-20260101T000000Z-fixture")
        self.assertEqual(payload["provider"], "replay")
        self.assertEqual(payload["model"], "fixture-model-1")
        self.assertIsNone(payload["base_url"])
        self.assertEqual(payload["suite_version"], failbench.__version__)
        self.assertEqual(payload["started_at"], "2026-01-01T00:00:00Z")
        self.assertTrue(payload["finished_at"].endswith("Z"))
        self.assertEqual(
            payload["environment"],
            {"python": platform.python_version(), "platform": platform.system()},
        )
        self.assertEqual(payload["config"], self.original["config"])

    def test_statuses_counts_and_deterministic_order(self) -> None:
        payload = self._payload()
        self.assertEqual(
            self._ids(payload),
            ["hal_fixture_01", "ctx_fixture_01", "rea_fixture_01"],
        )
        self.assertEqual(
            payload["counts"], {"probes": 3, "pass": 1, "fail": 1, "error": 1}
        )
        by_id = self._by_id(payload)
        self.assertEqual(by_id["hal_fixture_01"]["status"], "pass")
        self.assertEqual(by_id["rea_fixture_01"]["status"], "fail")
        self.assertEqual(by_id["ctx_fixture_01"]["status"], "error")

        # Repeats: both recorded attempts pass.
        hal = by_id["hal_fixture_01"]
        self.assertEqual([attempt["index"] for attempt in hal["attempts"]], [0, 1])
        self.assertEqual(
            [attempt["status"] for attempt in hal["attempts"]], ["pass", "pass"]
        )
        self.assertEqual(hal["latency_ms"], 30)
        self.assertEqual(hal["tokens"], {"prompt": 24, "completion": 6})
        self.assertEqual(hal["response_sha256"], _sha256("OK"))
        self.assertEqual(hal["response_excerpt"], "OK")

        ctx = by_id["ctx_fixture_01"]
        self.assertEqual(ctx["status"], "error")
        self.assertEqual(ctx["response_sha256"], _sha256(""))
        self.assertIn("connection reset", ctx["reason"])
        self.assertEqual(ctx["tokens"], {"prompt": 0, "completion": 0})
        self.assertEqual(ctx["latency_ms"], 40)

        rea = by_id["rea_fixture_01"]
        self.assertEqual(rea["attempts"][0]["status"], "fail")
        self.assertEqual(rea["reason"], rea["attempts"][0]["reason"])
        self.assertIn("expected", rea["reason"])

        for entry in payload["probes"]:
            for attempt in entry["attempts"]:
                self.assertEqual(len(attempt["response_sha256"]), 64)
                int(attempt["response_sha256"], 16)  # raises unless 64 hex digits

    def test_by_class_pass_rate(self) -> None:
        payload = self._payload()
        by_class = payload["by_class"]
        self.assertEqual(
            by_class["hallucination"],
            {"total": 1, "pass": 1, "fail": 0, "error": 0, "pass_rate": 1.0},
        )
        self.assertEqual(by_class["context_retrieval"]["pass_rate"], 0.0)
        self.assertEqual(by_class["reasoning_consistency"]["pass_rate"], 0.0)
        self.assertEqual(
            set(by_class),
            {"hallucination", "context_retrieval", "reasoning_consistency"},
        )
        # sycophancy probe exists in the corpus but has no recorded attempts.
        self.assertNotIn("sycophancy", by_class)

    def test_compared_to_matches_original(self) -> None:
        compared = self._payload()["compared_to"]
        self.assertEqual(compared["run_id"], "20260101T000000Z-fixture")
        self.assertEqual(compared["matched"], 3)
        self.assertEqual(compared["mismatched"], [])
        self.assertEqual(compared["missing_in_original"], [])
        self.assertEqual(compared["missing_in_replay"], [])

    def test_compared_to_detects_mismatch(self) -> None:
        original = copy.deepcopy(self.original)
        for entry in original["probes"]:
            if entry["probe_id"] == "rea_fixture_01":
                entry["status"] = "pass"
        compared = self._payload(original_results=original)["compared_to"]
        self.assertEqual(compared["matched"], 2)
        self.assertTrue(compared["mismatched"])
        self.assertIn("rea_fixture_01", [item["probe_id"] for item in compared["mismatched"]])
        mismatched = {
            item["probe_id"]: item for item in compared["mismatched"]
        }["rea_fixture_01"]
        self.assertEqual(mismatched["original_status"], "pass")
        self.assertEqual(mismatched["replayed_status"], "fail")

    def test_compared_to_detects_missing_probes(self) -> None:
        original_without_ctx = copy.deepcopy(self.original)
        original_without_ctx["probes"] = [
            entry
            for entry in original_without_ctx["probes"]
            if entry["probe_id"] != "ctx_fixture_01"
        ]
        compared = self._payload(original_results=original_without_ctx)["compared_to"]
        self.assertEqual(compared["missing_in_original"], ["ctx_fixture_01"])
        self.assertEqual(compared["missing_in_replay"], [])

        original_with_extra = copy.deepcopy(self.original)
        original_with_extra["probes"].append(
            {"probe_id": "syc_fixture_01", "status": "pass"}
        )
        compared = self._payload(original_results=original_with_extra)["compared_to"]
        self.assertEqual(compared["missing_in_replay"], ["syc_fixture_01"])
        self.assertEqual(compared["missing_in_original"], [])

    def test_compare_statuses_helper_tolerates_missing_keys(self) -> None:
        replayed = {
            "probes": [
                {"probe_id": "hal_x_01", "status": "pass"},
                {"probe_id": "rea_x_01", "status": "fail"},
            ]
        }
        original = {
            "run_id": "orig",
            "probes": [
                {"probe_id": "hal_x_01", "status": "fail"},
                {"probe_id": "ctx_x_01", "status": "error"},
            ],
        }
        compared = compare_statuses(replayed, original)
        self.assertEqual(compared["run_id"], "orig")
        self.assertEqual(compared["matched"], 0)
        self.assertEqual(
            compared["mismatched"],
            [
                {
                    "probe_id": "hal_x_01",
                    "original_status": "fail",
                    "replayed_status": "pass",
                }
            ],
        )
        self.assertEqual(compared["missing_in_original"], ["rea_x_01"])
        self.assertEqual(compared["missing_in_replay"], ["ctx_x_01"])

        empty = compare_statuses({}, {})
        self.assertEqual(
            empty,
            {
                "run_id": "",
                "matched": 0,
                "mismatched": [],
                "missing_in_original": [],
                "missing_in_replay": [],
            },
        )
        junk = compare_statuses({"probes": "junk"}, {"probes": [{"probe_id": 3}]})
        self.assertEqual(junk["matched"], 0)
        self.assertEqual(junk["mismatched"], [])

    def test_repeat_failure_makes_probe_fail(self) -> None:
        records = [
            _record("hal_fixture_01", 0, "OK", 5),
            _record("hal_fixture_01", 1, "NOPE", 7),
        ]
        payload = replay_recorded(records, [self.hal_probe])
        entry = payload["probes"][0]
        self.assertEqual(entry["status"], "fail")
        self.assertEqual(
            [attempt["status"] for attempt in entry["attempts"]], ["pass", "fail"]
        )
        self.assertEqual(entry["reason"], entry["attempts"][1]["reason"])
        self.assertEqual(payload["counts"], {"probes": 1, "pass": 0, "fail": 1, "error": 0})

    def test_unrecorded_probe_is_omitted(self) -> None:
        payload = self._payload()
        recorded_groups = group_attempts(self.records)
        self.assertEqual(payload["counts"]["probes"], len(recorded_groups))
        self.assertEqual(len(payload["probes"]), 3)
        self.assertNotIn("syc_fixture_01", self._ids(payload))

    def test_recorded_probe_missing_from_corpus_is_error(self) -> None:
        orphan = _record("agt_orphan_01", 0, "OK", 7)
        payload = replay_recorded(self.records + [orphan], self.probes)
        self.assertEqual(self._ids(payload)[-1], "agt_orphan_01")
        self.assertEqual(payload["counts"]["probes"], 4)
        self.assertEqual(payload["counts"]["error"], 2)
        entry = self._by_id(payload)["agt_orphan_01"]
        self.assertEqual(entry["class"], "unknown")
        self.assertEqual(entry["severity"], "unknown")
        self.assertEqual(entry["status"], "error")
        self.assertEqual(entry["title"], "(probe record missing)")
        self.assertEqual(
            entry["reason"], "probe record not found in current probes/ corpus"
        )
        self.assertEqual(entry["attempts"][0]["status"], "error")
        self.assertIn("unknown", payload["by_class"])

    def test_replay_recorded_is_deterministic_and_defaults(self) -> None:
        first = self._payload()
        second = self._payload(
            records=list(reversed(self.records)),
            probes=list(reversed(self.probes)),
        )
        self.assertEqual(self._ids(first), self._ids(second))
        self.assertEqual(first["counts"], second["counts"])
        self.assertEqual(
            [entry["attempts"] for entry in first["probes"]],
            [entry["attempts"] for entry in second["probes"]],
        )
        self.assertEqual(first["compared_to"], second["compared_to"])

        bare = replay_recorded(self.records, self.probes)
        self.assertEqual(bare["run_id"], "replay")
        self.assertEqual(bare["model"], "replay-recorded")
        self.assertIsNone(bare["compared_to"])
        self.assertEqual(bare["config"], {})
        self.assertTrue(bare["started_at"].endswith("Z"))

        empty = replay_recorded([], self.probes)
        self.assertEqual(empty["counts"]["probes"], 0)
        self.assertEqual(empty["probes"], [])
        self.assertEqual(empty["by_class"], {})

    def test_payload_never_copies_request_fields(self) -> None:
        payload = self._payload()
        serialized = json.dumps(payload)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn('"headers"', serialized)
        self.assertNotIn("Reply with the single word OK.", serialized)


# ---------------------------------------------------------------------------
# Atomic persistence
# ---------------------------------------------------------------------------

class TestWriteReplayResults(ReplayFixtureCase):
    def _payload(self) -> Dict[str, Any]:
        return replay_recorded(self.records, self.probes, original_results=self.original)

    def test_atomic_write_and_round_trip(self) -> None:
        payload = self._payload()
        out_dir = self.tmp / "out"
        target = write_replay_results(payload, out_dir)
        self.assertEqual(target, out_dir / "replay-results.json")
        self.assertTrue(target.is_file())

        text = target.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(
            text,
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )
        self.assertEqual(json.loads(text), payload)

        leftovers = [
            path.name for path in out_dir.iterdir() if path.name != "replay-results.json"
        ]
        self.assertEqual(leftovers, [])

    def test_creates_nested_directory_and_custom_filename(self) -> None:
        payload = self._payload()
        target = write_replay_results(
            payload, self.tmp / "nested" / "audit", filename="audit-replay.json"
        )
        self.assertEqual(
            target, self.tmp / "nested" / "audit" / "audit-replay.json"
        )
        self.assertTrue(target.is_file())
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), payload)


if __name__ == "__main__":  # pragma: no cover - manual helper
    unittest.main(verbosity=2)
