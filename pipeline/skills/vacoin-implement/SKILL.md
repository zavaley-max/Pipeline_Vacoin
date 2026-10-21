---
name: vacoin-implement
description: "Implement an approved change with precise file scope and targeted checks."
---

# Implement

Read the approved plan, manifest, dependencies and expected behavior. Work in authorized paths only. Add focused tests. Never infer permission for DB migrations, redeployments, production writes or unrelated refactors. Provide a concise change summary and test evidence.

## Operating contract

- Respect the target application's architecture and explicit user requirements.
- Choose the relevant workflow in `pipeline/requests/`.
- Keep edits, evidence and claims tied to the selected task only.
- Do not infer permission to publish, merge, deploy, change production data or exchange knowledge across projects.
- Document limitations and obtain human acceptance before considering work complete.

See `pipeline/README.md` and `docs/FUNCTIONALITY.md` in the installed project.
