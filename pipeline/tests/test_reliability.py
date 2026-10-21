"""Local negative cases for guards and recovery; synthetic data only."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline.py"
spec = importlib.util.spec_from_file_location("reliability_engine", SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        self.m = {"schema_version": 1, "task_id": "task-a", "plan_ref": "plan-v1",
                  "authorization_ref": "user-file-batch", "root_kind": "sandbox",
                  "files": [{"path": "a.py", "change": "modify", "sections": "setting",
                             "expected_behavior": "read environment"}], "checks": []}
        (self.root / "a.py").write_text("value = 1\n")

    def patch(self, path="a.py", content="+value = 2"):
        return f"*** Begin Patch\n*** Update File: {path}\n{content}\n*** End Patch\n"

    def hook(self, path="a.py", content="+value = 2"):
        return engine.hook_decision(self.root, self.m, {
            "hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(self.root),
            "tool_input": {"command": self.patch(path, content)}})

    def manifest(self):
        p = Path(self.tmp.name) / "manifest.json"
        p.write_text(json.dumps(self.m))
        return p

    def test_key_in_added_line_denied_but_removal_allowed(self):
        synthetic = "sk-proj-" + "A" * 48
        with self.assertRaises(engine.Invalid) as caught:
            self.hook(content="+key = '" + synthetic + "'")
        self.assertNotIn(synthetic, str(caught.exception))
        self.hook(content="-key = '" + synthetic + "'\n+key = os.environ['API_KEY']")

    def test_secret_starting_with_plus_not_hidden_as_diff_header(self):
        synthetic = "ghp_" + "B" * 36
        with self.assertRaises(engine.Invalid):
            self.hook(content="+++" + synthetic)

    def test_placeholder_and_environment_access_allowed(self):
        self.hook(content="+key = os.environ['API_KEY']\n+# sk-proj-REPLACE")

    def test_recognised_families_without_printing_values(self):
        samples = ["github_pat_" + "D" * 60, "AKIA" + "E" * 16,
                   "xoxb-" + "F" * 30, "-----BEGIN " + "PRIVATE KEY-----"]
        for value in samples:
            with self.assertRaises(engine.Invalid) as caught:
                self.hook(content="+" + value)
            self.assertNotIn(value, str(caught.exception))

    def test_secret_cli_reports_location_without_value(self):
        synthetic = "sk-ant-" + "C" * 48
        (self.root / "a.py").write_text("token = '" + synthetic + "'\n")
        r = subprocess.run([sys.executable, str(SCRIPT), "secrets", "--root", str(self.root),
                            "--manifest", str(self.manifest())], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(synthetic, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["findings"][0]["line"], 1)

    def test_protection_even_when_file_is_in_scope(self):
        self.m["files"][0]["path"] = "AGENTS.md"
        with self.assertRaises(engine.Invalid):
            self.hook(path="AGENTS.md")
        self.m["guards"] = {"maintenance_paths": ["AGENTS.md"],
                            "maintenance_authorization_ref": "user-approved-pipeline-edit"}
        self.hook(path="AGENTS.md")

    def test_additional_protected_path_has_same_rule(self):
        self.m["guards"] = {"protected_paths": ["a.py"]}
        with self.assertRaises(engine.Invalid):
            self.hook()

    def test_protected_alias_cannot_hide_target(self):
        try:
            (self.root / "AGENTS.md").symlink_to(self.root / "a.py")
        except OSError:
            self.skipTest("Symlink permission unavailable")
        with self.assertRaises(engine.Invalid):
            self.hook()

    def test_malformed_guard_config_and_empty_maintenance_ref_rejected(self):
        for g in ({"unknown": True}, {"maintenance_paths": ["AGENTS.md"]},
                  {"maintenance_authorization_ref": "user"}, {"protected_paths": ["../x"]},
                  {"research": {"targets": ["a.py"], "record": "r.json", "skip_authorization_ref": True}}):
            self.m["guards"] = g
            with self.subTest(g=g), self.assertRaises(engine.Invalid):
                engine.load_manifest(self.manifest())

    def research(self):
        self.m["guards"] = {"research": {"targets": ["a.py"], "record": "research.json"}}
        (self.root / "report.md").write_text("Sources and applicable limitations")
        record = {"task_id": self.m["task_id"], "plan_ref": self.m["plan_ref"],
                  "report_path": "report.md", "report_sha256": engine.file_hash(self.root / "report.md")}
        (self.root / "research.json").write_text(json.dumps(record))
        return record

    def test_research_missing_refuses_but_unrelated_patch_does_not_require_it(self):
        self.m["guards"] = {"research": {"targets": ["architecture.md"], "record": "absent.json"}}
        self.hook()
        self.m["files"].append(dict(self.m["files"][0], path="architecture.md"))
        with self.assertRaises(OSError):
            self.hook(path="architecture.md")

    def test_research_wrong_task_plan_or_changed_report_refuses(self):
        for key in ("task_id", "plan_ref"):
            record = self.research();record[key] = "other"
            (self.root / "research.json").write_text(json.dumps(record))
            with self.assertRaises(engine.Invalid):
                self.hook()
        self.research();(self.root / "report.md").write_text("changed")
        with self.assertRaises(engine.Invalid):
            self.hook()

    def test_research_matching_record_and_explicit_skip(self):
        self.research();self.hook()
        (self.root / "research.json").unlink()
        self.m["guards"]["research"]["skip_authorization_ref"] = "user-request-to-skip"
        self.hook()

    def sessions(self):
        folder = self.root / "pipeline/sessions/current"
        folder.mkdir(parents=True)
        (folder.parent / "index.json").write_text(json.dumps({"sessions": [
            {"id": "current", "task_id": "task-a", "status": "active", "state_file": "current/SESSION.md"},
            {"id": "other", "task_id": "other-task", "status": "open", "state_file": "not-present/SESSION.md"}]}))
        (folder / "SESSION.md").write_text("- task_id: task-a.\n- session_id: current.\n"
                                         "- Статус сессии: active.\n- task_ref: [TASK](../../../TASK.md).\n")
        (folder / "HISTORY.md").write_text("Started, interrupted; no acceptance")
        (self.root / "TASK.md").write_text("Pending user acceptance")
        return folder

    def test_resume_reads_selected_only_and_does_not_mutate(self):
        self.sessions()
        before = engine.scan(self.root)
        r = engine.resume_check(self.root, self.m, "current")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["versions"]), 3)
        self.assertFalse(r["automatic_retry"])
        self.assertEqual(r["user_acceptance"], "not_verified")
        self.assertEqual(engine.scan(self.root), before)

    def test_resume_detects_mismatch_missing_history_and_out_of_scope(self):
        folder = self.sessions();baseline = engine.snapshot(self.root, self.m)
        (folder / "SESSION.md").write_text((folder / "SESSION.md").read_text().replace("active", "completed"))
        (folder / "HISTORY.md").unlink()
        r = engine.resume_check(self.root, self.m, "current", baseline)
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["issues"]), 3)

    def test_resume_wrong_task_and_external_reference_refused(self):
        folder = self.sessions()
        with self.assertRaises(engine.Invalid):
            engine.resume_check(self.root, self.m, "other")
        (folder / "SESSION.md").write_text((folder / "SESSION.md").read_text().replace("../../../TASK.md", "../../../../outside.md"))
        with self.assertRaises(engine.Invalid):
            engine.resume_check(self.root, self.m, "current")

    def test_hook_cli_returns_deny_without_value_for_guard_failure(self):
        synthetic = "sk-proj-" + "Z" * 48
        payload = {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": str(self.root),
                   "tool_input": {"command": self.patch(content="+" + synthetic)}}
        r = subprocess.run([sys.executable, str(SCRIPT), "hook", "--root", str(self.root),
                            "--manifest", str(self.manifest())], input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertNotIn(synthetic, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
