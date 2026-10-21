# Security Model and Limitations

Pipeline Vacoin is an engineering aid, **not a security boundary**.

- Scope guards can identify restricted paths and intercepted edits, but cannot prevent every shell, API, MCP or external write.
- `AGENTS.md` and skills are instructions, not OS access controls.
- An independent reviewer instructed to be read-only may still possess real write privileges.
- The optional Codex improvement runner uses a detached Git worktree and a configured sandbox mode. That does not isolate all processes, network access or credentials.
- Keep production credentials, SSH keys, database access and deployment tokens unavailable to experimental agents.
- Maintain read-only baseline and frozen checks, then obtain human approval before adopting any modification to the pipeline.
- Store local evidence and logs outside Git; review them for confidential information.
- Never automatically exchange session histories, experience libraries or rule changes between projects.
- A passing test suite indicates only those tests passed. It cannot certify the integrity of all tools and runtime environments.

**Report vulnerabilities privately to the maintainer** before posting sensitive details in a public issue.
