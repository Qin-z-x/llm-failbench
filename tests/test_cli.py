"""Offline CLI contract tests for ``python -m failbench`` (stdlib unittest).

Every case shells out through :func:`tests.support.run_cli`, which puts the
repository root on ``PYTHONPATH``, scrubs API-key environment variables and
runs without any network access. All probes/evidence/results fixtures are
written to fresh temporary directories and deleted automatically, so the tests
never mutate the shipped corpus or ``results/``.

Run from the repository root::

    python -m unittest tests.test_cli -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tests import support
from tests.support import (
    FIXTURE_IDS,
    make_all_class_evidence,
    make_all_class_probes,
    make_probe,
    make_results_doc,
    read_json,
    read_jsonl,
    run_cli,
    write_evidence,
    write_json,
    write_probes,
)

REPO_ROOT = support.ROOT


def combined(proc: Any) -> str:
    """stdout + stderr of a completed CLI subprocess."""
    return (proc.stdout or "") + (proc.stderr or "")


class CliTestCase(unittest.TestCase):
    """Base class: shared temporary fixture corpus + small helpers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tempdir = tempfile.TemporaryDirectory(prefix="failbench-cli-")
        cls.tmp = Path(cls._tempdir.name)

        # One schema-valid probe per failure class (10 probes) + matching
        # evidence records, all synthetic and entirely offline.
        cls.probes_dir = cls.tmp / "fixture-probes"
        write_probes(cls.probes_dir, make_all_class_probes())

        cls.evidence_dir = cls.tmp / "fixture-evidence"
        write_evidence(cls.evidence_dir, make_all_class_evidence())

        cls.empty_evidence_dir = cls.tmp / "empty-evidence"
        cls.empty_evidence_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tempdir.cleanup()

    # -- helpers ---------------------------------------------------------
    def run_cmd(
        self,
        args: Sequence[Any],
        cwd: Optional[Any] = None,
        env_extra: Optional[Dict[str, str]] = None,
    ) -> Any:
        return run_cli(
            args,
            cwd=cwd if cwd is not None else REPO_ROOT,
            env_extra=env_extra,
        )

    def unique_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_results_doc(self, name: str, entries: List[Dict[str, Any]]) -> Path:
        path = self.tmp / name / "results.json"
        write_json(path, make_results_doc(entries))
        return path

    def assert_no_traceback(self, proc: Any) -> None:
        self.assertNotIn("Traceback", combined(proc), msg=combined(proc))

    def run_mock(self, out_dir: Path, extra_args: Optional[Sequence[Any]] = None) -> Any:
        args: List[Any] = [
            "run",
            "--provider",
            "mock",
            "--out",
            out_dir,
            "--probes-dir",
            self.probes_dir,
            "--quiet",
        ]
        if extra_args:
            args.extend(extra_args)
        return self.run_cmd(args)

    # -- 1. help ---------------------------------------------------------
    def test_top_level_help_lists_commands(self) -> None:
        proc = self.run_cmd(["--help"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        text = combined(proc)
        for token in ("list", "run", "gate", "validate", "replay", "report"):
            self.assertIn(token, text)
        self.assert_no_traceback(proc)

    def test_version_flag(self) -> None:
        proc = self.run_cmd(["--version"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("0.1.1", proc.stdout)
        self.assertIn("failbench", proc.stdout)
        self.assert_no_traceback(proc)

    def test_run_help_documents_options(self) -> None:
        proc = self.run_cmd(["run", "--help"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        text = combined(proc)
        for token in ("--provider", "--concurrency", "--out", "--demo", "--api-key-env"):
            self.assertIn(token, text)

    def test_validate_help_documents_strict(self) -> None:
        proc = self.run_cmd(["validate", "--help"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("--strict", combined(proc))

    # -- 2. list ---------------------------------------------------------
    def test_list_table_class_filter_and_json(self) -> None:
        proc = self.run_cmd(["list", "--probes-dir", self.probes_dir])
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("hal_fixture_01", proc.stdout)
        self.assertIn("probe(s) in", proc.stdout)
        self.assertIn("CLASS", proc.stdout)
        self.assert_no_traceback(proc)

        proc = self.run_cmd(
            ["list", "--probes-dir", self.probes_dir, "--class", "hallucination"]
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("hal_fixture_01", proc.stdout)
        self.assertNotIn("rea_fixture_01", proc.stdout)

        proc = self.run_cmd(["list", "--probes-dir", self.probes_dir, "--json"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        payload = json.loads(proc.stdout)
        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), len(FIXTURE_IDS))
        self.assertEqual({item["id"] for item in payload}, set(FIXTURE_IDS.values()))

    def test_list_invalid_class_is_usage_error(self) -> None:
        proc = self.run_cmd(
            ["list", "--probes-dir", self.probes_dir, "--class", "not_a_class"]
        )
        self.assertEqual(proc.returncode, 2, combined(proc))
        self.assertIn("unknown class", proc.stderr)
        self.assert_no_traceback(proc)

    def test_list_empty_corpus_exits_zero(self) -> None:
        empty_dir = self.unique_dir("empty-probes")
        proc = self.run_cmd(["list", "--probes-dir", empty_dir])
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("no probes found", combined(proc))
        self.assert_no_traceback(proc)

    def test_output_tolerates_unencodable_titles_on_gbk_console(self) -> None:
        """Regression: non-Latin probe titles must not crash cp936/gbk stdout."""
        unicode_dir = self.unique_dir("unicode-probes")
        probe = make_probe(
            FIXTURE_IDS["multilingual"],
            "multilingual",
            title="Arabic-Indic digits in a title \u0667\u0668",
        )
        write_probes(unicode_dir, [probe])
        env_extra = {"PYTHONIOENCODING": "gbk"}

        proc = self.run_cmd(
            ["list", "--probes-dir", unicode_dir], env_extra=env_extra
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertNotIn("internal error", combined(proc))
        self.assert_no_traceback(proc)
        self.assertIn(FIXTURE_IDS["multilingual"], proc.stdout)

        proc = self.run_cmd(
            ["list", "--probes-dir", unicode_dir, "--json"], env_extra=env_extra
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertNotIn("internal error", combined(proc))
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload), 1)
        self.assertIn("\u0667", payload[0]["title"])

    # -- 3. validate -----------------------------------------------------
    def test_validate_valid_corpus(self) -> None:
        proc = self.run_cmd(
            [
                "validate",
                "--probes-dir",
                self.probes_dir,
                "--evidence-dir",
                self.evidence_dir,
            ]
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("OK:", proc.stdout)
        self.assert_no_traceback(proc)

    def test_validate_invalid_probe_fails(self) -> None:
        bad_dir = self.unique_dir("invalid-probes")
        bad_probe = make_probe("hal_invalid_01", "hallucination", title="Hi")
        write_probes(bad_dir, [bad_probe])
        proc = self.run_cmd(
            [
                "validate",
                "--probes-dir",
                bad_dir,
                "--evidence-dir",
                self.empty_evidence_dir,
            ]
        )
        self.assertEqual(proc.returncode, 1, combined(proc))
        self.assertIn("ERROR", combined(proc))
        self.assert_no_traceback(proc)

    def test_validate_incomplete_corpus_warns_and_strict_fails(self) -> None:
        partial_dir = self.unique_dir("partial-probes")
        write_probes(
            partial_dir, [make_probe(FIXTURE_IDS["hallucination"], "hallucination")]
        )
        base_args = [
            "validate",
            "--probes-dir",
            partial_dir,
            "--evidence-dir",
            self.empty_evidence_dir,
        ]
        proc = self.run_cmd(base_args)
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("WARN:", combined(proc))
        self.assertIn("OK:", proc.stdout)

        strict_proc = self.run_cmd(base_args + ["--strict"])
        self.assertEqual(strict_proc.returncode, 1, combined(strict_proc))
        self.assertIn("STRICT", combined(strict_proc))

    # -- 4. run (mock e2e + determinism) ---------------------------------
    def test_run_mock_end_to_end_and_deterministic(self) -> None:
        first_out = self.unique_dir("run-first")
        proc = self.run_mock(first_out, ["--concurrency", "2"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("results.json", proc.stdout)
        self.assert_no_traceback(proc)

        results_path = first_out / "results.json"
        self.assertTrue(results_path.is_file())
        results = read_json(results_path)
        self.assertEqual(results["schema"], 1)
        self.assertEqual(results["counts"]["probes"], len(FIXTURE_IDS))
        self.assertEqual(results["counts"]["probes"], len(results["probes"]))

        raw_path = first_out / "raw.jsonl"
        self.assertTrue(raw_path.is_file())
        raw_lines = read_jsonl(raw_path)
        self.assertGreaterEqual(len(raw_lines), results["counts"]["probes"])

        second_out = self.unique_dir("run-second")
        proc = self.run_mock(second_out, ["--concurrency", "2"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        second = read_json(second_out / "results.json")

        def normalized(document: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
            return {
                probe["probe_id"]: (probe["status"], probe["response_sha256"])
                for probe in document["probes"]
            }

        self.assertEqual(normalized(results), normalized(second))

    # -- 5. run options --------------------------------------------------
    def test_run_limit_and_class_filters(self) -> None:
        limit_out = self.unique_dir("run-limit")
        proc = self.run_mock(limit_out, ["--limit", "2"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        limited = read_json(limit_out / "results.json")
        self.assertEqual(limited["counts"]["probes"], 2)
        self.assertEqual(len(limited["probes"]), 2)

        class_out = self.unique_dir("run-class")
        proc = self.run_mock(class_out, ["--class", "hallucination"])
        self.assertEqual(proc.returncode, 0, combined(proc))
        filtered = read_json(class_out / "results.json")
        self.assertGreaterEqual(filtered["counts"]["probes"], 1)
        self.assertEqual(
            {probe["class"] for probe in filtered["probes"]}, {"hallucination"}
        )

    def test_run_unknown_provider_is_usage_error(self) -> None:
        out = self.unique_dir("run-unknown-provider")
        proc = self.run_cmd(
            [
                "run",
                "--provider",
                "bogus",
                "--out",
                out,
                "--probes-dir",
                self.probes_dir,
                "--quiet",
            ]
        )
        self.assertEqual(proc.returncode, 2, combined(proc))
        self.assertIn("unknown provider", proc.stderr)
        self.assert_no_traceback(proc)

    def test_run_bad_concurrency_is_usage_error(self) -> None:
        out = self.unique_dir("run-bad-concurrency")
        proc = self.run_mock(out, ["--concurrency", "0"])
        self.assertEqual(proc.returncode, 2, combined(proc))
        self.assertIn("--concurrency", proc.stderr)

    # -- 6. openai provider without an API key ---------------------------
    def test_run_openai_missing_key_is_usage_error(self) -> None:
        out = self.unique_dir("run-openai-missing-key")
        proc = self.run_cmd(
            [
                "run",
                "--provider",
                "openai",
                "--base-url",
                "http://127.0.0.1:9",
                "--api-key-env",
                "FAILBENCH_TEST_MISSING_KEY",
                "--out",
                out,
                "--probes-dir",
                self.probes_dir,
            ]
        )
        self.assertEqual(proc.returncode, 2, combined(proc))
        text = combined(proc)
        self.assertIn("FAILBENCH_TEST_MISSING_KEY", text)
        self.assert_no_traceback(proc)
        # The CLI only ever handles the env var *name*; no key material leaks.
        self.assertNotIn("sk-", text)

    # -- 7. gate ---------------------------------------------------------
    def test_gate_identical_results_pass(self) -> None:
        entries = [
            {
                "probe_id": FIXTURE_IDS["hallucination"],
                "class": "hallucination",
                "status": "pass",
            },
            {
                "probe_id": FIXTURE_IDS["context_retrieval"],
                "class": "context_retrieval",
                "status": "fail",
            },
        ]
        baseline = self.write_results_doc("gate-baseline-pass", entries)
        current = self.write_results_doc("gate-current-pass", entries)
        proc = self.run_cmd(["gate", "--baseline", baseline, "--current", current])
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("GATE PASS", proc.stdout)
        self.assert_no_traceback(proc)

    def test_gate_regression_fails_and_names_probe(self) -> None:
        regressed_id = FIXTURE_IDS["hallucination"]
        baseline_entries = [
            {"probe_id": regressed_id, "class": "hallucination", "status": "pass"},
            {
                "probe_id": FIXTURE_IDS["reasoning_consistency"],
                "class": "reasoning_consistency",
                "status": "pass",
            },
        ]
        current_entries = [
            {"probe_id": regressed_id, "class": "hallucination", "status": "fail"},
            {
                "probe_id": FIXTURE_IDS["reasoning_consistency"],
                "class": "reasoning_consistency",
                "status": "pass",
            },
        ]
        baseline = self.write_results_doc("gate-baseline-reg", baseline_entries)
        current = self.write_results_doc("gate-current-reg", current_entries)
        proc = self.run_cmd(["gate", "--baseline", baseline, "--current", current])
        self.assertEqual(proc.returncode, 1, combined(proc))
        text = combined(proc)
        self.assertIn("GATE FAIL", text)
        self.assertIn(regressed_id, text)
        self.assert_no_traceback(proc)

    def test_gate_missing_baseline_is_usage_error(self) -> None:
        missing = self.tmp / "gate-missing" / "results.json"
        current = self.write_results_doc(
            "gate-current-missing",
            [
                {
                    "probe_id": FIXTURE_IDS["hallucination"],
                    "class": "hallucination",
                    "status": "pass",
                }
            ],
        )
        proc = self.run_cmd(["gate", "--baseline", missing, "--current", current])
        self.assertEqual(proc.returncode, 2, combined(proc))
        stderr_lower = (proc.stderr or "").lower()
        self.assertTrue(
            "gate error" in stderr_lower or "not found" in stderr_lower,
            msg=combined(proc),
        )
        self.assert_no_traceback(proc)

    # -- 8. replay -------------------------------------------------------
    def test_replay_reproduces_recorded_statuses(self) -> None:
        run_out = self.unique_dir("replay-run")
        proc = self.run_mock(run_out)
        self.assertEqual(proc.returncode, 0, combined(proc))
        original = read_json(run_out / "results.json")

        replay_out = self.unique_dir("replay-out")
        proc = self.run_cmd(
            [
                "replay",
                "--results",
                run_out,
                "--probes-dir",
                self.probes_dir,
                "--out",
                replay_out,
            ]
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assertIn("Replayed", proc.stdout)
        self.assert_no_traceback(proc)

        replay_path = replay_out / "replay-results.json"
        self.assertTrue(replay_path.is_file())
        replayed_doc = read_json(replay_path)
        self.assertEqual(replayed_doc["counts"]["probes"], original["counts"]["probes"])
        for status_key in ("pass", "fail", "error"):
            self.assertEqual(
                replayed_doc["counts"][status_key], original["counts"][status_key]
            )
        replayed_statuses = {
            probe["probe_id"]: probe["status"]
            for probe in replayed_doc.get("probes", [])
        }
        original_statuses = {
            probe["probe_id"]: probe["status"] for probe in original["probes"]
        }
        self.assertEqual(replayed_statuses, original_statuses)

    def test_replay_missing_results_path_is_usage_error(self) -> None:
        missing = self.tmp / "replay-missing-run"
        proc = self.run_cmd(["replay", "--results", missing])
        self.assertEqual(proc.returncode, 2, combined(proc))
        self.assertIn("not found", proc.stderr)
        self.assert_no_traceback(proc)

    def test_run_replay_provider_reproduces_recorded_statuses(self) -> None:
        run_out = self.unique_dir("replay-provider-run")
        proc = self.run_mock(run_out)
        self.assertEqual(proc.returncode, 0, combined(proc))
        original = read_json(run_out / "results.json")

        rerun_out = self.unique_dir("replay-provider-rerun")
        proc = self.run_cmd(
            [
                "run",
                "--provider",
                "replay",
                "--results",
                run_out,
                "--out",
                rerun_out,
                "--probes-dir",
                self.probes_dir,
                "--quiet",
            ]
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assert_no_traceback(proc)
        replayed = read_json(rerun_out / "results.json")
        self.assertEqual(replayed["counts"]["probes"], original["counts"]["probes"])
        original_statuses = {
            probe["probe_id"]: probe["status"] for probe in original["probes"]
        }
        replayed_statuses = {
            probe["probe_id"]: probe["status"] for probe in replayed["probes"]
        }
        self.assertEqual(replayed_statuses, original_statuses)

    # -- 9. report degrades gracefully -----------------------------------
    def test_report_command_never_crashes(self) -> None:
        run_out = self.unique_dir("report-run")
        proc = self.run_mock(run_out)
        self.assertEqual(proc.returncode, 0, combined(proc))

        site_out = self.tmp / "report-site"
        results_md = self.tmp / "report-RESULTS.md"
        proc = self.run_cmd(
            [
                "report",
                "--results",
                run_out,
                "--out",
                site_out,
                "--probes-dir",
                self.probes_dir,
                "--evidence-dir",
                self.empty_evidence_dir,
                "--results-md",
                results_md,
            ]
        )
        # failbench/report.py is a W4 deliverable: succeed, or fail cleanly with
        # a one-line message. A Python traceback is never acceptable.
        self.assertIn(proc.returncode, (0, 1), combined(proc))
        self.assert_no_traceback(proc)
        if proc.returncode == 0:
            self.assertTrue(site_out.is_dir())
            self.assertTrue((site_out / "index.html").is_file())

    # -- 10. demo alias --------------------------------------------------
    def test_demo_uses_mock_provider(self) -> None:
        demo_out = self.unique_dir("demo-out")
        proc = self.run_cmd(
            [
                "run",
                "--demo",
                "--out",
                demo_out,
                "--probes-dir",
                self.probes_dir,
                "--quiet",
            ]
        )
        self.assertEqual(proc.returncode, 0, combined(proc))
        self.assert_no_traceback(proc)
        results_path = demo_out / "results.json"
        self.assertTrue(results_path.is_file())
        results = read_json(results_path)
        self.assertEqual(results["provider"], "mock")


if __name__ == "__main__":  # pragma: no cover - convenience only
    unittest.main()
