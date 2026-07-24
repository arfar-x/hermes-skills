---
name: jira-project-context
description: >-
  Returns a reference snapshot of a Jira project: its issue types,
  workflow statuses, components, priorities, assignable users, and
  labels in use. Use for "what statuses does this project use", "who's
  on this project", "what labels exist" -- or before filtering JQL on a
  status/label/assignee you're not sure is real, to verify it instead of
  guessing.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, reference]
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
    prompt: "Default Jira project key (e.g. PAY), if you always work on the same project"
    required_for: optional -- if unset, you must resolve/pass --project yourself
---

# Jira: Project Context

**Read-only.** Run from this skill's directory:

```bash
python3 ../jira/scripts/jira_tool.py project_context [--project PAY]
```

(First-time setup, once per environment: `pip install -r ../jira/requirements.txt`.)

## Why this exists

Most "which tasks are ready for dev" / "who should I assign this to" /
"does this label exist" questions fail the same way: the model guesses a
plausible-sounding status, label, or field name instead of one that's
actually real for this Jira instance, and gets back a silent, misleading
zero-result match rather than an error. This tool is the one place to get
real answers -- a project's `issue_types`, `statuses` (overall and broken
down `statuses_by_issue_type`), `components`, instance-wide `priorities`,
assignable `users`, and a sample of `labels` actually in use -- in a
single call, to verify against instead of guessing.

## Remember it -- don't re-fetch every turn

A project's workflow, team, and label vocabulary don't change often.
Fetch this once per project and, **if your runtime has a persistent-memory
feature (something that survives past this turn or this conversation),
save the interesting parts** as project-scoped facts (e.g. "PAY statuses:
To Do, In Progress, Review, Done"; "PAY team: Alice, Bob, ..."). Consult
that memory in later turns and sessions instead of calling this again --
this tool itself does no caching of its own, so repeat calls always hit
Jira fresh. Only re-fetch if you have a specific reason to think something
changed (e.g. the user mentions a status/person that doesn't match what
you remember).

This same discipline isn't specific to this skill -- it's self-learning
across the whole toolset. `jira-search-users` (account_ids),
`jira-sprint`/`jira-kanban-status`/`jira-board` (a project's board
type/id) each ask the same question before calling anything: do you
already know this? Whatever any of them teaches you is worth folding
into the same per-project memory this skill seeds, not just what this
specific call returns.

## Using the result

- `statuses` / `statuses_by_issue_type` -- use to confirm an exact status
  name before writing `status = '...'` into JQL, or before calling
  `transition`. Note workflows can differ per issue type; check
  `statuses_by_issue_type` if a flat `statuses` match seems off for the
  issue type in question.
- `labels` -- a **sample** drawn from unresolved issues, not an
  exhaustive list (Jira has no endpoint that enumerates every label ever
  used in a project). Say so if the user asks for "all" labels.
- `users` -- assignable users for this project, each with `account_id`.
  If a name the user mentioned unambiguously matches one, use that
  `account_id` directly and skip a separate `search_users` call.
- `priorities` -- instance-wide (Jira priority schemes are rarely
  project-specific), in Jira's own configured order (highest first).
- `components` -- for `create_issue`/`edit_issue`'s `--components`, or to
  confirm one exists before filtering on it.

If the result contains `"error"`, tell the user what went wrong in plain
language instead of retrying silently or fabricating a result.

See `../jira/README.md` for architecture details and the full
environment-variable table.
