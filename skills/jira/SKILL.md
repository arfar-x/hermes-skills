---
name: jira
description: >-
  High-level Jira assistant. Answers questions like "what should I work
  on next", "summarize my tickets", "what's blocking PAY-123", logs work,
  and moves tickets between statuses -- by calling structured Jira tools
  and reasoning over their JSON output, never by guessing or inventing
  ticket data. Use whenever the user asks about Jira issues, sprints,
  boards, worklogs, or ticket status.
version: 1.0.0
metadata:
  hermes:
    tags: [jira, project-management, tickets, tools]
    category: software-development
    requires_toolsets: [terminal]
required_environment_variables:
  - name: JIRA_BASE_URL
    prompt: "Jira base URL (e.g. https://jira.mycompany.com)"
    required_for: all functionality
  - name: JIRA_USERNAME
    prompt: "Jira username"
    required_for: all functionality
  - name: JIRA_PASSWORD
    prompt: "Jira password"
    required_for: all functionality
  - name: JIRA_AUTO_CONFIRM_WRITES
    prompt: "Skip the confirm step before logging work / transitioning / creating / editing tickets? (true/false)"
    required_for: optional, defaults to false (asks before every write)
  - name: JIRA_DEFAULT_PROJECT
    prompt: "Default Jira project key for triage (e.g. PAY), if you always triage the same project"
    required_for: optional -- only used by triage; if unset, resolve/pass --project yourself
---

# Jira Assistant

## When to use

Any time the user asks about their Jira work: what to work on next,
summarizing tickets, checking blockers, searching issues by JQL, logging
time, moving a ticket's status, or checking the active sprint.

## How it works

This skill is a thin CLI wrapper (`scripts/jira_tool.py`) around a typed
Jira REST client (`lib/jira_client.py`). The CLI **only** validates input,
calls Jira, and prints one JSON document to stdout -- it never
summarizes, prioritizes, or explains. **All reasoning is your job.**

Run it from this skill's directory:

```
python3 scripts/jira_tool.py <tool> [--flags...]
```

(First-time setup, once per environment: `pip install -r requirements.txt`.)

## Core rules

1. **Always call a tool before answering a Jira question.** Never answer
   from memory or assumption -- if you haven't run the relevant command
   this turn, run it first.
2. **Never invent issue information.** Every key, summary, status,
   priority, comment, or date you state must come from the JSON a tool
   returned.
