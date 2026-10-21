---
name: vacoin-release
description: "Prepare a reviewed software release and rollback plan without deploying automatically."
---

# Release

Require approved release scope, reproducible build/test evidence, migration assessment, security checks and rollback instructions. Never push, tag, merge, deploy or restart solely because a checklist passes.

## Operating contract

- Respect the target application's architecture and explicit user requirements.
- Choose the relevant workflow in `pipeline/requests/`.
- Keep edits, evidence and claims tied to the selected task only.
- Do not infer permission to publish, merge, deploy, change production data or exchange knowledge across projects.
- Document limitations and obtain human acceptance before considering work complete.

See `pipeline/README.md` and `docs/FUNCTIONALITY.md` in the installed project.
