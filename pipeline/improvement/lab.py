#!/usr/bin/env python3
"""Pipeline Vacoin improvement laboratory. Standard library only; no project writes.

Evidence-driven Propose–Probe–Compose, parallel/sequential plans, experience
library and harness validation. NOT a self-modifying agent or Codex executor.
All outputs must live in an experiment directory outside project root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
LEVER_NAMES = {"prompt", "skill", "tool-guidance", "subagent", "script", "plugin"}
MODES = {"parallel", "sequential"}
PROTECTED = {
    "AGENTS.md", "pipeline/GUARDS.md", "pipeline/scripts/pipeline.py",
    "pipeline/templates/codex-hooks.toml",
    "pipeline/templates/codex-reviewer.toml", ".codex/config.toml",
}
ALLOWED_PREFIXES = ("pipeline/skills/", "pipeline/requests/", "pipeline/templates/")
SECRET_RE = re.compile(
    r"(?i)(?:sk-proj-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{36,}|"
    r"github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class Invalid(ValueError):
    pass


def relative(path: str) -> str:
    if not isinstance(path, str) or not path or "\\" in path:
        raise Invalid("Relative POSIX path required")
    parts = path.split("/")
    if path.startswith("/") or ":" in path or any(p in ("", ".", "..") for p in parts):
        raise Invalid("Unsafe path")
    return path


def inside(path: Path, parent: Path) -> bool:
    return path.resolve().is_relative_to(parent.resolve())


def canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(obj: object) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Invalid("Expected JSON object")
    return data


def write_new(path: Path, obj: dict, root: Path) -> None:
    # Never allow generated reports or library entries inside the application checkout.
    if inside(path, root):
        raise Invalid("Experiment output must be outside the repository root")
    if path.is_symlink() or path.exists():
        raise Invalid("Output exists: refusing overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_plan(plan: dict, root: Path) -> dict:
    if plan.get("schema_version") != SCHEMA or plan.get("project") != "vacoin-global":
        raise Invalid("Unexpected schema or project: cross-project import is forbidden")
    if plan.get("mode") not in MODES:
        raise Invalid("Unknown recursion mode")
    if not isinstance(plan.get("task_id"), str) or not plan["task_id"].strip():
        raise Invalid("task_id required")
    if not isinstance(plan.get("authorization_ref"), str) or not plan["authorization_ref"].strip():
        raise Invalid("User authorization reference required")
    if not isinstance(plan.get("baseline_ref"), str) or not plan["baseline_ref"].strip():
        raise Invalid("Frozen baseline reference required")
    if plan.get("auto_promote", False) is not False or plan.get("cross_project_sync", False) is not False:
        raise Invalid("Automatic promotion and cross-project sync are forbidden")
    candidates = plan.get("candidates")
    if not isinstance(candidates, list) or not (1 <= len(candidates) <= 6):
        raise Invalid("1..6 candidates required")
    ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise Invalid("Candidate must be an object")
        ident = candidate.get("id")
        if not isinstance(ident, str) or not re.fullmatch("[a-z0-9_-]{1,48}", ident) or ident in ids:
            raise Invalid("Invalid or duplicate candidate ID")
        ids.add(ident)
        if candidate.get("lever") not in LEVER_NAMES:
            raise Invalid("Unsupported change lever")
        edits = candidate.get("edits")
        if not isinstance(edits, list) or not edits:
            raise Invalid("Candidate has no edits")
        changed = set()
        for edit in edits:
            if not isinstance(edit, dict):
                raise Invalid("Edit must be an object")
            name = relative(edit.get("path"))
            if name in changed or name in PROTECTED or not name.startswith(ALLOWED_PREFIXES):
                raise Invalid("Duplicate, protected or out-of-scope edit: " + name)
            changed.add(name)
            if edit.get("operation") not in ("modify", "create"):
                raise Invalid("Only create/modify allowed")
            if not isinstance(edit.get("reason"), str) or not edit["reason"].strip():
                raise Invalid("Each edit requires a reason")
            if edit.get("operation") == "modify" and not (root / name).is_file():
                raise Invalid("Missing baseline file: " + name)
            if edit.get("operation") == "create" and (root / name).exists():
                raise Invalid("Create target already exists: " + name)
        if not isinstance(candidate.get("hypothesis"), str) or not candidate["hypothesis"].strip():
            raise Invalid("Candidate hypothesis required")
    checks = plan.get("checks")
    if not isinstance(checks, list) or len(checks) < 2:
        raise Invalid("At least 2 frozen independent checks required")
    checkids = set()
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            raise Invalid("Invalid check")
        cid = check["id"]
        if not re.fullmatch("[a-z0-9_-]{1,48}", cid) or cid in checkids:
            raise Invalid("Invalid/duplicate check")
        checkids.add(cid)
        if check.get("kind") not in ("functional", "regression", "security", "scope", "architecture"):
            raise Invalid("Unknown check kind")
        if not check.get("independent", False) is True:
            raise Invalid("All checks must be independent of candidate authors")
    if not any(x["kind"] == "regression" for x in checks):
        raise Invalid("Regression check required")
    serialized = canon(plan)
    if SECRET_RE.search(serialized):
        raise Invalid("Potential secret detected")
    return {"plan_sha256": sha(plan), "candidate_ids": sorted(ids), "check_ids": sorted(checkids)}


def validate_evidence(plan: dict, item: dict) -> None:
    if item.get("schema_version") != SCHEMA or item.get("project") != "vacoin-global":
        raise Invalid("Evidence project/schema mismatch")
    if item.get("task_id") != plan["task_id"] or item.get("plan_sha256") != sha(plan):
        raise Invalid("Evidence is not bound to the frozen plan")
    known = {c["id"] for c in plan["candidates"]} | {"baseline"}
    if item.get("candidate_id") not in known:
        raise Invalid("Evidence refers to unknown candidate")
    if not isinstance(item.get("isolated_workspace"), str) or not item["isolated_workspace"].strip():
        raise Invalid("Isolated workspace reference required")
    if not isinstance(item.get("run_id"), str) or not item["run_id"].strip():
        raise Invalid("Run ID required")
    if not isinstance(item.get("evaluator_ref"), str) or not item["evaluator_ref"].strip():
        raise Invalid("Independent evaluator reference required")
    if item.get("status") not in ("passed", "failed", "incomplete"):
        raise Invalid("Invalid status")
    results = item.get("checks")
    expected = {c["id"] for c in plan["checks"]}
    if not isinstance(results, dict) or set(results) != expected:
        raise Invalid("Every frozen check must be recorded")
    if any(v not in (True, False, None) for v in results.values()):
        raise Invalid("Checks must be true/false/null")
    if SECRET_RE.search(canon(item)):
        raise Invalid("Potential secret detected")



def schedule(plan: dict) -> dict:
    """Explicit, non-executing task-level recursion schedule.

    Parallel candidates are independent from the frozen baseline.
    Sequential candidates are ordered and each must inherit only the preceding
    validated candidate, never a silently modified live project.
    """
    ids = [c["id"] for c in plan["candidates"]]
    if plan["mode"] == "parallel":
        stages = [{"candidate_id": cid, "depends_on": "baseline",
                   "workspace": "new_isolated_worktree", "execution": "manual"} for cid in ids]
    else:
        previous = "baseline"
        stages = []
        for cid in ids:
            stages.append({"candidate_id": cid, "depends_on": previous,
                           "workspace": "new_isolated_worktree", "execution": "manual",
                           "gate": "previous_evidence_complete_and_validated"})
            previous = cid
    return {"schema_version": SCHEMA, "project": "vacoin-global",
            "task_id": plan["task_id"], "mode": plan["mode"], "plan_sha256": sha(plan),
            "baseline": {"id": "baseline", "frozen_ref": plan["baseline_ref"]},
            "stages": stages, "automatic_execution": False,
            "cross_project_sync": False}


def compose(plan: dict, evidence: list[dict]) -> dict:
    by_id = {}
    for item in evidence:
        validate_evidence(plan, item)
        cid = item["candidate_id"]
        if cid in by_id:
            raise Invalid("Duplicate candidate evidence (one frozen run per candidate)")
        by_id[cid] = item
    wanted = {c["id"] for c in plan["candidates"]} | {"baseline"}
    if set(by_id) != wanted:
        raise Invalid("Missing baseline or candidate evidence")
    mandatory = [c["id"] for c in plan["checks"]]
    passed = lambda e: e["status"] == "passed" and all(e["checks"][k] is True for k in mandatory)
    baseline_ok = passed(by_id["baseline"])
    scored = []
    for c in plan["candidates"]:
        row = by_id[c["id"]]
        scored.append({"candidate_id": c["id"], "eligible": passed(row),
                       "passed_checks": sum(v is True for v in row["checks"].values()),
                       "run_id": row["run_id"]})
    eligible = [x["candidate_id"] for x in scored if x["eligible"]]
    # No ranking from fabricated or mutable scores. The reviewer must choose among
    # independently passing candidates. Never auto-merge or silently weaken checks.
    return {"schema_version": SCHEMA, "project": "vacoin-global",
            "task_id": plan["task_id"], "plan_sha256": sha(plan),
            "baseline_passed": baseline_ok, "candidates": scored,
            "eligible_for_human_review": eligible, "accepted": None,
            "promotion": "manual_only", "cross_project_sync": False,
            "note": "Requires independent review, user approval and separate PR. No automatic compose/promotion."}


def experience(plan: dict, report: dict, selection: dict) -> dict:
    if report.get("plan_sha256") != sha(plan) or report.get("promotion") != "manual_only":
        raise Invalid("Mismatched report")
    candidate = selection.get("candidate_id")
    if candidate not in report["eligible_for_human_review"]:
        raise Invalid("Cannot adopt unqualified candidate")
    if not all(isinstance(selection.get(x), str) and selection[x].strip()
               for x in ("approval_ref", "evidence_ref", "lesson", "limitations")):
        raise Invalid("Manual approval, evidence, lesson and limitations required")
    if SECRET_RE.search(canon(selection)):
        raise Invalid("Potential secret detected")
    chosen = next(c for c in plan["candidates"] if c["id"] == candidate)
    return {"schema_version": SCHEMA, "project": "vacoin-global",
            "task_id": plan["task_id"], "candidate_id": candidate,
            "approval_ref": selection["approval_ref"], "evidence_ref": selection["evidence_ref"],
            "plan_sha256": sha(plan), "hypothesis": chosen["hypothesis"],
            "lesson": selection["lesson"], "limitations": selection["limitations"],
            "scope": [e["path"] for e in chosen["edits"]],
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "cross_project_sync": False,
            "note": "For Pipeline Vacoin only. Manual export/review required for other projects."}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="Existing checkout (read-only)")
    sub = ap.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--plan", type=Path, required=True)
    p = sub.add_parser("schedule")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    c = sub.add_parser("compose")
    c.add_argument("--plan", type=Path, required=True)
    c.add_argument("--evidence", type=Path, nargs="+", required=True)
    c.add_argument("--output", type=Path, required=True)
    e = sub.add_parser("record")
    e.add_argument("--plan", type=Path, required=True)
    e.add_argument("--report", type=Path, required=True)
    e.add_argument("--selection", type=Path, required=True)
    e.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        root = args.root.resolve(strict=True)
        plan = read(args.plan)
        validated = validate_plan(plan, root)
        if args.command == "validate":
            print(canon(validated))
        elif args.command == "schedule":
            result = schedule(plan)
            write_new(args.output, result, root)
            print(canon({"output": str(args.output), "stages": len(result["stages"])}))
        elif args.command == "compose":
            result = compose(plan, [read(p) for p in args.evidence])
            write_new(args.output, result, root)
            print(canon({"output": str(args.output), "eligible": result["eligible_for_human_review"]}))
        else:
            record = experience(plan, read(args.report), read(args.selection))
            write_new(args.output, record, root)
            print(canon({"output": str(args.output), "task_id": record["task_id"]}))
        return 0
    except (Invalid, OSError, ValueError) as exc:
        print("ERROR: " + str(exc), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
