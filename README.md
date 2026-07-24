# Agent skills

A personal collection of AI-agent skills -- a portable developer/work
toolset, not a single-purpose repo. It currently holds a Jira toolset;
it's meant to grow with unrelated toolsets (e.g. a company back-office
toolset) as siblings, each following the same convention.

Every skill here is a standard `SKILL.md`-fronted directory (YAML
frontmatter + a markdown body of instructions), with all actual logic
living in a plain Python CLI invoked via a shell/terminal tool. That
shape isn't tied to one agent runtime -- see "Installation" and "Usage"
below for Hermes Agent, Claude Code, and claude.ai specifically.

## Layout and convention

Every toolset in this repo follows the same shape: one directory with
the shared implementation, plus one thin directory per tool/action that
wraps it. For the existing Jira toolset:

```
skills/
├── jira/                # The full Jira client + CLI + tests (shared code)
├── jira-my-work/         # Thin skill: unresolved issues assigned to you
├── jira-issues/           # Thin skill: arbitrary JQL search
├── jira-issue-summary/    # Thin skill: full context for one issue
├── jira-blockers/         # Thin skill: blocking status for one issue
├── jira-sprint/           # Thin skill: active sprint/board/goal
├── jira-kanban-status/    # Thin skill: kanban board columns/issue counts
├── jira-board/             # Orchestrator: sprint or kanban_status, auto-detected
├── jira-worklog/          # Thin skill: log time (write, confirm-gated)
├── jira-worklog-edit/     # Thin skill: fix a worklog's duration/description/date (write, confirm-gated)
├── jira-worklog-delete/   # Thin skill: permanently delete a worklog (write, confirm-gated)
├── jira-log/               # Orchestrator: log/edit/delete a worklog, routed by intent (write, confirm-gated)
├── jira-status/           # Thin skill: move an issue's status (write, confirm-gated)
├── jira-worklog-report/   # Thin skill: logged time vs. estimate over a date range
├── jira-triage/           # Thin skill: group stories with their labeled subtasks for FE/BE/design triage
├── jira-search-users/     # Thin skill: look up a user's account_id by name/email
├── jira-create-issue/     # Thin skill: create a new issue or subtask (write, confirm-gated)
├── jira-edit-issue/       # Thin skill: update fields on an existing issue or subtask (write, confirm-gated)
└── jira-project-context/  # Thin skill: reference snapshot of a project's statuses/labels/users
```

A future toolset (say, `backoffice`) would land the same way:
`skills/backoffice/` for the shared client + CLI + tests, and
`skills/backoffice-<action>/` for each thin per-action skill -- see
"Adding a toolset" below.

Each thin `<toolset>-<action>` skill has its own `SKILL.md` so it gets
its own slash command (`/jira-my-work`, `/jira-issues`, ...) -- Hermes
maps one `SKILL.md` to exactly one slash command, with no sub-command or
namespacing support. Every thin skill is a wrapper that calls into
`<toolset>/scripts/*.py` via a relative path; `<toolset>/` itself also
still works standalone as a single do-everything skill (e.g. `/jira`).

A thin skill normally maps 1:1 to a single CLI subcommand. The one
documented exception is an **orchestrator skill** (e.g. `jira-board`,
`jira-log`): it doesn't add a new action of its own, it routes between
two or more *existing* thin skills' subcommands based on a condition --
either a signal returned by one of them (`jira-board` checks whether
`sprint` reports a kanban board before deciding to call `kanban_status`
instead) or the caller's own phrasing (`jira-log` picks `worklog` vs.
`worklog_edit` vs. `worklog_delete` from what's being asked). This keeps
the underlying sub-skills fully usable standalone for a caller who
already knows which one they want, while giving one skill/slash command
to reach for when they don't. Skills still cannot call each other
programmatically -- an orchestrator's `SKILL.md` body just tells the
agent which subcommand to run next, the same as any other instruction in
this repo.

See `skills/jira/README.md` for that toolset's architecture,
configuration, and test suite -- future toolsets should have their own
equivalent README under `skills/<toolset>/`.

## Tools

One row per thin skill, across all toolsets. Keep this in sync when
adding or removing a `skills/<toolset>-<action>/` directory -- it's the
single place to see everything installable at a glance.

