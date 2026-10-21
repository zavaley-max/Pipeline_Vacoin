# Pipeline Vacoin — Complete Functionality Guide

## 1. Purpose and scope

Pipeline Vacoin is an engineering workflow for **OpenAI Codex**, optimized for large, complex, evolving codebases. It is designed to help developers plan changes, control scope, carry context between sessions, review results and progressively improve agent instructions. It does **not** generate a software architecture or select technologies on its own: project architecture and requirements remain authoritative.

## 2. Request routing and 14 skills

Select the minimum necessary project-local skill from `.agents/skills/`:

| Skill | Responsibility |
| --- | --- |
| `vacoin-plan` | Translate authorized requirements into architecture-aware, file-specific plans |
| `vacoin-research` | Inspect implementation options and evidence without changing code |
| `vacoin-review` | Review plans, diffs, requirements and regression risks independently |
| `vacoin-implement` | Implement only approved changes in a controlled scope |
| `vacoin-verify` | Define and run targeted/final checks; inspect evidence and regressions |
| `vacoin-design` | Turn UX requirements into testable design handoff |
| `vacoin-bugfix` | Reproduce, diagnose and minimally fix defects |
| `vacoin-server-bugfix` | Investigate and plan server-side repairs with rollback |
| `vacoin-session` | Resume, hand off and close a project session with explicit status |
| `vacoin-lessons` | Record confirmed error causes, useful fixes and limitations |
| `vacoin-guards` | Review file-scope, protected paths, secrets and hook behavior |
| `vacoin-stuck` | Break out of repeated unsuccessful attempts using evidence |
| `vacoin-release` | Prepare release evidence and rollback; no automatic deployment |
| `vacoin-maintain` | Maintain the pipeline itself under explicit authorization |

A skill is written guidance, not an automatic invocation guarantee. Installation and discovery must be checked for each Codex version.

## 3. The engineering lifecycle

**Intake → Understand → Plan → Review → Scoped implementation → Targeted verification → Independent review → Final checks → Human acceptance → Optional release.**

Before coding: determine current behavior, architecture decisions, affected files, data dependencies, intended behavior, edge cases and acceptance tests. Record requirement changes separately from agent suggestions.

A proposed patch is restricted to a documented scope manifest and should not silently include unrelated refactors. Files may change only with authorization. New requirements trigger impact analysis, not hidden scope expansion.

## 4. Scope manifests and checks

`pipeline/templates/scope.example.json` demonstrates `schema_version: 1`, `task_id`, `plan_ref`, `authorization_ref`, `root_kind`, file operations, permitted sections, expected behavior and an array of checks. Customize every value.

The standard-library CLI (`pipeline/scripts/pipeline.py`) supports:

| Command | Function |
| --- | --- |
| `doctor` | Check required pipeline files and skill presence; not proof of active hooks |
| `validate` | Validate a manifest, paths, checks and declared guard rules |
| `snapshot` | Record the initial content for scoped comparison |
| `scope` | Detect out-of-scope changed, created or removed files versus baseline |
| `run-check` | Execute one explicitly declared test with a timeout, capturing a receipt |
| `check-receipt` | Confirm the receipt matches content, command and lane |
| `hook` | Evaluate certain intercepted tool operations against manifest guards |
| `secrets` | Detect a limited set of recognizable credential patterns |
| `resume-check` | Check selected session references without automatic resumption |

Run `python pipeline/scripts/pipeline.py --help` and the relevant subcommand's help for exact options. The hook does not cover every tool, shell escape, connector or mutation route. A receipt proves only the recorded check, not correctness of the entire system.

## 5. Evidence and sessions

Keep task notes, requirements, plan references and work-session state in your own repository according to your organization's policy. **Keep detailed evidence, logs, sensitive results, experiment worktrees and credentials outside version control.** Do not automatically archive, delete or publish working records.

Error reviews should capture what failed, what was tried, the confirmed root cause, the relevant evidence and limitations of the remedy. A proposed lesson must not silently become an enforced policy.

## 6. Experimental improvement lab

Four selected mechanisms are offered as **controlled experimental building blocks**, not a fully autonomous self-improving agent:

**Propose–Probe–Compose:** an authorized plan declares candidate improvements and frozen checks. Probes can run in separate detached worktrees; reports identify eligible candidates. Any combination and adoption require human review.

**Experience Library:** record a validated, human-approved lesson with its scope and evidence reference in a local project-specific location. This is not a shared cloud memory system.

**Parallel / Sequential Recursion:** deterministic schedules define independent candidates or a chain of refinement. The current runner supports individually selected candidates and the first sequential step; it does not automatically execute the whole chain.

**Harness Validation:** checks plan integrity, allowed edit surfaces, fingerprints, results schema, mandatory regression checks and non-automatic promotion. It does not authenticate an evaluator or provide OS-level isolation.

CLI:
```bash
python pipeline/improvement/lab.py --help
python pipeline/improvement/runner.py --help
```

Use `runner.py` without `--execute` first. An opt-in `--execute` starts real Codex execution and can incur usage costs. Worktrees are not containers; run the pilot without production secrets or external write access.

## 7. Release and rollback

Review scope, tests, security, data changes and deployment plan. Preserve Git history and any necessary backup. Never assume Git rollback will undo database writes, remote API calls or irreversible production operations. Publishing, merging and deployment require separate user authorization.

## 8. Known limitations

- The improvement lab has no automatic proposer, independent scoring engine, conflict-safe composition or fully automated multi-step sequential execution.
- Hooks are opt-in and need version-specific validation.
- The core CLI's secret scanner recognizes only documented patterns.
- No automated transfer of experience or settings across repositories.
- No continuous background agent or autonomous release management.
- Installation and CI passing do not guarantee safe use in a particular production environment.

## 9. Recommended first use

Choose an actual, narrow development task in a nonproduction branch. Write a scoped plan; take a snapshot; make the smallest change; run targeted checks; perform independent review; inspect the final scope and receipts; obtain human acceptance. Only after the standard workflow is stable, pilot the improvement lab on agent instructions.
