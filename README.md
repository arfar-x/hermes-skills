# hermes-skills

A personal collection of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
skills, installed via `skills.external_dirs` in `~/.hermes/config.yaml`
pointed at this repo's `skills/` directory.

## Layout

```
skills/
├── jira/                # The full Jira client + CLI + tests (shared code)
├── jira-my-work/         # Thin skill: unresolved issues assigned to you
├── jira-issues/           # Thin skill: arbitrary JQL search
├── jira-issue-summary/    # Thin skill: full context for one issue
├── jira-blockers/         # Thin skill: blocking status for one issue
├── jira-sprint/           # Thin skill: active sprint/board/goal
├── jira-worklog/          # Thin skill: log time (write, confirm-gated)
└── jira-transition/       # Thin skill: move an issue's status (write, confirm-gated)
```

Each `jira-*` skill has its own `SKILL.md` so it gets its own slash
command (`/jira-my-work`, `/jira-issues`, ...) -- Hermes maps one
`SKILL.md` to exactly one slash command, with no sub-command or
namespacing support. Every `jira-*` skill is a thin wrapper that calls
into `jira/scripts/jira_tool.py` via a relative path; `jira/` itself
also still works standalone as a single do-everything skill via
`/jira`.

See `skills/jira/README.md` for the client's architecture, configuration,
and test suite.

## Adding a skill

Drop a new `<name>/SKILL.md`-fronted directory under `skills/`. No
registration step is needed beyond that -- Hermes discovers it the next
time it scans `external_dirs`.
