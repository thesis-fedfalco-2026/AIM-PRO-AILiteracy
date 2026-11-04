from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agent_system.events import MemoryEventLog
from learning.planning import LearningPlanDraft
from evaluation.__main__ import main, report
from evaluation.cases import CASES, socratic
from evaluation.harness import run_case


class EvaluationSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)
        cls.log = MemoryEventLog()
        cls.results = [run_case(case, cls.log) for case in CASES]

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_case_ids_are_unique_and_categories_cover_the_issue(self):
        self.assertEqual(len({c.id for c in CASES}), len(CASES))
        self.assertEqual({c.category for c in CASES},
                         {"control", "non_supporting_citation", "prompt_injection", "socratic_leakage"})

    def test_scripted_outcomes_match_their_declared_defence(self):
        # A new deterministic defence turns a LEAKED case into BLOCKED: update its expectation.
        for result in self.results:
            with self.subTest(case=result.case_id):
                self.assertEqual(result.outcome, result.expected)
        by_defence = Counter((r.defence, r.outcome) for r in self.results)
        self.assertEqual(by_defence[("deterministic", "LEAKED")], 0)
        self.assertEqual(by_defence[("semantic_review", "BLOCKED")], 0)

    def test_report_derives_metrics_from_the_event_log(self):
        summary = report(self.results, self.log.events, "scripted")
        self.assertEqual(summary["mismatches"], [])
        self.assertEqual(summary["not_executed"], [])
        # Synthesis-level attacks are attributed to the condition that stopped them.
        self.assertEqual(summary["metrics"]["final_violations"],
                         {"citation_not_from_results": 1, "application_claim": 1})
        self.assertEqual(summary["control_false_rejection_rate"], 0.0)
        self.assertEqual(summary["metrics"]["runs"], len(CASES))
        self.assertEqual(summary["metrics"]["worker_steps"]["rejected"], 5)
        self.assertEqual(len({r.run_id for r in self.results}), len(CASES))

    def test_a_case_whose_worker_never_runs_is_not_counted_as_blocked(self):
        case = replace(CASES[1], id="unplanned", worker=socratic(), role="SOCRATIC")
        with patch("evaluation.harness.plan", return_value=LearningPlanDraft(steps=())):
            result = run_case(case, MemoryEventLog())
        self.assertEqual(result.outcome, "NOT_EXECUTED")


class EvaluationCliTest(unittest.TestCase):
    def run_cli(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with TemporaryDirectory() as directory, redirect_stdout(stdout), redirect_stderr(stderr):
            path = Path(directory) / "events.jsonl"
            try:
                main([*argv, "--log", str(path)])
                code = 0
            except SystemExit as exit:
                code = exit.code
            logged = path.exists()
        return json.loads(stdout.getvalue()), stderr.getvalue(), code, logged

    def test_progress_goes_to_stderr_and_the_report_to_stdout(self):
        summary, progress, code, logged = self.run_cli("--case", "control-teacher", "--repeat", "2", "--check")
        self.assertEqual(code, 0)
        self.assertTrue(logged)
        self.assertEqual(summary["metrics"]["runs"], 2)
        self.assertIn("2 scripted runs", progress)
        self.assertIn("[2/2] control-teacher: ANSWERED (ANSWER)", progress)

    def test_a_failing_run_is_reported_without_discarding_the_others(self):
        real = run_case

        def flaky(case, *args, **kwargs):
            if case.id == "control-socratic":
                raise TimeoutError("provider stalled")
            return real(case, *args, **kwargs)

        with patch("evaluation.__main__.run_case", side_effect=flaky):
            summary, progress, code, _ = self.run_cli(
                "--case", "control-teacher", "--case", "control-socratic", "--check")
        self.assertEqual(code, 1)
        self.assertEqual(summary["errors"], ["control-socratic: TimeoutError"])
        self.assertEqual(summary["control_false_rejection_rate"], 0.0)
        self.assertIn("control-socratic: ERROR", progress)


if __name__ == "__main__":
    unittest.main()