| Skill | Toolset | Type | Description |
|---|---|---|---|
| `jira` | [jira](skills/jira) | Read + Write | Do-everything Jira assistant (all actions below, one skill) |
| `jira-my-work` | [jira](skills/jira) | Read | Unresolved issues assigned to the current user (scoped to a project by default) |
| `jira-issues` | [jira](skills/jira) | Read | Arbitrary JQL search (incl. components/subtasks/custom fields; description on request) |
| `jira-issue-summary` | [jira](skills/jira) | Read | Full context for one issue (fields, comments, worklogs, changelog, links) |
| `jira-blockers` | [jira](skills/jira) | Read | Blocking status + reasons for one issue |
| `jira-sprint` | [jira](skills/jira) | Read | Active sprint, board, dates, goal (scoped to a project by default) |
| `jira-kanban-status` | [jira](skills/jira) | Read | Kanban board columns and per-column issue counts |
| `jira-board` | [jira](skills/jira) | Read | Orchestrator: routes to `jira-sprint` or `jira-kanban-status`, auto-detected |
| `jira-worklog` | [jira](skills/jira) | Write (gated) | Log time against an issue, optionally backdated |
| `jira-worklog-edit` | [jira](skills/jira) | Write (gated) | Update an existing worklog's duration/description/date |
| `jira-worklog-delete` | [jira](skills/jira) | Write (gated) | Permanently delete a worklog entry |
| `jira-log` | [jira](skills/jira) | Write (gated) | Orchestrator: routes to `jira-worklog`/`jira-worklog-edit`/`jira-worklog-delete` by intent |
| `jira-status` | [jira](skills/jira) | Write (gated) | Move an issue to a new status |
| `jira-worklog-report` | [jira](skills/jira) | Read | Logged time vs. estimate over a date range, per issue and total |
| `jira-triage` | [jira](skills/jira) | Read | Group unresolved stories/bugs/tasks with their labeled subtasks, for frontend/backend/design-readiness triage |
| `jira-search-users` | [jira](skills/jira) | Read | Look up a user's account_id by name/email fragment |
| `jira-create-issue` | [jira](skills/jira) | Write (gated) | Create a new issue or subtask |
| `jira-edit-issue` | [jira](skills/jira) | Write (gated) | Update fields on an existing issue or subtask |
| `jira-project-context` | [jira](skills/jira) | Read | Reference snapshot of a project: issue types, statuses, components, priorities, users, labels |

## Installation

1. Clone this repo somewhere permanent -- skills run straight out of the
   checkout, there's no build/publish step:

   ```bash
   git clone git@github.com:arfar-x/skills.git
   ```

2. Install each toolset's Python dependencies into whatever environment
   your agent runtime actually executes shell commands in (see the
   per-runtime notes below for what that environment is):

   ```bash
   pip install -r skills/jira/requirements.txt
   ```

3. Set the environment variables each toolset needs (see that toolset's
   own `README.md`, e.g. `skills/jira/README.md`, for its config table --
   for Jira that's `JIRA_BASE_URL` / `JIRA_USERNAME` / `JIRA_PASSWORD`).
   Where those variables need to live differs by runtime -- see below.

### Hermes Agent

- **Discovery**: point `skills.external_dirs` in `~/.hermes/config.yaml`
  at this repo's `skills/` directory:

  ```yaml
  skills:
    external_dirs:
      - /path/to/your/local/checkout/of/skills/skills
  ```

  or `hermes skills install arfar-x/agent-skills/skills/<path-to-one-skill>` to fetch
  a single skill by path. There is no bulk/sub-package install -- one
  `SKILL.md` per install call, so `external_dirs` is the practical
  option for a growing personal collection like this one.
- **Slash commands**: Hermes maps exactly one `SKILL.md` to exactly one
  `/<name>` command, with no sub-command or colon-namespacing support.
  That's why each tool (`jira-my-work`, `jira-issues`, ...) is its own
  thin skill directory instead of one skill with sub-commands.
- **Env vars**: Hermes runs skill code in a sandboxed `terminal` tool
  that strips environment variables by default. A var only reaches the
  process if it's listed in that skill's `required_environment_variables`
  frontmatter *and* the skill has been loaded in the session (Hermes
  auto-registers the allowlist on `skill_view`). An env var actually read
  by the code but missing from that list is silently stripped, not just
  undocumented -- this applies to every toolset here, not just Jira, so
  each new toolset's skills must list every env var its code path reads.
  See the "Conventions" note in `AGENTS.md`. Set the actual values
  wherever Hermes' sandbox inherits its environment from (e.g. its own
  `.env` file).
