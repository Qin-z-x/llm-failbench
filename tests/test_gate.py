"""Offline unit tests for ``failbench.gate`` (CI regression gate).

Run from the repository root::

    python -m unittest tests.test_gate -v

Everything uses synthetic results documents written under a temporary
directory; no network, no corpus files, no model calls.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from failbench.gate import (
    GateError,
    compare_files,
    compare_results,
    format_report,
    load_results,
)
from tests.support import make_results_doc, write_json

BASE_RUN_ID = "20260101T000000Z-base"
CURR_RUN_ID = "20260102T000000Z-current"


def _entry(probe_id, cls, status, **extra):
    data = {"probe_id": probe_id, "class": cls, "status": status}
    data.update(extra)
    return data


def _reorder_probes(document, order):
    by_id = {probe["probe_id"]: probe for probe in document["probes"]}
    document["probes"] = [by_id[probe_id] for probe_id in order]
    return document


def _set_statuses(document, mapping):
    for probe in document["probes"]:
        if probe["probe_id"] in mapping:
            probe["status"] = mapping[probe["probe_id"]]
    return document


class GateTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    # -- helpers ---------------------------------------------------------
    def write_run(self, name, entries, run_id):
        """Write ``<tmp>/<name>/results.json`` and return the file path."""
        path = self.tmp / name / "results.json"
        write_json(path, make_results_doc(entries, run_id=run_id))
        return path

    def write_doc(self, name, payload):
        path = self.tmp / name / "results.json"
        write_json(path, payload)
        return path

    # -- 1. identical documents -----------------------------------------
    def test_identical_documents_gate_passes(self):
        entries = [
            _entry("hal_ident_01", "hallucination", "pass"),
            _entry("ctx_ident_01", "context_retrieval", "fail"),
            _entry("rea_ident_01", "reasoning_consistency", "error"),
        ]
        baseline = self.write_run("baseline", entries, BASE_RUN_ID)
        current = self.write_run("current", entries, CURR_RUN_ID)

        comparison = compare_files(baseline, current)

        self.assertFalse(comparison["has_regressions"])
        self.assertEqual(comparison["regressions"], [])
        self.assertEqual(comparison["improvements"], [])
        self.assertEqual(comparison["new_probes"], [])
        self.assertEqual(len(comparison["unchanged"]), len(entries))
        self.assertEqual(comparison["summary"]["regressions"], 0)
        self.assertEqual(comparison["summary"]["unchanged"], len(entries))
        self.assertEqual(comparison["summary"]["baseline_probes"], len(entries))
        self.assertEqual(comparison["summary"]["current_probes"], len(entries))
        self.assertEqual(comparison["baseline"]["run_id"], BASE_RUN_ID)
        self.assertEqual(comparison["current"]["run_id"], CURR_RUN_ID)
        self.assertEqual(comparison["baseline"]["counts"]["pass"], 1)
        self.assertEqual(comparison["baseline"]["counts"]["fail"], 1)
        self.assertEqual(comparison["baseline"]["counts"]["error"], 1)

        report = format_report(comparison)
        self.assertIn("GATE PASS", report)
        self.assertNotIn("GATE FAIL", report)
        self.assertIn("FailBench regression gate", report)
        self.assertIn("Unchanged: {0}".format(len(entries)), report)
        self.assertIn("no regressions ({0} probes compared)".format(len(entries)), report)

    # -- 2. status regressions ------------------------------------------
    def test_status_regressions_are_detected(self):
        baseline_entries = [
            _entry("hal_reg_01", "hallucination", "pass"),
            _entry("ctx_reg_01", "context_retrieval", "pass"),
            _entry("rea_reg_01", "reasoning_consistency", "fail"),
        ]
        current_entries = [
            _entry("hal_reg_01", "hallucination", "fail"),
            _entry("ctx_reg_01", "context_retrieval", "error"),
            _entry("rea_reg_01", "reasoning_consistency", "error"),
        ]
        comparison = compare_files(
            self.write_run("baseline", baseline_entries, BASE_RUN_ID),
            self.write_run("current", current_entries, CURR_RUN_ID),
        )

        self.assertTrue(comparison["has_regressions"])
        regressions = comparison["regressions"]
        self.assertEqual(
            [item["probe_id"] for item in regressions],
            ["hal_reg_01", "ctx_reg_01", "rea_reg_01"],
        )
        self.assertTrue(all(item["kind"] == "status_regression" for item in regressions))
        transitions = {
            item["probe_id"]: (item["baseline_status"], item["current_status"])
            for item in regressions
        }
        self.assertEqual(transitions["hal_reg_01"], ("pass", "fail"))
        self.assertEqual(transitions["ctx_reg_01"], ("pass", "error"))
        self.assertEqual(transitions["rea_reg_01"], ("fail", "error"))
        self.assertEqual(comparison["summary"]["regressions"], 3)
        self.assertEqual(comparison["improvements"], [])

        report = format_report(comparison)
        self.assertIn("GATE FAIL", report)
        self.assertIn("3 regression(s) detected.", report)
        self.assertIn("Regressions (3):", report)
        for probe_id in ("hal_reg_01", "ctx_reg_01", "rea_reg_01"):
            self.assertIn(probe_id, report)

    # -- 3. improvements -------------------------------------------------
    def test_improvements_are_reported(self):
        baseline_entries = [
            _entry("hal_imp_01", "hallucination", "fail"),
            _entry("ctx_imp_01", "context_retrieval", "error"),
            _entry("rea_imp_01", "reasoning_consistency", "error"),
        ]
        current_entries = [
            _entry("hal_imp_01", "hallucination", "pass"),
            _entry("ctx_imp_01", "context_retrieval", "pass"),
            _entry("rea_imp_01", "reasoning_consistency", "fail"),
        ]
        comparison = compare_files(
            self.write_run("baseline", baseline_entries, BASE_RUN_ID),
            self.write_run("current", current_entries, CURR_RUN_ID),
        )

        self.assertFalse(comparison["has_regressions"])
        self.assertEqual(comparison["regressions"], [])
        improvements = comparison["improvements"]
        self.assertEqual(
            [item["probe_id"] for item in improvements],
            ["hal_imp_01", "ctx_imp_01", "rea_imp_01"],
        )
        transitions = {
            item["probe_id"]: (item["baseline_status"], item["current_status"])
            for item in improvements
        }
        self.assertEqual(transitions["hal_imp_01"], ("fail", "pass"))
        self.assertEqual(transitions["ctx_imp_01"], ("error", "pass"))
        self.assertEqual(transitions["rea_imp_01"], ("error", "fail"))
        self.assertEqual(comparison["summary"]["improvements"], 3)

        report = format_report(comparison)
        self.assertIn("GATE PASS", report)
        self.assertNotIn("GATE FAIL", report)
        self.assertIn("Improvements (3):", report)
        self.assertIn("IMPROVEMENT", report)

    # -- 4. missing probe ------------------------------------------------
    def test_missing_probe_is_regression(self):
        baseline_entries = [
            _entry("hal_keep_01", "hallucination", "pass"),
            _entry("ctx_gone_01", "context_retrieval", "pass"),
        ]
        current_entries = [_entry("hal_keep_01", "hallucination", "pass")]
        comparison = compare_files(
            self.write_run("baseline", baseline_entries, BASE_RUN_ID),
            self.write_run("current", current_entries, CURR_RUN_ID),
        )

        self.assertTrue(comparison["has_regressions"])
        self.assertEqual(len(comparison["regressions"]), 1)
        missing = comparison["regressions"][0]
        self.assertEqual(missing["probe_id"], "ctx_gone_01")
        self.assertEqual(missing["class"], "context_retrieval")
        self.assertEqual(missing["kind"], "missing_probe")
        self.assertEqual(missing["baseline_status"], "pass")
        self.assertIsNone(missing["current_status"])
        self.assertEqual(comparison["summary"]["regressions"], 1)

        report = format_report(comparison)
        self.assertIn("MISSING", report)
        self.assertIn("ctx_gone_01", report)
        self.assertIn("probe missing from current results (was pass)", report)
        self.assertIn("GATE FAIL", report)

    # -- 5. new probe ----------------------------------------------------
    def test_new_probe_is_informational(self):
        baseline_entries = [_entry("hal_new_01", "hallucination", "pass")]
        current_entries = [
            _entry("hal_new_01", "hallucination", "pass"),
            _entry("ml_added_01", "multilingual", "fail"),
        ]
        comparison = compare_files(
            self.write_run("baseline", baseline_entries, BASE_RUN_ID),
            self.write_run("current", current_entries, CURR_RUN_ID),
        )

        self.assertFalse(comparison["has_regressions"])
        self.assertEqual(comparison["regressions"], [])
        self.assertEqual(len(comparison["new_probes"]), 1)
        novel = comparison["new_probes"][0]
        self.assertEqual(novel["probe_id"], "ml_added_01")
        self.assertEqual(novel["class"], "multilingual")
        self.assertEqual(novel["current_status"], "fail")
        self.assertEqual(comparison["summary"]["new"], 1)
        self.assertEqual(comparison["summary"]["current_probes"], 2)

        report = format_report(comparison)
        self.assertIn("New probes (not in baseline): 1", report)
        self.assertIn("GATE PASS", report)

    # -- 6. ordering determinism ----------------------------------------
    def test_ordering_and_summary_are_deterministic(self):
        baseline_entries = [
            _entry("rea_ord_01", "reasoning_consistency", "fail"),
            _entry("hal_ord_01", "hallucination", "pass"),
            _entry("ctx_ord_01", "context_retrieval", "pass"),
            _entry("ml_ord_01", "multilingual", "pass"),
        ]
        current_entries = [
            _entry("hal_ord_01", "hallucination", "fail"),
            _entry("rea_ord_01", "reasoning_consistency", "error"),
            _entry("ctx_ord_01", "context_retrieval", "pass"),
            _entry("det_added_02", "determinism_calibration", "pass"),
            _entry("syc_added_01", "sycophancy", "fail"),
        ]
        baseline_order = ["rea_ord_01", "hal_ord_01", "ctx_ord_01", "ml_ord_01"]
        current_order = [
            "hal_ord_01",
            "rea_ord_01",
            "ctx_ord_01",
            "det_added_02",
            "syc_added_01",
        ]
        baseline_doc = _reorder_probes(
            make_results_doc(baseline_entries, run_id=BASE_RUN_ID), baseline_order
        )
        current_doc = _reorder_probes(
            make_results_doc(current_entries, run_id=CURR_RUN_ID), current_order
        )

        comparison = compare_results(baseline_doc, current_doc)

        # Baseline order, mixing status regressions and the missing probe.
        self.assertEqual(
            [item["probe_id"] for item in comparison["regressions"]],
            ["rea_ord_01", "hal_ord_01", "ml_ord_01"],
        )
        self.assertEqual(
            [item["kind"] for item in comparison["regressions"]],
            ["status_regression", "status_regression", "missing_probe"],
        )
        self.assertEqual(comparison["improvements"], [])
        self.assertEqual(
            [item["probe_id"] for item in comparison["unchanged"]], ["ctx_ord_01"]
        )
        # New probes follow current document order.
        self.assertEqual(
            [item["probe_id"] for item in comparison["new_probes"]],
            ["det_added_02", "syc_added_01"],
        )
        self.assertEqual(comparison["baseline"]["path"], None)
        self.assertEqual(comparison["baseline"]["run_id"], BASE_RUN_ID)
        self.assertEqual(comparison["current"]["run_id"], CURR_RUN_ID)

        summary = comparison["summary"]
        self.assertEqual(summary["regressions"], len(comparison["regressions"]))
        self.assertEqual(summary["improvements"], len(comparison["improvements"]))
        self.assertEqual(summary["new"], len(comparison["new_probes"]))
        self.assertEqual(summary["unchanged"], len(comparison["unchanged"]))
        self.assertEqual(summary["baseline_probes"], 4)
        self.assertEqual(summary["current_probes"], 5)
        self.assertEqual(
            summary["regressions"] + summary["improvements"] + summary["unchanged"],
            summary["baseline_probes"],
        )
        # Probes present in both runs: unchanged + improvements + status regressions.
        present_regressions = [
            item for item in comparison["regressions"] if item["kind"] != "missing_probe"
        ]
        self.assertEqual(
            summary["unchanged"] + summary["improvements"] + len(present_regressions),
            summary["current_probes"] - summary["new"],
        )

    # -- 7. compare_files paths and gate errors --------------------------
    def test_compare_files_paths_and_gate_errors(self):
        entries = [_entry("hal_err_01", "hallucination", "pass")]
        baseline_file = self.write_run("baseline", entries, BASE_RUN_ID)
        current_file = self.write_run("current", entries, CURR_RUN_ID)

        by_file = compare_files(baseline_file, current_file)
        self.assertEqual(by_file["baseline"]["path"], str(baseline_file))
        self.assertEqual(by_file["current"]["path"], str(current_file))
        self.assertFalse(by_file["has_regressions"])

        by_dir = compare_files(baseline_file.parent, current_file.parent)
        self.assertEqual(by_dir["baseline"]["path"], str(baseline_file.parent))
        self.assertEqual(by_dir["current"]["path"], str(current_file.parent))

        self.assertEqual(load_results(baseline_file)["run_id"], BASE_RUN_ID)
        self.assertEqual(load_results(baseline_file.parent)["run_id"], BASE_RUN_ID)

        with self.assertRaises(GateError) as ctx:
            load_results(self.tmp / "missing_run" / "results.json")
        self.assertIn("results file not found", str(ctx.exception))

        empty_dir = self.tmp / "empty_run"
        empty_dir.mkdir()
        with self.assertRaises(GateError) as ctx:
            compare_files(empty_dir, current_file)
        self.assertIn("results file not found", str(ctx.exception))

        bad_json = self.tmp / "bad_json" / "results.json"
        bad_json.parent.mkdir(parents=True)
        bad_json.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(GateError) as ctx:
            load_results(bad_json)
        self.assertIn("invalid JSON", str(ctx.exception))

        invalid_documents = {
            "no_probes": {"schema": 1},
            "probes_not_list": {"schema": 1, "probes": {}},
            "schema_not_int": {"schema": "1", "probes": []},
            "probe_not_object": {"schema": 1, "probes": ["hal_x_01"]},
            "probe_missing_status": {
                "schema": 1,
                "probes": [{"probe_id": "hal_x_01", "class": "hallucination"}],
            },
        }
        for name, payload in invalid_documents.items():
            with self.subTest(document=name):
                path = self.write_doc(name, payload)
                with self.assertRaises(GateError) as ctx:
                    load_results(path)
                self.assertIn("invalid results document", str(ctx.exception))

        with self.assertRaises(GateError):
            compare_results({"schema": 1}, make_results_doc(entries))

        # Missing ``counts`` is tolerated and rebuilt from the probes.
        doc = make_results_doc(entries)
        doc.pop("counts")
        path = self.write_doc("no_counts", doc)
        comparison = compare_results(load_results(path), load_results(path))
        self.assertEqual(comparison["baseline"]["counts"]["probes"], 1)
        self.assertEqual(comparison["baseline"]["counts"]["pass"], 1)

    # -- 8. deterministic / bounded formatting ---------------------------
    def test_format_report_deterministic_and_capped(self):
        baseline_entries = [
            _entry("hal_fmt_{0:02d}".format(index), "hallucination", "pass")
            for index in range(25)
        ]
        current_entries = [
            _entry("hal_fmt_{0:02d}".format(index), "hallucination", "fail")
            for index in range(25)
        ]
        comparison = compare_files(
            self.write_run("baseline", baseline_entries, BASE_RUN_ID),
            self.write_run("current", current_entries, CURR_RUN_ID),
        )
        self.assertEqual(len(comparison["regressions"]), 25)

        first = format_report(comparison)
        second = format_report(comparison)
        self.assertEqual(first, second)
        self.assertNotIn("Traceback", first)
        self.assertFalse(first.endswith("\n"))
        self.assertIn("... and 5 more", first)
        self.assertIn("Regressions (25):", first)
        self.assertIn("GATE FAIL", first)
        self.assertLess(max(len(line) for line in first.splitlines()), 200)
        shown = [line for line in first.splitlines() if "hal_fmt_" in line]
        self.assertEqual(len(shown), 20)

    # -- 9. unknown status values are harmless ---------------------------
    def test_unknown_statuses_are_handled_defensively(self):
        baseline_doc = make_results_doc(
            [
                _entry("hal_unk_01", "hallucination", "pass"),
                _entry("hal_unk_02", "hallucination", "pass"),
                _entry("hal_unk_03", "hallucination", "pass"),
                _entry("hal_unk_04", "hallucination", "pass"),
            ],
            run_id=BASE_RUN_ID,
        )
        _set_statuses(
            baseline_doc,
            {
                "hal_unk_01": "skipped",
                "hal_unk_02": "skipped",
                "hal_unk_03": "pass",
                "hal_unk_04": "pass",
            },
        )
        current_doc = make_results_doc(
            [
                _entry("hal_unk_01", "hallucination", "pass"),
                _entry("hal_unk_02", "hallucination", "pass"),
                _entry("hal_unk_03", "hallucination", "pass"),
                _entry("hal_unk_05", "hallucination", "pass"),
            ],
            run_id=CURR_RUN_ID,
        )
        _set_statuses(
            current_doc,
            {
                "hal_unk_01": "skipped",
                "hal_unk_02": "pass",
                "hal_unk_03": "skipped",
                "hal_unk_05": "skipped",
            },
        )

        comparison = compare_files(
            self.write_doc("baseline", baseline_doc),
            self.write_doc("current", current_doc),
        )

        # Only the genuinely missing probe is a regression.
        self.assertEqual(len(comparison["regressions"]), 1)
        self.assertEqual(comparison["regressions"][0]["probe_id"], "hal_unk_04")
        self.assertEqual(comparison["regressions"][0]["kind"], "missing_probe")
        self.assertEqual(comparison["improvements"], [])
        unchanged = {item["probe_id"]: item["status"] for item in comparison["unchanged"]}
        self.assertEqual(unchanged["hal_unk_01"], "skipped")
        self.assertEqual(unchanged["hal_unk_02"], "pass")
        self.assertEqual(unchanged["hal_unk_03"], "skipped")
        self.assertEqual(len(comparison["unchanged"]), 3)
        self.assertEqual(
            [item["probe_id"] for item in comparison["new_probes"]], ["hal_unk_05"]
        )
        self.assertTrue(comparison["has_regressions"])

        report = format_report(comparison)  # must not raise
        self.assertIn("MISSING", report)
        self.assertIn("GATE FAIL", report)


if __name__ == "__main__":
    unittest.main()
