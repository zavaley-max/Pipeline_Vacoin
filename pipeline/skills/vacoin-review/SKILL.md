---
name: vacoin-review
description: "Independently review plans, code changes, scope and verification evidence."
---

# Review

Review only the agreed task and affected context. Identify incorrect assumptions, missing acceptance criteria, security regressions, unexpected file edits and evidence gaps. Provide actionable findings with severity and exact references. Do not modify the code while acting as an independent reviewer.

## Operating contract

- Respect the target application's architecture and explicit user requirements.
- Choose the relevant workflow in `pipeline/requests/`.
- Keep edits, evidence and claims tied to the selected task only.
- Do not infer permission to publish, merge, deploy, change production data or exchange knowledge across projects.
- Document limitations and obtain human acceptance before considering work complete.

See `pipeline/README.md` and `docs/FUNCTIONALITY.md` in the installed project.
