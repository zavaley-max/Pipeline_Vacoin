---
name: vacoin-bugfix
description: "Reproduce and correct a bug with minimal change and regression evidence."
---

# Bugfix

Capture expected and actual behavior, reproduce failure, identify root cause and affected modules. Apply the smallest safe fix. Add a regression test and verify no adjacent behavior was damaged. Escalate unclear root cause.

## Operating contract

- Respect the target application's architecture and explicit user requirements.
- Choose the relevant workflow in `pipeline/requests/`.
- Keep edits, evidence and claims tied to the selected task only.
- Do not infer permission to publish, merge, deploy, change production data or exchange knowledge across projects.
- Document limitations and obtain human acceptance before considering work complete.

See `pipeline/README.md` and `docs/FUNCTIONALITY.md` in the installed project.
