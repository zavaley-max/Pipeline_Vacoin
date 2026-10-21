# Pipeline Vacoin

**A Codex-first engineering pipeline for building and maintaining large, complex software systems.**

> **This is my first public project.** I built Pipeline Vacoin to make AI-assisted engineering more disciplined, traceable, and reliable when codebases become too large and interconnected for ad-hoc prompting.
>
> **Designed primarily for OpenAI Codex.** The workflow and agent skills prioritize Codex. Other coding agents may adapt the Markdown guidance, but integration with them is not guaranteed.

**Release status:** Public-release candidate **0.4.0-preview**. The repository remains private until the author explicitly publishes it. This is *not* an officially supported OpenAI or Google product.

Pipeline Vacoin provides a reusable project-local workflow, not an AI model. It organizes requirements, architecture-aware planning, scoped implementation, code review, verification, session continuity, incident learning, and controlled experiments to improve the agent's own instructions.

## Why it exists

Large software systems require more than generating code that passes one test. Changes may cross APIs, database boundaries, asynchronous jobs, user interfaces, authorization rules, and deployment environments. Pipeline Vacoin makes the agent account for these dependencies **before** it edits files, verifies what changed, records how the result was tested, and leaves final approval with the developer.

## Features at a glance

| Area | Capabilities |
| --- | --- |
| Planning | Requirements, file-specific plans, architecture impact, acceptance criteria |
| Guardrails | Explicit scope manifests, snapshot comparisons, guarded paths, limited secret-pattern scanning |
| Delivery | Implementation guidance, regression checks, verification receipts, independent review |
| Continuity | Per-project sessions, handoffs, error records and lessons |
| Reliability | Read-only diagnosis, recovery guidance, conservative deployment checklists |
| Improvement (experimental) | Propose–Probe–Compose; Experience Library; parallel/sequential schedules; harness validation |
| Codex integration | 14 project-local skills, `AGENTS.md`, opt-in hook examples, explicit `codex exec` probe runner |

## Quick start

Requirements: **Python 3.10+**, Git, and a supported Codex CLI for agent-powered workflows. Python checks use the standard library; the optional improvement runner invokes `codex exec`. Verify your CLI version and sandbox capabilities independently.

```bash
git clone https://github.com/zavaley-max/Pipeline_Vacoin.git
cd Pipeline_Vacoin
python -m unittest discover -s pipeline/tests -v
python scripts/install.py --target /absolute/path/to/your-project
python scripts/install.py --target /absolute/path/to/your-project --apply
```

The first install command is a **dry run**. The second copies a local `pipeline/` and project-scoped `.agents/skills/` to your application repository without overwriting existing files. If an `AGENTS.md` already exists, merge the provided guidance manually. Never install into a production worktree without inspecting the changes first.

Then open your application project with Codex, read `AGENTS.md` and `pipeline/README.md`, and select only the skill relevant to your task.

## Full documentation

- [Complete functionality guide](docs/FUNCTIONALITY.md) — detailed capabilities, commands, limits, and examples.
- [Installation and configuration](docs/INSTALL.md) — portable installation, Codex skills and opt-in hooks.
- [Security and boundaries](docs/SECURITY.md) — what the guards protect and what they do not.
- [Improvement lab](pipeline/improvement/README.md) — experimental harness-improvement workflow.
- [Credits and third-party notices](docs/CREDITS.md) — upstream inspirations and bundled license notices.

## Core philosophy

**Human approval is the release gate.** The pipeline does not automatically merge, deploy, execute database migrations, publish repositories, modify production services, or share knowledge between separate projects. Its tools are safeguards and evidence collectors; they are **not** a hardened security sandbox.

## License and attribution

Source code and original documentation in this distribution are offered under [MIT](LICENSE), except separately marked third-party material. See [credits](docs/CREDITS.md) and preserved license notices in `licenses/`. The improvement design draws inspiration from [Harness²](https://github.com/google-research/harness2) without bundling its implementation.

Contributions, issues, feedback and reproducible bug reports are welcome after the public launch.