3. **Never fabricate blockers.** Only report a blocker if `blockers`'s
   `reasons` array (or `my_work`/`search`'s `blocked` field) actually
   contains it. If `"blocked": false`, say so -- don't invent a plausible
   one.
4. **Never guess ticket status.** Re-fetch via `issue_summary`, `my_work`,
   or `search` rather than trusting stale conversation history.
5. **Write operations require confirmation.** `transition`, `worklog`,
   `worklog_edit`, `worklog_delete`, `create_issue`, and `edit_issue`
   refuse to execute unless run with `--confirm` (this is enforced in
   code, not just prompted). Unless `JIRA_AUTO_CONFIRM_WRITES=true` is set:
   - State exactly what you're about to do -- **including the date**
     for `worklog` if it isn't today -- and wait for the user's explicit
     yes.
   - Only then re-run the same command with `--confirm` appended.
   - If a result has `"requires_confirmation": true`, treat that as the
     tool declining to act -- relay `pending_action` (which echoes back
     `date`/`started` for worklogs) to the user and ask.
   - For `worklog`/`worklog_edit --date`: resolve relative day-names
     ("last Tuesday", "yesterday") to an actual calendar date yourself
     first -- you know today's date; the tool only accepts unambiguous
     dates, and silently defaulting to today when the user meant a
     different day is exactly the kind of mistake this rule exists to
     prevent.
   - `worklog_delete` is destructive and irreversible -- confirm which
     specific entry (issue, duration, date, description if known)
     before deleting, don't just confirm "delete a worklog".
   - `create_issue`/`edit_issue` never invent an `--assignee_account_id`
     from a display name -- resolve it via `search_users` first (see
     rule 9), and ask the user if `search_users` returns more than one
     match.
6. **Chain tool calls when needed.** E.g. "what should I work on next,
   and is anything blocking it?" = `my_work` first, then `blockers` on
   the top candidate(s).
7. **If a result contains `"error"`,** tell the user what went wrong in
   plain language (not found, permission denied, invalid JQL, etc.)
   instead of retrying silently or fabricating a result.
8. **Link issue keys, don't just print them.** Every tool that returns an
   issue (or a subtask, or a linked issue) includes a sibling `url` field
   (e.g. `issue.url`, `subtasks[].url`, `links[].related_url`) -- when you
   mention an issue key in prose, render it as a markdown link using that
   `url`, e.g. `[PAY-123](https://jira.example.com/browse/PAY-123)`, instead
   of a bare key. Never construct the URL yourself; only use the `url` a
   tool actually returned.
9. **Never write ad-hoc code to talk to Jira.** Every intention this skill
   needs to serve should be reachable by chaining the tools above --
   `search`'s free-form `--jql` plus `search_users` for resolving a
   person's name is the intended escape hatch for requests that don't map
   to a single tool 1:1 (e.g. "find John's tasks that I reported, due
   tomorrow"). Resolve names via `search_users`, resolve relative dates
   yourself, then build the JQL and call `search` -- don't write and run a
   new Python script against the Jira REST API to accomplish the same
   thing.
10. **Ask for only the fields you need.** `search`'s `--only` and
    `issue_summary`'s `--sections` let you name exactly what to fetch and
    get back, instead of everything. Default to the tool's default set for
    open-ended questions; narrow it (e.g. `--only summary,status,priority`,
    or `--sections issue`) once you know exactly which fields answer the
    question, especially over many issues at once -- this is the main
    lever for keeping bulk results token-cheap. `key`, `url`, and
    `custom_fields` are always present regardless of `--only`, and
    `blocked` is always computed for `search` even if `status`/`links`
    weren't explicitly requested.

## Commands

```bash
# Unresolved issues assigned to the current user
python3 scripts/jira_tool.py my_work

# Full context for one issue: fields, comments, worklogs, changelog, links.
# --sections limits which parts to fetch/return (default: all)
python3 scripts/jira_tool.py issue_summary --issue_key PAY-123 [--sections issue,worklogs]

# Blocking status + reasons for one issue
python3 scripts/jira_tool.py blockers --issue_key PAY-123

# Arbitrary JQL search. --only asks for exactly the named fields you need
# instead of everything (default: everything except description and
# time-tracking fields); "blocked" is always computed and returned
python3 scripts/jira_tool.py search --jql "assignee = currentUser() AND updated <= -14d" \
  [--fields customfield_10056] [--only summary,status,priority]

# Enumerate every field (incl. custom fields) to discover a custom field's id by name
python3 scripts/jira_tool.py list_fields

# Look up a user by name/email fragment, to get an account_id for JQL
# assignee filters or create_issue/edit_issue's --assignee_account_id
python3 scripts/jira_tool.py search_users --query john

# Active sprint / board / dates / goal
python3 scripts/jira_tool.py sprint

# Your logged time over a date range, vs. each issue's original estimate
python3 scripts/jira_tool.py worklog_report --since -14d [--until 2026-07-20] [--max_issues 50]

# Log time (write, gated -- see rule 5); --date defaults to now, accepts
# a relative offset ("-1d"), ISO date, or ISO datetime -- resolve
# relative day-names to an actual date yourself first (rule 5)
python3 scripts/jira_tool.py worklog --issue_key PAY-123 --duration 2h \
  --description "implementing validation" [--date 2026-07-20] --confirm

# Move to a status (write, gated -- see rule 5); target status/transition
# name is resolved automatically, no need to know Jira's internal IDs
python3 scripts/jira_tool.py transition --issue_key PAY-123 --status Review --confirm

# Fix a worklog's duration/description/date (write, gated -- see rule 5);
# find --worklog_id via issue_summary's worklogs[].id
python3 scripts/jira_tool.py worklog_edit --issue_key PAY-123 --worklog_id 28459 \
  [--duration 2h] [--description "..."] [--date 2026-07-20] --confirm

# Permanently delete a worklog entry (write, gated, irreversible -- see rule 5)
python3 scripts/jira_tool.py worklog_delete --issue_key PAY-123 --worklog_id 28459 --confirm

# Group unresolved stories/bugs/tasks with their labeled subtasks, for
# frontend/backend/design-readiness triage -- --project falls back to
# JIRA_DEFAULT_PROJECT if omitted
python3 scripts/jira_tool.py triage [--project PAY] [--parent_issue_types Story,Bug,Task]

# Create a new issue or subtask (write, gated -- see rule 5); pass
# --issue_type Sub-task and --parent_key for a subtask, same tool either way
python3 scripts/jira_tool.py create_issue --project PAY --summary "Fix checkout crash" \
  --issue_type Bug [--description "..."] [--parent_key PAY-100] [--labels Frontend,UX] \
  [--assignee_account_id ...] [--priority High] [--components API] --confirm

# Update fields on an existing issue or subtask (write, gated -- see rule 5)
python3 scripts/jira_tool.py edit_issue --issue_key PAY-123 \
  [--summary "..."] [--description "..."] [--labels Frontend] \
  [--assignee_account_id ...] [--priority High] [--components API] --confirm
```

## Examples

**"What should I work on next?"**
Run `my_work`. Reason over the returned list (priority, status, `blocked`,
staleness) and recommend the best candidate in prose -- don't just dump
the JSON.

**"What's blocking PAY-412?"**
Run `blockers --issue_key PAY-412`. If `blocked: true`, summarize
`reasons` in a sentence. If `false`, say nothing is blocking it.

**"Summarize PAY-412."**
Run `issue_summary --issue_key PAY-412`. Produce a concise natural-
language summary of status, recent activity, and any linked work.

**"Log 2h on PAY-412 for implementing validation."**
First confirm with the user ("I'll log 2h on PAY-412: 'implementing
validation' — confirm?"), then run `worklog ... --confirm`.

**"Log 4h30m on PAY-412 for last Tuesday."**
Resolve "last Tuesday" to an actual calendar date yourself (you know
today's date), then confirm with the user including that resolved date
("I'll log 4h 30m on PAY-412 dated 2026-07-20 — confirm?"), then run
`worklog --issue_key PAY-412 --duration 4h30m --description "..." --date 2026-07-20 --confirm`.
Never omit `--date` when the user specified a day other than today --
omitting it logs against right now, silently on the wrong day.

**"That worklog is on the wrong day, it should be Tuesday not Thursday."**
Find the worklog's id (via `issue_summary`'s `worklogs[].id`, or from
the id a prior `worklog` call returned), resolve "Tuesday" to an actual
date, confirm with the user, then run `worklog_edit --issue_key ... --worklog_id ... --date 2026-07-20 --confirm`.
Don't create a new worklog and leave the wrong one in place -- edit the
existing entry, or delete-and-recreate only if the user asks for that
specifically.

**"Delete that worklog, I logged it by mistake."**
Confirm exactly which entry (issue, duration, date) before deleting --
this is irreversible -- then run `worklog_delete --issue_key ... --worklog_id ... --confirm`.

**"Move PAY-412 to Review."**
Confirm with the user, then run `transition --issue_key PAY-412 --status Review --confirm`.

**"Which of my tickets haven't been updated recently?"**
Run `search --jql "assignee = currentUser() AND resolution = Unresolved AND updated <= -14d"`.

**"How many hours have I logged in the last two weeks?"**
Run `worklog_report --since -14d` and report `total_logged_seconds` (converted
to hours) -- don't estimate from memory.

**"How much more than the estimate did I work?"**
Run `worklog_report` for the relevant window and report `total_delta_seconds`
(`total_logged_seconds - total_original_estimate_seconds`), plus the
worst-offending issues from the `issues` list (their own `delta_seconds`).
Note that `original_estimate_seconds` is `null` for any issue with no
estimate set -- exclude those from an "over/under estimate" claim rather
than treating a missing estimate as zero.

**"What did I get stuck on recently?"**
Run `worklog_report` and reason over each issue's `logged_seconds` (vs. its
`original_estimate_seconds`) and its worklogs' `comment` text -- don't just
list the top issue by hours, actually read what the comments say happened.

**"Which tasks have a Figma link?" (design ready)**
Run `list_fields` once, find the field whose `name` matches "Figma" (try
"Figma", "Figma Link", "Design Link" -- the exact label varies per
instance), then `search --jql "..." --fields <that id>` and check
`custom_fields.<that id>` on each issue for a non-empty value. Never
guess a `customfield_NNNNN` id without confirming it via `list_fields`.

**"Which tasks are ready for dev?"**
This is almost always a status name, not a special tool -- run
`search --jql "status = 'Ready for Dev'"` (confirm the exact status name
against the project's workflow first if unsure, e.g. via one `my_work`
or `search` call to see what statuses actually appear).

**"Which task has no log that I should log?"**
Run `search --jql "assignee = currentUser() AND resolution = Unresolved AND timespent is EMPTY"`.

**"Which tasks don't have subtasks yet?" / "Which need backend vs frontend work?" / "Which stories need triage?"**
Run `triage [--project PAY]` (falls back to `JIRA_DEFAULT_PROJECT` if you
omit `--project`; resolve a project yourself first if neither is set --
see `jira-triage`'s SKILL.md). For each returned story: if
`has_frontend_subtask`/`has_backend_subtask` are already known (i.e.
`needs_triage` is `false`), report them as fact. If `needs_triage` is
`true` (no subtasks yet), infer frontend/backend/design needs from
`description`, falling back to `summary` if there's no description --
and if neither gives enough signal, tell the user this story doesn't have
enough information to suggest subtasks rather than guessing. Always
caveat an inferred verdict as inferred, never state it as fact the way
`has_frontend_subtask`/`has_backend_subtask` are.

**"Based on the description, which tasks need backend or frontend?" (ad hoc, no subtask structure yet)**
If the user just wants a one-off read of a few issues rather than a full
triage sweep, `search --only summary,description` (description is omitted
by default, see rule below) or `issue_summary` per issue is fine -- reach
for `triage` instead when the question is really about the Frontend/Backend
subtask workflow across many stories.

**"Find John's tasks that I reported, due tomorrow."** (ad hoc, no dedicated tool)
Per rule 9, chain `search_users` + `search` rather than writing new code:
run `search_users --query john` (ask the user to disambiguate if more than
one match), resolve "tomorrow" to an actual calendar date yourself, then
run `search --jql "assignee = <account_id> AND reporter = currentUser() AND due = <date>"`.

**"Create a bug for the checkout crash."**
Confirm the project, summary, and issue type with the user, then run
`create_issue --project PAY --summary "Checkout crash" --issue_type Bug --confirm`.

**"Add a frontend subtask under PAY-100 for the checkout UI."**
Same tool as above, scoped to a subtask: confirm with the user, then run
`create_issue --project PAY --summary "Checkout UI" --issue_type Sub-task --parent_key PAY-100 --labels Frontend --confirm`.

**"Reassign PAY-123 to John."**
Resolve John to an `account_id` via `search_users` first (ask if there's
more than one match), confirm with the user, then run
`edit_issue --issue_key PAY-123 --assignee_account_id <account_id> --confirm`.

## Reference

See `README.md` in this skill directory for architecture details, the
full environment-variable table, and how to run the test suite
(`pytest`, covering the client, config validation, and every tool's
success/error/confirmation paths).
