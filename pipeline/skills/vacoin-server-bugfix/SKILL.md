---
name: vacoin-server-bugfix
description: "Investigate infrastructure or server-side defects with controlled risk and rollback."
---

# Server bugfix

Start read-only; establish actual paths, versions and deployed commits. Do not assume remote access. Back up before authorized edits and preserve configuration differences. Require explicit authorization for restart, deploy, database changes or destructive commands.

## Operating contract

- Respect the target application's architecture and explicit user requirements.
- Choose the relevant workflow in `pipeline/requests/`.
- Keep edits, evidence and claims tied to the selected task only.
- Do not infer permission to publish, merge, deploy, change production data or exchange knowledge across projects.
- Document limitations and obtain human acceptance before considering work complete.

See `pipeline/README.md` and `docs/FUNCTIONALITY.md` in the installed project.
