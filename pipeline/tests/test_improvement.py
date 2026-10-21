"""Behavioral tests for the isolated improvement laboratory; no application writes."""
import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "improvement" / "lab.py"
spec = importlib.util.spec_from_file_location("improvement_lab", SCRIPT)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "checkout"
        (self.root / "pipeline" / "skills" / "sample").mkdir(parents=True)
        (self.root / "pipeline" / "skills" / "sample" / "SKILL.md").write_text("baseline")
        self.plan = {
            "schema_version": 1, "project": "vacoin-global",
            "mode": "parallel", "task_id": "T-1", "authorization_ref": "user-message",
            "baseline_ref": "git:test-commit",
            "auto_promote": False, "cross_project_sync": False,
            "candidates": [{"id": "c1", "lever": "skill",
                "hypothesis": "Explicit file requirements reduce regressions",
                "edits": [{"path": "pipeline/skills/sample/SKILL.md",
                           "operation": "modify", "reason": "clarify instructions"}]}],
            "checks": [{"id": "regression", "kind": "regression", "independent": True},
                       {"id": "security", "kind": "security", "independent": True}]
        }

    def evidence(self, candidate, status="passed", regression=True, security=True):
        return {"schema_version": 1, "project": "vacoin-global",
                "task_id": self.plan["task_id"], "candidate_id": candidate,
                "plan_sha256": lab.sha(self.plan),
                "run_id": candidate + "-run",
                "isolated_workspace": "/sandbox/" + candidate,
                "evaluator_ref": "separate-independent-evaluator",
                "status": status, "checks": {"regression": regression, "security": security}}

    def test_valid_plan(self):
        result = lab.validate_plan(self.plan, self.root)
        self.assertEqual(result["candidate_ids"], ["c1"])

    def test_no_cross_project(self):
        p = copy.deepcopy(self.plan)
        p["project"] = "different-project"
        with self.assertRaises(lab.Invalid):
            lab.validate_plan(p, self.root)

    def test_no_automatic_promote_or_sync(self):
        for name in ("auto_promote", "cross_project_sync"):
            p = copy.deepcopy(self.plan)
            p[name] = True
            with self.assertRaises(lab.Invalid):
                lab.validate_plan(p, self.root)

    def test_no_protected_edits_or_traversal(self):
        for path in ("AGENTS.md", "pipeline/GUARDS.md",
                     "pipeline/scripts/pipeline.py", "../outside",
                     "pipeline/skills/../secret", "other/README.md"):
            p = copy.deepcopy(self.plan)
            p["candidates"][0]["edits"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(lab.Invalid):
                lab.validate_plan(p, self.root)

    def test_regression_cannot_be_removed(self):
        p = copy.deepcopy(self.plan)
        p["checks"] = [{"id": "security", "kind": "security", "independent": True},
                       {"id": "scope", "kind": "scope", "independent": True}]
        with self.assertRaises(lab.Invalid):
            lab.validate_plan(p, self.root)

    def test_untrusted_evidence_wrong_plan(self):
        row = self.evidence("c1")
        row["plan_sha256"] = "another"
        with self.assertRaises(lab.Invalid):
            lab.validate_evidence(self.plan, row)

    def test_compose_pass_and_fail(self):
        report = lab.compose(self.plan, [self.evidence("baseline"), self.evidence("c1")])
        self.assertEqual(report["eligible_for_human_review"], ["c1"])
        self.assertIsNone(report["accepted"])
        self.assertEqual(report["promotion"], "manual_only")
        report = lab.compose(self.plan, [self.evidence("baseline"),
                                         self.evidence("c1", security=False)])
        self.assertEqual(report["eligible_for_human_review"], [])

    def test_incomplete_never_eligible(self):
        report = lab.compose(self.plan, [self.evidence("baseline"),
                                         self.evidence("c1", status="incomplete")])
        self.assertEqual(report["eligible_for_human_review"], [])

    def test_missing_and_duplicate_evidence(self):
        with self.assertRaises(lab.Invalid):
            lab.compose(self.plan, [self.evidence("c1")])
        with self.assertRaises(lab.Invalid):
            lab.compose(self.plan, [self.evidence("baseline"), self.evidence("c1"),
                                    self.evidence("c1")])

    def test_experience_requires_manual_approval(self):
        report = lab.compose(self.plan, [self.evidence("baseline"), self.evidence("c1")])
        data = {"candidate_id": "c1", "evidence_ref": "receipt:123",
                "approval_ref": "user:approved", "lesson": "Works on regression suite",
                "limitations": "Only one skill"}
        result = lab.experience(self.plan, report, data)
        self.assertFalse(result["cross_project_sync"])
        data["approval_ref"] = ""
        with self.assertRaises(lab.Invalid):
            lab.experience(self.plan, report, data)

    def test_no_output_inside_project_or_overwrite(self):
        with self.assertRaises(lab.Invalid):
            lab.write_new(self.root / "report.json", {"x": 1}, self.root)
        target = self.home / "report.json"
        lab.write_new(target, {"x": 1}, self.root)
        with self.assertRaises(lab.Invalid):
            lab.write_new(target, {"x": 2}, self.root)

    def test_parallel_schedule_keeps_independent_baseline(self):
        schedule = lab.schedule(self.plan)
        self.assertEqual(schedule["stages"][0]["depends_on"], "baseline")
        self.assertFalse(schedule["automatic_execution"])

    def test_sequential_schedule_has_explicit_dependencies(self):
        p = copy.deepcopy(self.plan)
        p["mode"] = "sequential"
        p["candidates"].append(copy.deepcopy(p["candidates"][0]))
        p["candidates"][1]["id"] = "c2"
        result = lab.schedule(p)
        self.assertEqual([x["depends_on"] for x in result["stages"]], ["baseline", "c1"])
        self.assertEqual(result["stages"][1]["gate"], "previous_evidence_complete_and_validated")


    def test_runner_dry_run_with_frozen_head(self):
        import sys
        from unittest.mock import patch
        improvement_dir = str(SCRIPT.parent)
        if improvement_dir not in sys.path:
            sys.path.insert(0, improvement_dir)
        import runner
        self.plan["baseline_ref"] = "a" * 40
        self.assertEqual(lab.validate_plan(self.plan, self.root)["candidate_ids"], ["c1"])
        with patch.object(runner, "git", side_effect=["", "a" * 40]):
            out = runner.start(self.plan, self.root, self.home / "pilot", "c1",
                               "Improve instruction quality", timeout=120, execute=False)
        self.assertTrue(out["dry_run"])
        self.assertFalse((self.home / "pilot").exists())

    def test_runner_does_not_accept_live_baseline_mismatch(self):
        import sys
        from unittest.mock import patch
        improvement_dir = str(SCRIPT.parent)
        if improvement_dir not in sys.path:
            sys.path.insert(0, improvement_dir)
        import runner
        self.plan["baseline_ref"] = "b" * 40
        with patch.object(runner, "git", side_effect=["", "a" * 40]):
            with self.assertRaises(runner.lab.Invalid):
                runner.start(self.plan, self.root, self.home / "pilot", "c1",
                             "Improve instruction quality", timeout=120, execute=False)

    def test_runner_rejects_sequential_without_gated_lineage(self):
        import sys
        from unittest.mock import patch
        improvement_dir = str(SCRIPT.parent)
        if improvement_dir not in sys.path:
            sys.path.insert(0, improvement_dir)
        import runner
        self.plan["mode"] = "sequential"
        self.plan["candidates"].append(copy.deepcopy(self.plan["candidates"][0]))
        self.plan["candidates"][1]["id"] = "c2"
        self.plan["baseline_ref"] = "a" * 40
        with self.assertRaises(runner.lab.Invalid):
            runner.start(self.plan, self.root, self.home / "pilot", "c2",
                         "Improve instruction quality", timeout=120, execute=False)

    def test_sequential_and_parallel_valid(self):
        for mode in ("parallel", "sequential"):
            p = copy.deepcopy(self.plan)
            p["mode"] = mode
            self.assertEqual(lab.validate_plan(p, self.root)["candidate_ids"], ["c1"])


if __name__ == "__main__":
    unittest.main()