- Alternatively, if your Hermes deployment can't use `external_dirs`
  (e.g. a remote/managed instance), copy a skill directory directly:
  `cp -r skills/jira ~/.hermes/skills/jira`. This creates a disconnected
  copy -- future changes to this repo won't apply until you re-copy.

### Claude Code

- **Discovery**: copy or symlink a skill directory into
  `.claude/skills/<name>/` (project-scoped) or `~/.claude/skills/<name>/`
  (personal, available in every project), e.g.:

  ```bash
  ln -s /path/to/your/local/checkout/of/skills/skills/jira ~/.claude/skills/jira
  ```

  Claude Code decides when to invoke a skill by matching its
  `description` against the task at hand -- there's no separate
  per-skill slash-command registration step.
- **Env vars**: Claude Code's shell tool inherits your actual shell
  environment, so a toolset's required env vars just need to be
  exported normally (`.zshrc`, a sourced `.env`, etc.) -- there's no
  separate allowlist to satisfy, unlike Hermes.

### claude.ai (web/app)

- **Discovery**: zip the skill directory (e.g. `skills/jira/`) and
  upload it under Settings -> Capabilities -> Skills.
- **Env vars / network**: code there runs inside Anthropic's own hosted
  sandbox, which has no access to your local shell environment *or*
  your internal network. A toolset that calls out to an internal host
  (an on-prem Jira, an internal back-office API, ...) won't be reachable
  from there regardless of env vars -- this path only really works for
  services reachable from the public internet, and you'll need another
  way to supply secrets (claude.ai's own per-skill configuration, if
  the toolset exposes one).

### Frontmatter compatibility

Hermes-only frontmatter keys (`metadata.hermes.*`,
`required_environment_variables`) are just unknown YAML to Claude and
are ignored -- no stripping or per-platform variant is needed. The same
`SKILL.md` file works unmodified across every runtime above.

## Usage

Once a toolset's env vars are set and its skill is discoverable (see
Installation), invoke it:

- **Hermes**: use its slash command directly, e.g. `/jira-my-work`, or
  `/jira` for the do-everything form (e.g. `/jira what's blocking
  PAY-123?`). Run `/skills` to confirm a skill is currently loaded.
- **Claude Code / claude.ai**: just ask in plain language -- e.g. "what
  should I work on next in Jira?" or "log 2h against PAY-123". Claude
  matches your request against each installed skill's `description` and
  invokes it (and its underlying CLI) automatically; there's no slash
  command to remember.

Every toolset documents its own read vs. write actions and any
confirmation gating in its own `README.md` -- e.g. `skills/jira/README.md`
lists `my_work`, `issue_summary`, `blockers`, `search`, `search_users`,
`sprint` (read), and `worklog`, `transition`, `create_issue`, `edit_issue`
(write, refuse to run without `--confirm` or
`JIRA_AUTO_CONFIRM_WRITES=true`). Check that file before relying on a
new toolset's write actions.

## Adding a toolset

To add an unrelated toolset (e.g. a company back-office skill-set),
follow the same pattern the Jira toolset already uses:

1. `skills/<toolset>/` -- the shared implementation: a `lib/` (client,
   auth/config from env vars), `tools/` (one module per action), a
   `scripts/<toolset>_tool.py` CLI dispatcher, a `tests/` suite, its own
   `requirements.txt`, and a `README.md` documenting its config and env
   vars. This directory's own `SKILL.md` can work standalone as a
   single do-everything skill.
2. `skills/<toolset>-<action>/` -- one thin `SKILL.md`-only directory
   per action/tool, each shelling out to
   `../<toolset>/scripts/<toolset>_tool.py <action> [flags]`. These
   exist purely so each action gets its own slash command in Hermes;
   they contain no Python of their own and nothing to test.
3. List every env var the toolset's code actually reads in each thin
   skill's `required_environment_variables` frontmatter (Hermes-only,
   but harmless elsewhere -- see "Frontmatter compatibility" above).
4. Follow the repo-wide conventions in `AGENTS.md` regardless of
   toolset -- credentials only from env vars, no hardcoded local paths,
   write/mutating actions confirmation-gated in code (not just
   prompted).
5. Add one row per new thin skill to the "Tools" table above.

No registration step is needed beyond adding the files -- Hermes
discovers new skills the next time it scans `external_dirs`, and Claude
discovers them the next time you copy/symlink into `.claude/skills/`
(or re-zip for claude.ai).
