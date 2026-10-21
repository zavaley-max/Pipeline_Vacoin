"""Behavioural tests of adapted guards, using temporary files only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline.py"
spec = importlib.util.spec_from_file_location("vacoin_pipeline", SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        (self.root / "a.txt").write_text("old", encoding="utf-8")
        (self.root / "existing-change.txt").write_text("unfinished", encoding="utf-8")
        self.m = {"schema_version": 1, "task_id": "task-a", "plan_ref": "approved-plan",
                  "authorization_ref": "user-message", "root_kind": "sandbox",
                  "files": [{"path": "a.txt", "change": "modify", "sections": "text",
                             "expected_behavior": "new content"}],
                  "checks": [{"id": "targeted", "argv": [sys.executable, "-c", "print('ok')"],
                              "lanes": ["minimal", "final"], "timeout_seconds": 5}]}

    def manifest_file(self, m=None):
        path = self.base / "scope.json"
        path.write_text(json.dumps(m or self.m), encoding="utf-8")
        return path

    def payload(self, patch, **kwargs):
        return dict(hook_event_name="PreToolUse", tool_name="apply_patch",
                    cwd=str(self.root), tool_input={"command": patch}, **kwargs)

    def patch(self, op, path):
        return f"*** Begin Patch\n*** {op} File: {path}\n+value\n*** End Patch\n"

    def test_manifest_rejects_traversal_absolute_alias_and_ignored_dir(self):
        for name in ("../a.txt", "/a.txt", "D:/a.txt", "src/../a.txt", "src\\a.txt", "node_modules/a.txt"):
            with self.subTest(name=name):
                m = copy.deepcopy(self.m)
                m["files"][0]["path"] = name
                with self.assertRaises(engine.Invalid):
                    engine.load_manifest(self.manifest_file(m))

    def test_duplicate_windows_case_is_rejected(self):
        m = copy.deepcopy(self.m)
        f = dict(m["files"][0], path="A.txt")
        m["files"].append(f)
        with self.assertRaises(engine.Invalid):
            engine.load_manifest(self.manifest_file(m))

    def test_unknown_change_and_empty_sections_rejected(self):
        for key, value in (("change", "overwrite-all"), ("sections", "")):
            m = copy.deepcopy(self.m)
            m["files"][0][key] = value
            with self.assertRaises(engine.Invalid):
                engine.load_manifest(self.manifest_file(m))

    def test_missing_original_file_rejected(self):
        (self.root / "a.txt").unlink()
        with self.assertRaises(engine.Invalid):
            engine.snapshot(self.root, self.m)

    def test_authorized_edit_with_preexisting_change(self):
        baseline = engine.snapshot(self.root, self.m)
        (self.root / "a.txt").write_text("new", encoding="utf-8")
        result = engine.check_scope(self.root, self.m, baseline)
        self.assertTrue(result["ok"])
        self.assertEqual([x["path"] for x in result["changed"]], ["a.txt"])

    def test_extra_edit_create_and_delete_are_detected(self):
        baseline = engine.snapshot(self.root, self.m)
        (self.root / "existing-change.txt").write_text("overwritten", encoding="utf-8")
        (self.root / "extra.txt").write_text("extra", encoding="utf-8")
        (self.root / "a.txt").unlink()
        result = engine.check_scope(self.root, self.m, baseline)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["out_of_scope"]), 3)

    def test_changed_manifest_or_wrong_root_cannot_reuse_baseline(self):
        baseline = engine.snapshot(self.root, self.m)
        changed = copy.deepcopy(self.m)
        changed["files"][0]["sections"] = "broader"
        for m, b in ((changed, baseline), (self.m, dict(baseline, root="other"))):
            with self.assertRaises(engine.Invalid):
                engine.check_scope(self.root, m, b)

    def test_non_object_baseline_is_structured_refusal(self):
        with self.assertRaises(engine.Invalid):
            engine.check_scope(self.root, self.m, [])
        baseline = self.base / "bad-baseline.json"
        baseline.write_text("[]", encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "scope", "--root", str(self.root),
                                 "--manifest", str(self.manifest_file()), "--baseline", str(baseline)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stderr)["ok"])

    def test_doctor_requires_script_and_all_skills(self):
        docs = ["AGENTS.md", "pipeline/README.md", "pipeline/COMMANDS.md", "pipeline/GUARDS.md",
                "pipeline/SKILLS.md", "pipeline/journals/ERRORS.md"]
        for name in docs:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        result = engine.doctor(self.root)
        self.assertFalse(result["ok"])
        self.assertIn("pipeline/scripts/pipeline.py", result["missing"])
        for name in engine.REQUIRED_SKILLS:
            for suffix in ("SKILL.md", "agents/openai.yaml"):
                p = self.root / "pipeline/skills" / name / suffix
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
        script = self.root / "pipeline/scripts/pipeline.py"
        script.parent.mkdir(parents=True)
        script.touch()
        self.assertTrue(engine.doctor(self.root)["ok"])
        (self.root / "pipeline/skills/vacoin-review/SKILL.md").unlink()
        result = engine.doctor(self.root)
        self.assertFalse(result["ok"])
        self.assertIn("pipeline/skills/vacoin-review/SKILL.md", result["missing"])

    def test_before_after_cannot_observe_temporary_restored_edit(self):
        self.m["checks"][0]["argv"][-1] = (
            "from pathlib import Path; p=Path('a.txt'); old=p.read_bytes(); "
            "p.write_bytes(b'temporary'); print(p.read_text()); p.write_bytes(old)"
        )
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        self.assertEqual(receipt["verdict"], "passed")
        self.assertEqual(receipt["input_before"], receipt["input_after"])

    def test_artifacts_cannot_overwrite_or_change_own_root(self):
        with self.assertRaises(engine.Invalid):
            engine.write_artifact(self.root / "result.json", self.root, {})
        path = self.base / "result.json"
        engine.write_artifact(path, self.root, {})
        with self.assertRaises(engine.Invalid):
            engine.write_artifact(path, self.root, {})

    def test_pass_receipt_matches_current_content(self):
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        self.assertEqual(receipt["verdict"], "passed")
        self.assertTrue(engine.check_receipt(self.root, self.m, receipt, "targeted", "minimal")["ok"])
        self.assertEqual(receipt["user_acceptance"], "not_recorded")

    def test_second_edit_same_filename_invalidates_receipt(self):
        (self.root / "a.txt").write_text("first edit", encoding="utf-8")
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        (self.root / "a.txt").write_text("second edit", encoding="utf-8")
        with self.assertRaises(engine.Invalid):
            engine.check_receipt(self.root, self.m, receipt, "targeted", "minimal")

    def test_modified_command_or_another_task_invalidates_receipt(self):
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        for modified in (dict(self.m, task_id="task-b"), copy.deepcopy(self.m)):
            if modified["task_id"] == "task-a":
                modified["checks"][0]["argv"][-1] = "print('different')"
            with self.assertRaises(engine.Invalid):
                engine.check_receipt(self.root, modified, receipt, "targeted", "minimal")

    def test_failed_command_cannot_pass(self):
        self.m["checks"][0]["argv"][-1] = "raise SystemExit(7)"
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        self.assertEqual(receipt["exit_code"], 7)
        with self.assertRaises(engine.Invalid):
            engine.check_receipt(self.root, self.m, receipt, "targeted", "minimal")

    def test_code_changed_during_test_is_not_a_pass(self):
        self.m["checks"][0]["argv"][-1] = "from pathlib import Path; Path('a.txt').write_text('changed')"
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["verdict"], "failed")

    def test_timeout_is_failed(self):
        self.m["checks"][0]["argv"][-1] = "import time; time.sleep(3)"
        self.m["checks"][0]["timeout_seconds"] = 1
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        self.assertTrue(receipt["timed_out"])
        self.assertEqual(receipt["verdict"], "failed")

    def test_full_check_not_permitted_in_minimal_lane(self):
        self.m["checks"][0]["lanes"] = ["final"]
        with self.assertRaises(engine.Invalid):
            engine.run_check(self.root, self.m, "targeted", "minimal")

    def test_server_command_not_executed(self):
        self.m["root_kind"] = "server-files"
        self.m["checks"][0]["argv"][-1] = "from pathlib import Path; Path('server-touch').touch()"
        with self.assertRaises(engine.Invalid):
            engine.run_check(self.root, self.m, "targeted", "final")
        self.assertFalse((self.root / "server-touch").exists())

    def test_zero_boolean_is_not_successful_exit_code(self):
        receipt = engine.run_check(self.root, self.m, "targeted", "minimal")
        receipt["exit_code"] = False
        with self.assertRaises(engine.Invalid):
            engine.check_receipt(self.root, self.m, receipt, "targeted", "minimal")

    def test_hook_allows_planned_and_rejects_extra_file(self):
        result = engine.hook_decision(self.root, self.m, self.payload(self.patch("Update", "a.txt")))
        self.assertNotIn("permissionDecision", result["hookSpecificOutput"])
        for name in ("extra.txt", "../outside.txt"):
            with self.assertRaises(engine.Invalid):
                engine.hook_decision(self.root, self.m, self.payload(self.patch("Update", name)))

    def test_hook_parses_all_files_not_only_first(self):
        patch = "*** Begin Patch\n*** Update File: a.txt\n+x\n*** Add File: extra.txt\n+y\n*** End Patch\n"
        with self.assertRaises(engine.Invalid):
            engine.hook_decision(self.root, self.m, self.payload(patch))

    def test_hook_allows_followup_edit_of_created_file(self):
        self.m["files"][0].update(path="new.txt", change="create")
        engine.hook_decision(self.root, self.m, self.payload(self.patch("Add", "new.txt")))
        engine.hook_decision(self.root, self.m, self.payload(self.patch("Update", "new.txt")))

    def test_move_requires_both_old_and_new_paths(self):
        patch = "*** Begin Patch\n*** Update File: a.txt\n*** Move to: b.txt\n+x\n*** End Patch\n"
        with self.assertRaises(engine.Invalid):
            engine.hook_decision(self.root, self.m, self.payload(patch))
        self.m["files"][0]["change"] = "delete"
        self.m["files"].append(dict(self.m["files"][0], path="b.txt", change="create"))
        engine.hook_decision(self.root, self.m, self.payload(patch))

    def test_user_tool_rule_denies_matching_command(self):
        self.m["tool_rules"] = [{"tool_regex": "Bash", "command_regex": r"git\s+push",
                                 "decision": "deny", "reason": "Publishing is not authorized"}]
        engine.load_manifest(self.manifest_file())
        with self.assertRaises(engine.Invalid):
            engine.hook_decision(self.root, self.m, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                  "tool_input": {"command": "git push origin main"}})
        engine.hook_decision(self.root, self.m, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                             "tool_input": {"command": "git status"}})

    def test_invalid_rule_is_reported(self):
        self.m["tool_rules"] = [{"tool_regex": "[", "decision": "deny", "reason": "invalid"}]
        with self.assertRaises(engine.Invalid):
            engine.load_manifest(self.manifest_file())

    def test_symlink_cannot_escape_root(self):
        outside = self.base / "outside.txt"
        outside.write_text("data", encoding="utf-8")
        try:
            (self.root / "link.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(engine.Invalid):
            engine.hook_decision(self.root, self.m, self.payload(self.patch("Update", "link.txt")))
        with self.assertRaises(engine.Invalid):
            engine.scan(self.root)

    def test_cli_deny_shape_and_malformed_json(self):
        for payload in (json.dumps(self.payload(self.patch("Update", "extra.txt"))), "not json"):
            result = subprocess.run([sys.executable, str(SCRIPT), "hook", "--root", str(self.root),
                                     "--manifest", str(self.manifest_file())], input=payload,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0)
            response = json.loads(result.stdout)
            self.assertEqual(response["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertNotIn("continue", response)

    def test_cli_snapshot_scope_and_receipt_end_to_end(self):
        manifest = self.manifest_file()
        common = ["--root", str(self.root), "--manifest", str(manifest)]
        baseline, receipt = self.base / "baseline.json", self.base / "receipt.json"
        def call(command, *args):
            proc = subprocess.run([sys.executable, str(SCRIPT), command, *common, *args],
                                  text=True, capture_output=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        call("snapshot", "--output", str(baseline))
        (self.root / "a.txt").write_text("new", encoding="utf-8")
        self.assertTrue(call("scope", "--baseline", str(baseline))["ok"])
        call("run-check", "--check", "targeted", "--lane", "minimal", "--output", str(receipt))
        self.assertNotIn("_diagnostic_output", json.loads(receipt.read_text()))
        self.assertTrue(call("check-receipt", "--check", "targeted", "--lane", "minimal",
                             "--receipt", str(receipt))["ok"])


if __name__ == "__main__":
    unittest.main()
