#!/usr/bin/env python3
"""Run a single explicit Codex probe in a detached Git worktree.

No automatic candidate promotion or project-to-project exchange. This is a
local opt-in pilot runner, not a hardened VM/container boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

# Import frozen-plan validation from the existing improvement lab.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab

def invoke(argv: list[str], *, cwd: Path, timeout: int, stdin: str | None = None):
    return subprocess.run(argv, cwd=cwd, text=True, input=stdin,
                          capture_output=True, timeout=timeout, check=False)

def git(root: Path, *args: str):
    result = invoke(["git", *args], cwd=root, timeout=30)
    if result.returncode:
        raise lab.Invalid("Git command failed: " + " ".join(args[:3]))
    return result.stdout.strip()

def start(plan: dict, root: Path, out: Path, candidate_id: str,
          prompt: str, *, timeout: int, execute: bool):
    lab.validate_plan(plan, root)
    if not inside_external(out, root):
        raise lab.Invalid("Worktree and evidence output must be outside the main checkout")
    candidates = {x["id"]: x for x in plan["candidates"]}
    if candidate_id not in candidates:
        raise lab.Invalid("Unknown candidate")
    if plan["mode"] == "sequential" and candidate_id != plan["candidates"][0]["id"]:
        raise lab.Invalid("Sequential descendants require independently gated manual baselines")
    if not isinstance(prompt, str) or not prompt.strip():
        raise lab.Invalid("Prompt cannot be empty")
    if lab.SECRET_RE.search(prompt):
        raise lab.Invalid("Potential credential in prompt")
    if len(prompt) > 20000:
        raise lab.Invalid("Prompt too long")
    if out.exists():
        raise lab.Invalid("Experiment output exists; refusing overwrite")
    if not git(root, "status", "--porcelain", "--untracked-files=normal") == "":
        raise lab.Invalid("Main checkout has uncommitted changes; pilot requires clean checkout")
    baseline = git(root, "rev-parse", "HEAD")
    declared_ref = plan["baseline_ref"]
    if declared_ref not in (baseline, "git:" + baseline):
        raise lab.Invalid("Plan baseline_ref must equal current full commit SHA")
    if not execute:
        return {"dry_run": True, "baseline": baseline, "candidate_id": candidate_id,
                "worktree": str(out / "worktree"), "sandbox": "workspace-write"}
    if shutil.which("codex") is None:
        raise lab.Invalid("Codex CLI is not in PATH")
    if shutil.which("git") is None:
        raise lab.Invalid("Git executable is unavailable")

    out.mkdir(parents=True)
    workspace = out / "worktree"
    evidence = out / "evidence"
    evidence.mkdir()
    added = False
    result = None
    failure = None
    try:
        git(root, "worktree", "add", "--detach", str(workspace), baseline)
        added = True
        required_paths = [e["path"] for e in candidates[candidate_id]["edits"]]
        safe_prompt = (
            "Isolated experiment for the host project. Obey AGENTS.md and the existing "
            "pipeline rules. Do not access or change production systems, databases, "
            "the remote GitHub repository, external projects or secrets. Do not run "
            "git push, publish, deploy or migrate. Modify ONLY these paths: "
            + json.dumps(required_paths, ensure_ascii=False)
            + ". The task is to improve agent guidance, NOT application logic. "
            "Respond with changed files and observed limitations.\n\n"
            + prompt
        )
        result = invoke(
            ["codex", "exec", "--sandbox", "workspace-write",
             "--json", "--output-last-message", str(evidence / "last-message.txt"), "-"],
            cwd=workspace, stdin=safe_prompt, timeout=timeout
        )
        # Store output locally only. It can include sensitive tool output and
        # therefore must NEVER be committed as part of the repository.
        (evidence / "codex-stdout.jsonl").write_text(result.stdout, encoding="utf-8")
        (evidence / "codex-stderr.txt").write_text(result.stderr, encoding="utf-8")
        status = invoke(["git", "status", "--porcelain", "--untracked-files=all"],
                        cwd=workspace, timeout=30)
        (evidence / "git-status.txt").write_text(status.stdout, encoding="utf-8")
        changed = invoke(["git", "diff", "--name-only", "HEAD", "--"],
                         cwd=workspace, timeout=30)
        listed = set(x for x in changed.stdout.splitlines() if x)
        untracked = invoke(["git", "ls-files", "--others", "--exclude-standard"],
                           cwd=workspace, timeout=30)
        listed.update(x for x in untracked.stdout.splitlines() if x)
        expected = set(required_paths)
        out_of_scope = sorted(listed - expected)
        data = {
            "schema_version": 1, "project": "vacoin-global",
            "task_id": plan["task_id"], "candidate_id": candidate_id,
            "plan_sha256": lab.sha(plan), "baseline_commit": baseline,
            "isolated_workspace": str(workspace), "run_id": out.name,
            "started_by_explicit_operator": True,
            "execution_exit_code": result.returncode,
            "changed_paths": sorted(listed), "out_of_scope_paths": out_of_scope,
            "status": "incomplete",
            "checks": {c["id"]: None for c in plan["checks"]},
            "note": "Runner collects facts only. Independent checks/evaluator still required.",
            "captured_utc": datetime.now(timezone.utc).isoformat()
        }
        (evidence / "probe.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"dry_run": False, "probe": str(evidence / "probe.json"),
                "exit_code": result.returncode, "out_of_scope": out_of_scope,
                "status": "incomplete"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        failure = type(exc).__name__
        (evidence / "runner-error.txt").write_text(failure, encoding="utf-8")
        return {"dry_run": False, "status": "incomplete", "error": failure}
    finally:
        # Preserve worktree for independent review. Operator may manually remove it
        # AFTER collecting evidence using git worktree remove <path>.
        if not added and workspace.exists():
            raise lab.Invalid("Untracked worktree directory created unexpectedly")

def inside_external(path: Path, root: Path) -> bool:
    p = path.resolve()
    r = root.resolve()
    return not (p == r or p.is_relative_to(r)) and not r.is_relative_to(p)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--execute", action="store_true", help="Explicitly run codex")
    a = parser.parse_args()
    try:
        if not 30 <= a.timeout <= 3600:
            raise lab.Invalid("Timeout must be between 30 and 3600 seconds")
        print(json.dumps(start(lab.read(a.plan), a.root.resolve(strict=True),
                               a.out.resolve(), a.candidate,
                               a.prompt_file.read_text(encoding="utf-8"),
                               timeout=a.timeout, execute=a.execute),
                         ensure_ascii=False, indent=2))
    except (lab.Invalid, OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
