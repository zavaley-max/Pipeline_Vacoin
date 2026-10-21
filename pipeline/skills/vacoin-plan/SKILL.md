---
name: vacoin-plan
description: "Translate approved requirements into architecture-aware, file-specific implementation plans."
---

# Plan

Gather current behavior, constraints, acceptance criteria, data-flow impacts and risks. Produce a scoped plan with file paths, expected behavior, minimal checks, final regression checks and rollback. Distinguish approved decisions from proposals. Never implement code in a planning-only task.

## Operating contract

- Respect the target application's architecture and explicit user requirements.
- Choose the relevant workflow in `pipeline/requests/`.
- Keep edits, evidence and claims tied to the selected task only.
- Do not infer permission to publish, merge, deploy, change production data or exchange knowledge across projects.
- Document limitations and obtain human acceptance before considering work complete.

See `pipeline/README.md` and `docs/FUNCTIONALITY.md` in the installed project.
