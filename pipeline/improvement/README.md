# Pipeline Vacoin Improvement Lab (experimental)

The improvement lab adapts four general ideas associated with Harness² for conservative, Codex-first engineering workflows. It is an **independent implementation**, not a copy of the Google Research framework.

**Propose–Probe–Compose:** prepare a frozen JSON plan describing proposed changes to agent guidance and independent checks. A probe can be launched explicitly in a detached Git worktree, then reviewed. `compose` lists candidates that meet the structured evidence criteria. It does not automatically merge candidate files or promote changes.

**Experience Library:** `record` writes a project-specific lesson only if it has a human approval reference, evidence reference and limitations. Evidence and experience files stay outside the Git checkout; do not share them across projects.

**Parallel / Sequential Recursion:** `schedule` creates an execution plan. Parallel candidates start from the same frozen baseline; sequential candidates depend on prior validated results. The current real runner only executes one individually chosen parallel candidate or the first sequential candidate. There is no automatic multi-round execution.

**Harness Validation:** `validate` enforces plan structure, eligible edit paths, frozen check definitions and project identity. Set the plan's `project` field to the **exact basename of the consuming project's root folder**. The validator compares it to the checkout's name. This is a convenience guard, not an authentication boundary.

## Usage

```bash
python pipeline/improvement/lab.py --root "/path/to/app" validate --plan "/external/evidence/plan.json"
python pipeline/improvement/lab.py --root "/path/to/app" schedule --plan "/external/evidence/plan.json" --output "/external/evidence/schedule.json"
python pipeline/improvement/runner.py --root "/path/to/app" --plan "/external/evidence/plan.json" --candidate c1 --prompt-file "/external/evidence/prompt.txt" --out "/external/evidence/c1"
```

The runner is dry-run by default. The explicit `--execute` flag invokes `codex exec` with workspace-write sandbox settings; model access may incur usage costs. Do not use production credentials or depend on a Git worktree as network/process isolation. The initial probe record remains `incomplete` until independently verified.

`compose` and `record` have additional required arguments, shown by `--help`. The `plan.example.json` and `evidence.example.json` files are placeholders, not approved tasks or actual evidence.

## Limits

No autonomous proposer, independent scoring engine, conflict-safe composer, full multi-step sequential engine, hardened sandbox or automatic cross-project knowledge exchange. Promotion requires a separate human decision.
