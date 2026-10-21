#!/usr/bin/env python3
"""Install Pipeline Vacoin into an existing local project (dry run by default)."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parents[1]
SKILLS = SOURCE / "pipeline" / "skills"

def run(target: Path, apply: bool):
    target = target.expanduser().resolve()
    if not target.is_dir():
        raise ValueError("Target project must already exist.")
    if target == SOURCE or target.is_relative_to(SOURCE) or SOURCE.is_relative_to(target):
        raise ValueError("Target must be separate from the distribution repository.")
    if target.is_symlink():
        raise ValueError("Symlink targets are not supported.")
    if not (target / ".git").exists():
        raise ValueError("Target must be a Git worktree/repository.")
    names = sorted(p for p in SKILLS.iterdir() if p.is_dir() and p.name.startswith("vacoin-"))
    if len(names) != 14:
        raise ValueError("Expected exactly 14 project-local skills.")
    # Fail closed: the installer never merges, replaces or deletes existing files.
    destinations = [(SOURCE / "pipeline", target / "pipeline")]
    destinations += [(p, target / ".agents" / "skills" / p.name) for p in names]
    destinations += [(SOURCE / "AGENTS.md", target / "AGENTS.md")] if not (target / "AGENTS.md").exists() else []
    conflicts = [str(dst) for _, dst in destinations if dst.exists() or dst.is_symlink()]
    if (target / "pipeline").exists() and (target / "pipeline").is_symlink():
        conflicts.append(str(target / "pipeline"))
    if (target / ".agents").is_symlink() or (target / ".agents" / "skills").is_symlink():
        raise ValueError("Symlinked project skill directories are not supported.")
    if conflicts:
        raise ValueError("Existing destinations must be reviewed and merged manually: " + ", ".join(conflicts))
    print("Pipeline Vacoin installation plan:")
    for _, dst in destinations:
        print("  +", dst)
    if (target / "AGENTS.md").exists():
        print("Existing AGENTS.md will NOT be changed. Merge instructions manually.")
    if not apply:
        print("DRY RUN: no changes made. Pass --apply to copy.")
        return
    copied=[]
    try:
        for source, dest in destinations:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest, symlinks=False)
            else:
                shutil.copy2(source, dest)
            copied.append(dest)
    except Exception:
        # Only rollback our newly created destinations, never pre-existing content.
        for dst in reversed(copied):
            if dst.is_dir():
                shutil.rmtree(dst)
            elif dst.exists():
                dst.unlink()
        raise
    print("Installed files. Codex skill discovery and hooks still require verification.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="Existing Git project directory")
    parser.add_argument("--apply", action="store_true", help="Copy instead of dry-run")
    args=parser.parse_args()
    try:
        run(args.target, args.apply)
    except (ValueError, OSError) as exc:
        print("INSTALL ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)

if __name__=="__main__":
    main()
