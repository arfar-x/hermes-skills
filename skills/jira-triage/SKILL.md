---
name: jira-triage
description: >-
  Groups unresolved Jira stories/bugs/tasks with their labeled subtasks to
  determine which ones need frontend work, backend work, or design/Figma
  readiness, and which ones haven't been broken into subtasks yet and need
  manual triage. Use for "which tasks have no subtasks yet", "which need
  frontend vs backend", "which stories still need triage".
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, triage]
    category: software-development
    requires_toolsets: [terminal]
required_environment_variables:
  - name: JIRA_BASE_URL
    prompt: "Jira base URL (e.g. https://jira.mycompany.com)"
    required_for: all functionality
  - name: JIRA_USERNAME
    prompt: "Jira username"
    required_for: basic auth mode (the default)
  - name: JIRA_PASSWORD
    prompt: "Jira password"
    required_for: basic auth mode (the default)
  - name: JIRA_DEFAULT_PROJECT
    prompt: "Default Jira project key for triage (e.g. PAY), if you always triage the same project"
    required_for: optional -- if unset, you must resolve/pass --project yourself
---

# Jira: Triage

**Read-only.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py triage [--project PAY] [--parent_issue_types Story,Bug,Task]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

## Why this exists

In a common team workflow, a PM creates parent issues (Story/Bug/Task/Epic)
from business asks, and developers/designers create subtasks under them
labeled `Frontend`/`Backend` (or similar). A parent story often doesn't say
by itself whether it needs frontend, backend, or both -- that only becomes
explicit once subtasks exist. This tool surfaces exactly that gap: which
stories already have labeled subtasks (so the answer is a known fact), and
which don't yet (so the answer has to be inferred or flagged as unclear).

## What the tool returns (fact, not judgment)

`triage` does two Jira searches and groups the results -- pure bookkeeping,
no inference:

1. Parent issues (`--parent_issue_types`, default `Story,Bug,Task`) in the
   project, each with `description`, `components`, `status`.
2. Subtasks (`issuetype = Sub-task`) in the same project, each with its
   `labels` and parent key -- fetched as their own search because a parent's
   embedded `subtasks` field is a stub that does **not** include labels.

Each returned story has:

- `subtasks`: the matched subtask stubs (`key`, `summary`, `status`, `labels`).
- `has_frontend_subtask` / `has_backend_subtask`: `true` only if a subtask's
  `labels` actually contains "frontend"/"backend" (case-insensitive
  substring match) -- a fact, not a guess.
- `needs_triage`: `true` when `subtasks` is empty -- meaning nobody has
  broken this story into Frontend/Backend/Design work yet.

## Your job: reasoning over what the tool returns

- **If a story has subtasks** (`needs_triage: false`): answer
  frontend/backend questions directly from `has_frontend_subtask` /
  `has_backend_subtask` -- these are already known facts, don't re-infer
  them from the description.
- **If a story has no subtasks yet** (`needs_triage: true`): infer whether
  it needs frontend, backend, and/or design work from its `description`.
  - If `description` is empty or too vague to tell, fall back to
    `summary` (the title) and judge whether the title alone gives enough
    signal (e.g. "Fix login page styling" clearly implies frontend).
  - If neither the description nor the title gives enough information to
    infer anything useful, say so explicitly to the user -- e.g. "PAY-142
    has no subtasks and its description/title don't give enough detail to
    suggest what work it needs; it needs a human look." Never invent a
    frontend/backend/design verdict when there isn't enough signal for one.
  - Always caveat inferred verdicts as inferred (e.g. "likely needs
    frontend, based on the description") -- never state them with the same
    confidence as a `has_frontend_subtask`/`has_backend_subtask` fact.
- **"Design/Figma ready?"** isn't part of this tool's output (Figma link
  fields are instance-specific custom fields) -- run `list_fields` (via
  the `jira` skill's CLI, `python3 ../jira/scripts/jira_tool.py
  list_fields`) to find the field id, then `search --fields <id>` per
  story, or read it from `description` if the link is embedded in text.

## Project scope

`--project` is required by the underlying Jira client, one way or another:

- If `JIRA_DEFAULT_PROJECT` is set, omitting `--project` uses it automatically.
- Otherwise, resolve the project yourself before calling this -- e.g. from
  an issue key already mentioned in the conversation, from a quick
  `jira-my-work` call to see what project keys appear, or by asking the
  user. Never guess a project key.
- If the tool's result has `"error"` because no project could be resolved,
  ask the user which project to triage instead of retrying blindly.

## Example

**"Which stories still need frontend or backend, and which need review because they have no subtasks?"**
Run `triage --project PAY` (or without `--project` if `JIRA_DEFAULT_PROJECT`
is set). For each story: if `needs_triage` is `false`, report
`has_frontend_subtask`/`has_backend_subtask` as fact. If `needs_triage` is
`true`, read `description` (falling back to `summary`) and give an inferred,
clearly-caveated verdict -- or say there isn't enough information if there
isn't.

If the result contains `"error"`, tell the user what went wrong in plain
language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
