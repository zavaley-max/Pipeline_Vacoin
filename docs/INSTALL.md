# Installation and Codex Configuration

## Requirements

- Python 3.10+.
- Git.
- OpenAI Codex CLI for agent execution and project-local skills.
- A separate test workspace for experimental probe runs.

## Install into a project

```bash
git clone https://github.com/zavaley-max/Pipeline_Vacoin.git
cd Pipeline_Vacoin
python -m unittest discover -s pipeline/tests -v
python scripts/install.py --target "/absolute/path/to/your-app"
python scripts/install.py --target "/absolute/path/to/your-app" --apply
```

The installer only copies a local pipeline and skills; it does not configure your operating system or activate hooks. It refuses to overwrite existing destinations and leaves an existing `AGENTS.md` unchanged. If a destination already exists, inspect and merge it manually; **do not delete existing user data to make the installation pass**.

It will install the following where absent:

```text
your-app/
  AGENTS.md
  pipeline/
    scripts/
    improvement/
    templates/
    tests/
    ...
  .agents/skills/vacoin-*/
```

Check that your Codex version recognizes the project-local skills. The installer makes no assumptions about a particular global Codex configuration.

## Optional Codex hook integration

`pipeline/templates/codex-hooks.toml` is a **nonactive example**, not a guarantee that your Codex supports that event or command shape. Verify your installed Codex documentation and trusted hook mechanism, fill in local absolute paths and scope manifest, and manually merge changes with existing project configuration. Perform real allow/deny tests; inspect every escape route via shell or external tools. Do not replace the user's entire config.

## Starting a task

1. Read the project's `AGENTS.md` and its architecture or conventions.
2. Select the appropriate `vacoin-*` skill.
3. Capture a requirement reference and an exact file-scope plan.
4. Fill out `pipeline/templates/scope.example.json` with real authorized files and checks.
5. Validate the manifest, snapshot the working state, then begin edits.
6. Verify changed files and run independent review and regression tests.
7. Record human acceptance; publish changes only on explicit instruction.

## Storage guidance

Store sensitive evidence, model outputs and per-task experiment worktrees **outside the application Git checkout**. The improvement plan's `project` must match the exact root-directory name of the target checkout. Do not use a shared evidence or experience directory for unrelated projects.

## Updating

Install new versions into a separate checkout, compare files before updating existing installations, back up customized configuration, and preserve a rollback commit. Installer refusal to overwrite is intentional.
