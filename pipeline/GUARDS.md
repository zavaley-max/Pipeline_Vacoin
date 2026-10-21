# Guardrails and Limitations

A scope manifest defines the authorized paths, edits, expected behavior and checks. `snapshot` preserves baseline fingerprints; `scope` detects changes beyond that manifest. `hook` may evaluate intercepted Codex tool calls when supported and activated.

Protected configuration is not changed by ordinary tasks. Use independent approval for modifications to `AGENTS.md`, guards, CLI scripts and hook configuration. Skill prompts and model output are not trusted authorizations.

**Important:** this is a best-effort engineering control, not a comprehensive sandbox. It does not intercept all shell, MCP, network or server writes. Confirm actual hook activation and denial behavior in your own environment. See `docs/SECURITY.md`.
