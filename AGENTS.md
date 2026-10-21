# Pipeline Vacoin — Codex Engineering Instructions

This repository is the **distribution** of a Codex-first engineering workflow for complex codebases. Always communicate in the user's requested language. Follow the user's actual requirements and the target application's approved architecture before the pipeline's generic examples.

## Working principles

1. Read the user request and applicable project architecture. Do not invent technical constraints, integrations or database schema.
2. Identify the task route: plan, research, implementation, review, verification, defect, design, infrastructure, release or maintenance.
3. Read only the applicable project-local skill under `.agents/skills/`.
4. Separate confirmed user requirements from agent proposals. Prepare explicit expected behavior, scope and checks.
5. Change only approved files. Avoid opportunistic refactors. Keep a baseline and verify actual file diffs.
6. Assess regression and security risks. An unverified result is not an accepted result.
7. Do not automatically change protected instructions, release to production, run migrations, push changes, merge branches or share project experience.
8. Keep secrets, detailed logs and evidence outside public Git. Never include external project files or confidential work history.
9. Explicitly request or verify authorization for high-impact operations. Preserve user data and rollback options.
10. Harness improvement experiments require isolated workspaces, independent checks and human approval. Do not auto-adopt experimental agent rules.

Start with [pipeline/README.md](pipeline/README.md); use [docs/FUNCTIONALITY.md](docs/FUNCTIONALITY.md) for detail. Hook examples are not enabled automatically.
