# Pipeline Vacoin — Codex-first Engineering Pipeline

A project-local workflow for engineering complex systems, organized around human-approved requirements, scoped changes, test evidence, and review.

Start in `AGENTS.md`; choose a route in `requests/` and an installed skill in `.agents/skills/`. Do not preload all skills or project documents.

- [Commands](COMMANDS.md)
- [Scope and guardrails](GUARDS.md)
- [Skill catalog](SKILLS.md)
- [Improvement experiments](improvement/README.md)
- [Full user guide](https://github.com/zavaley-max/Pipeline_Vacoin/blob/main/docs/FUNCTIONALITY.md)

The core CLI is `scripts/pipeline.py`; all Codex hooks are opt-in. The optional improvement lab is experimental and never automatically shares learning between projects.

**Status:** preview 0.4.0; validate in each target environment. Written primarily for Codex.
