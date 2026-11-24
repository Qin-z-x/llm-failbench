"""Repository-level integration smoke test for the FailBench harness.

Runs the deterministic ``mock`` provider against the *real* probe corpus in
``probes/`` (offline, no API key), checks the CONTRACT section 7 artifact shape,
and verifies the demo run is deterministic after normalizing run ids,
timestamps and latency values.

Skipped when the corpus is not present yet (e.g. a fresh checkout that only
contains the harness), so the unit suite stays self-contained.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from failbench import __version__, runner
from failbench.providers import get_provider
from failbench.schema import CLASSES, PROBES_DIR, load_probes
from tests import support

#: Below this corpus size a deterministic pass/fail mix assertion is not fair.
MIN_CORPUS = 20


def _normalized(results):
    """Strip volatile metadata; keep the reproducible measurement."""
    return {
        probe["probe_id"]: (probe["status"], probe["response_sha256"])
        for probe in results["probes"]
    }


def _assert_contract_shape(testcase, results, raw_lines):
    testcase.assertEqual(results["schema"], 1)
    testcase.assertEqual(results["suite_version"], __version__)
    testcase.assertRegex(results["run_id"], r"^\d{8}T\d{6}Z-mock$")
    testcase.assertEqual(results["provider"], "mock")
    testcase.assertTrue(results["model"])
    for key in (
        "started_at",
        "finished_at",
        "environment",
        "config",
        "counts",
        "by_class",
        "probes",
    ):
        testcase.assertIn(key, results)
    counts = results["counts"]
    testcase.assertEqual(counts["probes"], len(results["probes"]))
    testcase.assertEqual(
        counts["probes"], counts["pass"] + counts["fail"] + counts["error"]
    )
    testcase.assertLessEqual(results["started_at"], results["finished_at"])
    testcase.assertIn("python", results["environment"])
    testcase.assertIn("platform", results["environment"])

    total_by_class = 0
    for class_name, bucket in results["by_class"].items():
        testcase.assertIn(class_name, CLASSES)
        testcase.assertEqual(
            bucket["total"], bucket["pass"] + bucket["fail"] + bucket["error"]
        )
        expected_rate = (
            round(bucket["pass"] / bucket["total"], 4) if bucket["total"] else 0.0
        )
        testcase.assertEqual(bucket["pass_rate"], expected_rate)
        total_by_class += bucket["total"]
    testcase.assertEqual(total_by_class, counts["probes"])

    statuses = {"pass", "fail", "error"}
    for probe in results["probes"]:
        for key in (
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
        ):
            testcase.assertIn(key, probe)
        testcase.assertIn(probe["status"], statuses)
        testcase.assertTrue(probe["reason"])
        testcase.assertLessEqual(len(probe["response_excerpt"]), 500)
        testcase.assertRegex(probe["response_sha256"], r"^[0-9a-f]{64}$")
        testcase.assertGreaterEqual(len(probe["attempts"]), 1)
        for attempt in probe["attempts"]:
            testcase.assertIn(attempt["status"], statuses)
            testcase.assertRegex(attempt["response_sha256"], r"^[0-9a-f]{64}$")

    testcase.assertEqual(
        len(raw_lines), sum(len(probe["attempts"]) for probe in results["probes"])
    )
    for line in raw_lines:
        testcase.assertEqual(
            set(line),
            {
                "probe_id",
                "attempt",
                "request",
                "response",
                "error",
                "latency_ms",
                "timestamp",
            },
        )
        testcase.assertNotIn("sk-", json.dumps(line))


class HarnessSmokeTests(unittest.TestCase):
    """End-to-end runner smoke test on the shipped corpus (offline)."""

    @classmethod
    def setUpClass(cls):
        if not PROBES_DIR.is_dir():
            raise unittest.SkipTest("probes/ corpus not present")
        cls.probes = load_probes()
        if len(cls.probes) < MIN_CORPUS:
            raise unittest.SkipTest(
                "probes/ corpus too small for a mix assertion ({0} < {1})".format(
                    len(cls.probes), MIN_CORPUS
                )
            )

    def test_mock_demo_contract_and_determinism(self):
        provider = get_provider("mock")
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = runner.run_from_paths(
                out_dir=first_dir, provider=provider, progress=False
            )
            raw_lines = support.read_jsonl(Path(first_dir) / "raw.jsonl")
            _assert_contract_shape(self, first, raw_lines)
            on_disk = json.loads(
                (Path(first_dir) / "results.json").read_text(encoding="utf-8")
            )
            self.assertEqual(on_disk, first)

            second = runner.run_from_paths(
                out_dir=second_dir, provider=provider, progress=False
            )
            self.assertEqual(_normalized(first), _normalized(second))

            # CONTRACT section 8: the mock demo must never be 100% pass.
            self.assertGreater(first["counts"]["fail"] + first["counts"]["error"], 0)

    def test_gate_self_comparison_passes_on_identical_runs(self):
        from failbench import gate

        provider = get_provider("mock")
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            runner.run_from_paths(out_dir=first_dir, provider=provider, progress=False)
            runner.run_from_paths(out_dir=second_dir, provider=provider, progress=False)
            comparison = gate.compare_files(
                Path(first_dir) / "results.json", Path(second_dir) / "results.json"
            )
            self.assertFalse(comparison["has_regressions"])
            self.assertEqual(comparison["summary"]["regressions"], 0)
            self.assertIn("GATE PASS", gate.format_report(comparison))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
