#!/usr/bin/env python3
"""Pipeline Vacoin pipeline: explicit local checks; no git writes or server execution.

Adapted concepts: Vibe Dev 9.0.4 scope guards, verification receipts, doctor.
Original source and MIT attribution: ../UPSTREAM.md and ../licenses/.
Python 3.10+, standard library only. Does not modify journals or application files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

VERSION = "0.3.0"
# Generated/dependency directories only. Explicit edits here require a different
# reviewed manifest/tool; they cannot be added to the tracked-file allowlist.
EXCLUDED = {".git", "node_modules", ".next", "coverage", "__pycache__"}
KINDS = {"sandbox", "local", "server-files"}
LANES = {"minimal", "final"}
PROTECTED = {"AGENTS.md", "pipeline/GUARDS.md", "pipeline/scripts/pipeline.py",
             "pipeline/templates/codex-hooks.toml", "pipeline/templates/codex-reviewer.toml",
             ".codex/config.toml"}
# Recognisable formats only; values are never included in diagnostics.
SECRET_PATTERNS = {
    "provider-key": re.compile(r"\b(?:sk-proj-|sk-ant-)[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})"),
    "aws-access-id": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
}
REQUIRED_SKILLS = (
    "vacoin-plan", "vacoin-research", "vacoin-review", "vacoin-implement",
    "vacoin-verify", "vacoin-design", "vacoin-bugfix", "vacoin-server-bugfix",
    "vacoin-session", "vacoin-lessons", "vacoin-guards", "vacoin-stuck",
    "vacoin-release", "vacoin-maintain",
)


class Invalid(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as f:
        return json.load(f)


def utc():
    return datetime.now(timezone.utc).isoformat()


def relative_name(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise Invalid("Path must be relative and use forward slashes.")
    p = PurePosixPath(value)
    if p.is_absolute() or ":" in value or "\x00" in value or any(
            part in {"", ".", ".."} for part in value.split("/")):
        raise Invalid(f"Invalid path: {value!r}")
    if any(part in EXCLUDED for part in p.parts):
        raise Invalid(f"File is in an excluded directory: {value}")
    return p.as_posix()


def load_manifest(path):
    m = read_json(path)
    if not isinstance(m, dict) or type(m.get("schema_version")) is not int or m["schema_version"] != 1:
        raise Invalid("Expected manifest schema_version=1.")
    for key in ("task_id", "plan_ref", "authorization_ref"):
        if not isinstance(m.get(key), str) or not m[key].strip():
            raise Invalid(f"Missing required value: {key}.")
    if m.get("root_kind") not in KINDS:
        raise Invalid("root_kind must be sandbox, local, or server-files.")
    files = m.get("files")
    if not isinstance(files, list) or not files:
        raise Invalid("A nonempty exact file list is required.")
    names = set()
    for f in files:
        if not isinstance(f, dict):
            raise Invalid("Each file entry must be an object.")
        name = relative_name(f.get("path"))
        # Reject Windows aliases on all platforms, so one manifest is portable.
        if name.casefold() in names:
            raise Invalid(f"Duplicate or case-ambiguous path: {name}")
        names.add(name.casefold())
        if f.get("change") not in {"create", "modify", "delete"}:
            raise Invalid(f"Unknown operation: {name}")
        if not isinstance(f.get("sections"), str) or not f["sections"].strip():
            raise Invalid(f"Missing exact change sections: {name}")
        if not isinstance(f.get("expected_behavior"), str) or not f["expected_behavior"].strip():
            raise Invalid(f"Missing expected behavior: {name}")
    checks = m.get("checks", [])
    if not isinstance(checks, list):
        raise Invalid("checks must be an array.")
    ids = set()
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str) or not check["id"].strip():
            raise Invalid("Check ID is missing.")
        if check["id"] in ids:
            raise Invalid("Duplicate check ID.")
        ids.add(check["id"])
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(v, str) or not v for v in argv):
            raise Invalid("argv must be a nonempty array of strings; no shell/eval.")
        lanes = check.get("lanes")
        if not isinstance(lanes, list) or not lanes or any(l not in LANES for l in lanes):
            raise Invalid("lanes must be minimal and/or final.")
        timeout = check.get("timeout_seconds", 45)
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise Invalid("timeout_seconds must be an integer from 1 to 600.")
    rules = m.get("tool_rules", [])
    if not isinstance(rules, list):
        raise Invalid("tool_rules must be an array.")
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("decision") not in {"deny", "warn"}:
            raise Invalid("Rule decision must be deny or warn.")
        if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            raise Invalid("A rule must provide a reason.")
        if not isinstance(rule.get("tool_regex"), str) or not rule["tool_regex"]:
            raise Invalid("A rule must match a tool name.")
        for key in ("tool_regex", "command_regex", "path_regex"):
            if key in rule:
                if not isinstance(rule[key], str):
                    raise Invalid("Regular expression must be a string.")
                try:
                    re.compile(rule[key])
                except re.error as exc:
                    raise Invalid(f"Invalid regular expression {key}: {exc}") from exc
    validate_guards(m)
    return m


def validate_guards(m):
    g = m.get("guards", {})
    keys = {"protected_paths", "maintenance_paths", "maintenance_authorization_ref", "research"}
    if not isinstance(g, dict) or set(g) - keys:
        raise Invalid("Unknown guards format.")
    for key in ("protected_paths", "maintenance_paths"):
        values = g.get(key, [])
        if not isinstance(values, list):
            raise Invalid(f"{key} must be an array of exact relative paths.")
        names = [relative_name(v).casefold() for v in values]
        if len(names) != len(set(names)):
            raise Invalid(f"Duplicate path in {key}.")
    protected = {p.casefold() for p in PROTECTED | set(g.get("protected_paths", []))}
    if any(p.casefold() not in protected for p in g.get("maintenance_paths", [])):
        raise Invalid("maintenance_paths must be protected paths.")
    ref = g.get("maintenance_authorization_ref", "")
    if not isinstance(ref, str) or bool(ref.strip()) != bool(g.get("maintenance_paths")):
        raise Invalid("Maintenance requires exact maintenance_paths and a user authorization reference.")
    research = g.get("research")
    if research is not None:
        if not isinstance(research, dict) or set(research) - {"targets", "record", "skip_authorization_ref"}:
            raise Invalid("Unknown guards format.research.")
        targets = research.get("targets")
        if not isinstance(targets, list) or not targets:
            raise Invalid("research.targets must be a nonempty list of architecture files.")
        names = [relative_name(v).casefold() for v in targets]
        if len(names) != len(set(names)):
            raise Invalid("Duplicate architecture path.")
        relative_name(research.get("record"))
        skip = research.get("skip_authorization_ref", "")
        if not isinstance(skip, str):
            raise Invalid("Skipping research requires explicit user authorization reference.")


def secret_categories(text):
    return sorted(name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text))


def check_research(root, m):
    r = m.get("guards", {}).get("research")
    if r is None:
        return {"configured": False}
    if r.get("skip_authorization_ref", "").strip():
        return {"configured": True, "skipped": True,
                "limitation": "The agent must verify that the user actually authorized skipping research."}
    record = read_json(resolve_file(root, r["record"]))
    if not isinstance(record, dict) or record.get("task_id") != m["task_id"] or record.get("plan_ref") != m["plan_ref"]:
        raise Invalid("Research belongs to a different task or plan version.")
    report = resolve_file(root, record.get("report_path"))
    if not report.is_file() or not report.read_text(encoding="utf-8").strip():
        raise Invalid("Research report is missing or empty.")
    if record.get("report_sha256") != file_hash(report):
        raise Invalid("Research report changed; evidence must be reconciled.")
    return {"configured": True, "skipped": False,
            "limitation": "A report's existence and version do not prove research quality or tool access."}


def guard_patch(root, m, paths, patch):
    validate_guards(m)
    g = m.get("guards", {})
    protected = {resolve_file(root, p).resolve().relative_to(root).as_posix().casefold()
                 for p in PROTECTED | set(g.get("protected_paths", []))}
    maintained = {resolve_file(root, p).resolve().relative_to(root).as_posix().casefold()
                  for p in g.get("maintenance_paths", [])}
    for path in paths:
        if path.casefold() in protected and path.casefold() not in maintained:
            raise Invalid(f"A protected file requires separately authorized maintenance: {path}")
    inserted = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+"))
    categories = secret_categories(inserted)
    if categories:
        raise Invalid("Potential credential pattern detected in added text: " + ", ".join(categories) +
                      ". Value redacted; use an environment variable instead of a literal.")
    research = g.get("research")
    if research and {p.casefold() for p in paths} & {p.casefold() for p in research["targets"]}:
        check_research(root, m)


def scan_secrets(root, m):
    validate_root(root, m)
    findings = []
    for item in m["files"]:
        p = resolve_file(root, item["path"])
        if not p.is_file():
            continue
        for number, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for category in secret_categories(line):
                findings.append({"path": item["path"], "line": number, "category": category})
    return {"ok": not findings, "findings": findings,
            "limitation": "Only existing manifest-scoped files are checked, not Git history or every secret format."}


def resume_check(root, m, session_id, baseline=None):
    index = read_json(root / "pipeline/sessions/index.json")
    if not isinstance(index, dict) or not isinstance(index.get("sessions"), list):
        raise Invalid("Invalid session index.")
    cards = [c for c in index["sessions"] if isinstance(c, dict) and c.get("id") == session_id]
    if len(cards) != 1:
        raise Invalid("Selected session is missing or its ID is duplicated.")
    card = cards[0]
    if card.get("task_id") != m["task_id"] or card.get("status") not in {"open", "active", "completed"}:
        raise Invalid("Session index record does not match the task or status.")
    state = resolve_file(root / "pipeline/sessions", card.get("state_file"))
    if not inside(state.resolve(), root):
        raise Invalid("Session is outside the project.")
    text = state.read_text(encoding="utf-8")
    task = re.search(r"(?m)^-\s*task_id:\s*([^\s.;]+)", text)
    sid = re.search(r"(?m)^-\s*session_id:\s*([^\s.;]+)", text)
    status = re.search(r"(?m)^-\s*Session status:\s*(open|active|completed)\b", text)
    ref = re.search(r"(?m)^-\s*task_ref:\s*\[[^\]]+\]\(([^)]+)\)", text)
    issues = []
    if not task or task[1] != card["task_id"] or not sid or sid[1] != session_id:
        issues.append("SESSION IDs do not match the index.")
    if not status or status[1] != card["status"]:
        issues.append("SESSION status does not match the index.")
    files = [state, state.parent / "HISTORY.md"]
    if ref:
        if ":" in ref[1] or "\\" in ref[1]:
            raise Invalid("task_ref must be a local relative link; verify external sources separately.")
        target = (state.parent / ref[1]).resolve()
        if not inside(target, root):
            raise Invalid("task_ref escapes the project; verify external references separately.")
        files.append(target)
    else:
        issues.append("task_ref in the required format is missing.")
    versions = []
    for p in files:
        if not inside(p.resolve(), root):
            raise Invalid("Recovery file escapes project root.")
        if not p.is_file():
            issues.append("Linked document is missing: " + p.relative_to(root).as_posix())
        else:
            versions.append({"path": p.relative_to(root).as_posix(), "sha256": file_hash(p)})
    scope = check_scope(root, m, baseline) if baseline is not None else None
    if scope is not None and not scope["ok"]:
        issues.append("Changes outside the approved file list were detected.")
    return {"ok": not issues, "session_id": session_id, "task_id": m["task_id"],
            "issues": issues, "versions": versions, "scope": scope,
            "user_acceptance": "not_verified", "automatic_retry": False,
            "limitation": "Reference checks do not prove that an interrupted action completed or that code and external effects are correct."}


def root_path(value):
    root = Path(value).resolve(strict=True)
    if not root.is_dir():
        raise Invalid("Root must be an existing directory.")
    return root


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_file(root, name):
    path = root / relative_name(name)
    if not inside(path.resolve(), root):
        raise Invalid(f"Path or link escapes root: {name}")
    return path


def validate_root(root, m):
    for f in m["files"]:
        resolve_file(root, f["path"])


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root):
    files = {}
    def on_error(exc):
        raise exc
    for current, dirs, names in os.walk(root, followlinks=False, onerror=on_error):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        # Never hide a symlinked source directory from scope/fingerprint checks.
        for d in dirs:
            p = Path(current) / d
            if p.is_symlink():
                raise Invalid(f"Directory symlink requires separate verification: {p}")
        for name in sorted(names):
            p = Path(current) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                if not inside(p.resolve(), root) or not p.resolve().is_file():
                    raise Invalid(f"Unverified external or dangling symlink: {rel}")
                files[rel] = {"sha256": file_hash(p), "link": os.readlink(p)}
            elif p.is_file():
                files[rel] = {"sha256": file_hash(p)}
            else:
                raise Invalid(f"Unsupported file type: {rel}")
    return files


def fingerprint(root, m, files=None):
    return digest({"root": str(root), "manifest": digest(m),
                   "files": scan(root) if files is None else files})


def write_artifact(path, root, value):
    # Keeping evidence outside the root avoids evidence changing its own hash.
    p = Path(path).resolve()
    if inside(p, root):
        raise Invalid("Store verification output outside the checked root.")
    if p.exists():
        raise Invalid("Output already exists; use a new path.")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def snapshot(root, m):
    validate_root(root, m)
    files = scan(root)
    for f in m["files"]:
        exists = f["path"] in files
        if exists != (f["change"] != "create"):
            raise Invalid(f"Baseline state does not match requested operation: {f['path']}")
    return {"schema_version": 1, "kind": "scope-baseline", "task_id": m["task_id"],
            "root": str(root), "manifest_sha256": digest(m), "created_at": utc(), "files": files}


def check_scope(root, m, baseline):
    validate_root(root, m)
    if (not isinstance(baseline, dict) or baseline.get("schema_version") != 1 or baseline.get("kind") != "scope-baseline"
            or baseline.get("task_id") != m["task_id"] or baseline.get("root") != str(root)
            or baseline.get("manifest_sha256") != digest(m) or not isinstance(baseline.get("files"), dict)):
        raise Invalid("Snapshot belongs to another task, root or plan version.")
    old, new = baseline["files"], scan(root)
    allowed = {f["path"]: f["change"] for f in m["files"]}
    changes, violations = [], []
    for path in sorted(old.keys() | new.keys()):
        if old.get(path) == new.get(path):
            continue
        change = "create" if path not in old else "delete" if path not in new else "modify"
        item = {"path": path, "change": change}
        changes.append(item)
        if allowed.get(path) != change:
            violations.append(item)
    return {"ok": not violations, "changed": changes, "out_of_scope": violations,
            "limitation": "A reviewer must verify which sections of an allowed file changed."}


def selected_check(m, check_id, lane):
    for c in m.get("checks", []):
        if c["id"] == check_id:
            if lane not in c["lanes"]:
                raise Invalid("Check is not authorized in the selected lane.")
            return c
    raise Invalid("Check is missing from the plan.")


def run_check(root, m, check_id, lane):
    if m["root_kind"] == "server-files":
        raise Invalid("Server commands must be run by the operator; run-check is disabled here.")
    validate_root(root, m)
    c = selected_check(m, check_id, lane)
    before = fingerprint(root, m)
    started = utc()
    tick = time.monotonic()
    timed_out = False
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen(c["argv"], cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                shell=False, start_new_session=(os.name != "nt"))
        try:
            proc.wait(timeout=c.get("timeout_seconds", 45))
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                proc.kill()
            proc.wait()
        output.seek(0)
        h, size = hashlib.sha256(), 0
        for chunk in iter(lambda: output.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
        output.seek(0)
        head = output.read(2048)
        if size > 4096:
            output.seek(-2048, os.SEEK_END)
            excerpt = head + b"\n...\n" + output.read(2048)
        else:
            output.seek(0)
            excerpt = output.read(4096)
    after = fingerprint(root, m)
    passed = proc.returncode == 0 and not timed_out and before == after
    return {"schema_version": 1, "kind": "verification-receipt", "engine_version": VERSION,
            "task_id": m["task_id"], "root": str(root), "manifest_sha256": digest(m),
            "check_id": check_id, "lane": lane, "argv": c["argv"], "started_at": started,
            "finished_at": utc(), "duration_seconds": round(time.monotonic() - tick, 3),
            "exit_code": proc.returncode, "timed_out": timed_out,
            "input_before": before, "input_after": after,
            "output_sha256": h.hexdigest(), "output_bytes": size,
            "verdict": "passed" if passed else "failed",
            "source": "agent-local-run", "user_acceptance": "not_recorded",
            "_diagnostic_output": excerpt.decode("utf-8", errors="replace") if not passed else ""}


def check_receipt(root, m, receipt, check_id, lane):
    validate_root(root, m)
    c = selected_check(m, check_id, lane)
    expected = {"schema_version": 1, "kind": "verification-receipt", "task_id": m["task_id"],
                "root": str(root), "manifest_sha256": digest(m), "check_id": check_id,
                "lane": lane, "argv": c["argv"], "verdict": "passed", "timed_out": False,
                "source": "agent-local-run"}
    if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected.items()):
        raise Invalid("Invalid, failed or unrelated verification receipt.")
    if type(receipt.get("exit_code")) is not int or receipt["exit_code"] != 0:
        raise Invalid("Check did not finish successfully.")
    current = fingerprint(root, m)
    if receipt.get("input_before") != current or receipt.get("input_after") != current:
        raise Invalid("Receipt is stale or source changed during the check.")
    return {"ok": True, "check_id": check_id, "user_acceptance": "not_verified"}


def patch_changes(text):
    if not isinstance(text, str) or not text.startswith("*** Begin Patch\n") or not text.rstrip().endswith("*** End Patch"):
        raise Invalid("Could not parse apply_patch; verify the tool payload format.")
    changes = []
    for line in text.splitlines():
        for prefix, action in (("*** Add File: ", "create"), ("*** Update File: ", "modify"),
                               ("*** Delete File: ", "delete")):
            if line.startswith(prefix):
                changes.append([line[len(prefix):], action])
                break
        if line.startswith("*** Move to: "):
            if not changes or changes[-1][1] != "modify":
                raise Invalid("Ambiguous file move.")
            changes[-1][1] = "delete"
            changes.append([line[len("*** Move to: "):], "create"])
    if not changes:
        raise Invalid("No recognized file paths in patch.")
    return changes


def hook_decision(root, m, payload):
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "PreToolUse":
        raise Invalid("Expected PreToolUse JSON.")
    validate_root(root, m)
    tool, inp = payload.get("tool_name"), payload.get("tool_input")
    if not isinstance(tool, str) or not tool:
        raise Invalid("Tool name missing from event.")
    command = inp.get("command", inp.get("patch", "")) if isinstance(inp, dict) else inp
    command = command if isinstance(command, str) else ""
    paths = []
    if tool == "apply_patch":
        paths = [name for name, _ in patch_changes(command)]
    elif isinstance(inp, dict):
        candidate = inp.get("file_path", inp.get("path"))
        if isinstance(candidate, str):
            paths = [candidate]
    warnings = []
    for rule in m.get("tool_rules", []):
        if not re.fullmatch(rule["tool_regex"], tool):
            continue
        if "command_regex" in rule and not re.search(rule["command_regex"], command):
            continue
        if "path_regex" in rule and not any(re.search(rule["path_regex"], p) for p in paths):
            continue
        if rule["decision"] == "deny":
            raise Invalid(rule["reason"])
        warnings.append(rule["reason"])
    warning = " ".join(warnings)
    if tool == "Bash":
        if m["root_kind"] == "server-files":
            raise Invalid("Server-side Linux commands require operator execution.")
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                "Hook does not validate arbitrary shell commands. Follow the approved plan; "
                "check scope after the command. Server commands require operator approval. " + warning}}
    if tool != "apply_patch":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                "Automatic path checks are not implemented for this tool. "
                "Review exact file paths and run scope after changes. " + warning}}
    changes = patch_changes(command)
    cwd = Path(payload.get("cwd", str(root))).resolve()
    allowed = {f["path"]: f["change"] for f in m["files"]}
    relative_paths = []
    for name, action in changes:
        p = Path(name)
        p = p if p.is_absolute() else cwd / p
        p = p.resolve()
        if not inside(p, root):
            raise Invalid(f"Edit outside checked root: {name}")
        rel = p.relative_to(root).as_posix()
        relative_name(rel)
        # Later edits to a file created in this batch are still in scope.
        accepted = allowed.get(rel) == action or (allowed.get(rel) == "create" and action == "modify")
        if not accepted:
            raise Invalid(f"Edit outside approved plan: {rel} ({action})")
        relative_paths.append(rel)
    guard_patch(root, m, relative_paths, command)
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
            "apply_patch paths match the approved file list; code sections still require review. " + warning}}


def doctor(root):
    base = root / "pipeline"
    required = [root / "AGENTS.md", base / "README.md", base / "COMMANDS.md",
                base / "GUARDS.md", base / "SKILLS.md", base / "journals/ERRORS.md",
                base / "scripts/pipeline.py"]
    for name in REQUIRED_SKILLS:
        required.extend([base / "skills" / name / "SKILL.md",
                         base / "skills" / name / "agents/openai.yaml"])
    missing = [str(p.relative_to(root)) for p in required if not p.is_file()]
    skills = sorted(p.parent.name for p in (base / "skills").glob("*/SKILL.md"))
    return {"ok": not missing, "engine_version": VERSION, "python": sys.version.split()[0],
            "missing": missing, "repository_skills": skills,
            "hook_activation": "not_confirmed", "journal_automation": "disabled",
            "note": "Files alone do not prove that Codex skills are loaded or hooks are active."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "snapshot", "scope", "run-check", "check-receipt", "hook", "doctor", "secrets", "resume-check"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True)
        if name != "doctor":
            p.add_argument("--manifest", required=True)
        if name in {"snapshot", "run-check"}:
            p.add_argument("--output", required=True)
        if name == "scope":
            p.add_argument("--baseline", required=True)
        if name in {"run-check", "check-receipt"}:
            p.add_argument("--check", required=True)
            p.add_argument("--lane", choices=sorted(LANES), required=True)
        if name == "check-receipt":
            p.add_argument("--receipt", required=True)
        if name == "resume-check":
            p.add_argument("--session", required=True)
            p.add_argument("--baseline")
    args = parser.parse_args(argv)
    try:
        root = root_path(args.root)
        m = load_manifest(args.manifest) if args.command != "doctor" else None
        if args.command == "validate":
            validate_root(root, m)
            result = {"ok": True, "task_id": m["task_id"]}
        elif args.command == "snapshot":
            result = snapshot(root, m)
            write_artifact(args.output, root, result)
            result = {"ok": True, "output": str(Path(args.output).resolve()), "files": len(result["files"])}
        elif args.command == "scope":
            result = check_scope(root, m, read_json(args.baseline))
        elif args.command == "run-check":
            # Validate output before executing a potentially expensive command.
            dest = Path(args.output).resolve()
            if inside(dest, root) or dest.exists():
                raise Invalid("A new output file outside the checked root is required.")
            result = run_check(root, m, args.check, args.lane)
            diagnostic = result.pop("_diagnostic_output")
            write_artifact(dest, root, result)
            result = {"ok": result["verdict"] == "passed", "output": str(dest),
                      "exit_code": result["exit_code"], "timed_out": result["timed_out"],
                      "diagnostic_output": diagnostic}
        elif args.command == "check-receipt":
            result = check_receipt(root, m, read_json(args.receipt), args.check, args.lane)
        elif args.command == "secrets":
            result = scan_secrets(root, m)
        elif args.command == "resume-check":
            result = resume_check(root, m, args.session, read_json(args.baseline) if args.baseline else None)
        elif args.command == "hook":
            result = hook_decision(root, m, json.load(sys.stdin))
        else:
            result = doctor(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        if args.command == "hook":
            # Correct Codex block shape, rather than unsupported continue:false.
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                    "permissionDecision": "deny", "permissionDecisionReason": str(exc)}}, ensure_ascii=False))
            return 0
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
