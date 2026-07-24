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
   tool actually returned. This applies just as much to bulk/grouped
   output (a status-grouped list, a table, a summary line rolling up
   several keys) as it does to a single issue mentioned in a sentence --
   don't drop back to bare keys once you're listing many issues at once;
   link every one.
9. **Never write ad-hoc code -- neither to talk to Jira, nor to
   post-process a tool's output.** Every intention this skill needs to
   serve should be reachable by chaining the tools above -- `search`'s
   free-form `--jql` plus `search_users` for resolving a person's name is
   the intended escape hatch for requests that don't map to a single tool
   1:1 (e.g. "find John's tasks that I reported, due tomorrow"). Resolve
   names via `search_users`, resolve relative dates yourself, then build
   the JQL and call `search` -- don't write and run a new Python script
   against the Jira REST API to accomplish the same thing. This also
   covers sorting/filtering/picking-the-max out of a tool's own JSON
   result (e.g. "what's the last task I worked on"): use `--order_by`/
   `--max_results`/`--only` (`my_work`, `search`) to get exactly the
   answer back, or reason over the JSON yourself -- don't pipe a tool's
   output into a second interpreter (`python3 -c ...`, `jq`, etc.) to
   compute it. Besides being unnecessary, piping tool output straight
   into another interpreter is exactly the kind of command a security
   scanner (Hermes' included) will flag and block for approval.
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
11. **Never guess a JQL field name or literal value -- there are two
    different vocabularies, don't mix them up.** `--only`/`--sections`
    use this skill's own output names (`due_date`, `issue_type`);
    `--jql` uses Jira's own JQL field names, which are different:
    `due` (not `due_date`), `issuetype` (not `issue_type`), `reporter`
    for "who filed this" (not `creator` -- don't invent an alternate
    field name if a query using the documented one returns nothing).
    Use exactly the field names shown in this file's Examples --
    `reporter`, `assignee`, `status`, `due`, `priority`, `labels`,
    `resolution`, `updated`, `created`. Never write a status literal
    (e.g. `status = 'Pending'`) into JQL unless you've actually seen
    that exact status appear in a prior `my_work`/`search` result, in
    `project_context`'s `statuses`, or the user gave it to you -- a
    plausible-sounding guess doesn't error, it just silently returns
    zero misleading results. If a query built this way still returns
    nothing, don't silently swap in a different field name and retry
    blind -- tell the user exactly what you searched (state the JQL)
    and ask, or verify first (`project_context` for statuses/labels/
    users, `list_fields` for custom fields) rather than guessing your
    way through several variants.
12. **Remember a project's workflow instead of re-fetching it every
    turn.** `project_context --project X` returns a project's real
    `issue_types`, `statuses`, `components`, `priorities`, assignable
    `users`, and a sample of `labels` in one call -- this is the
    grounding source rule 11 refers to. Call it once per project; if
    your runtime has a persistent-memory feature (something that
    survives past this turn or this conversation), save the interesting
    parts as project-scoped facts (e.g. "PAY statuses: To Do, In
    Progress, Review, Done"; "PAY team: Alice, Bob, ...") so later turns
    and sessions can consult that memory instead of calling
    `project_context` again -- a project's workflow, team, and label
    vocabulary don't change often. Use whatever you already know (freshly
    fetched or remembered) to catch a likely typo or mismatched term in
    what the user said (e.g. "pended" doesn't match any real status --
    ask what they meant) instead of guessing blind.
13. **Format every response for fast skimming, using the templates
    below.** This applies in every runtime you might be running in, not
    just one particular chat surface -- it's plain markdown plus emoji,
    which renders the same everywhere. Lead with the answer, not a
    preamble; put a one-line summary first (counts, the headline fact),
    then supporting detail below it, so the gist is visible without
    reading the whole message. One issue per line. Every group/section
    gets exactly one leading emoji as a visual anchor for the message
    *kind* (pick one consistently per kind of question, e.g. 📋 for a
    list, 🎫 for one issue, 👉 for a recommendation) -- don't invent a new
    emoji vocabulary per response or reuse one emoji for different
    meanings across responses. The only *data-driven* icon is priority
    (🔴 High/Highest, 🟡 Medium, 🟢 Low/Lowest) -- never invent a
    status-to-emoji mapping, since status names and their meaning differ
    per project's workflow (rule 11); a status name is just bolded plain
    text as a group header.

    Grouped/bulk list (`search`, `triage`, `my_work` with several results):
    ```
    📋 <project> — <what this is> (<total count>)
    <n> active · <n> in review · <n> backlog unassigned  <- whatever counts matter here

    <Status name> (<count>)
    🔴 [KEY](url) <summary> — <assignee>
    🟡 [KEY](url) <summary> — <assignee>

    <Next status name> (<count>)
    ...
    ```

    Single issue (`issue_summary`, `blockers`, `get_issue`):
    ```
    🎫 [KEY](url) — <summary>
    🔴 <priority> · <status> · <assignee>

    🔗 Blocked by [KEY](url) (<its status>)   <- only if actually blocked, rule 3
    ⏱ <logged> / <estimate> logged
    💬 "<latest comment text>" — <relative time>
    ```
    Omit any line above that doesn't apply (no blockers, no worklogs, no
    comments) rather than printing an empty or "none" line for each.

    Recommendation (`my_work` reasoned into "what should I work on
    next"):
    ```
    👉 Do next: [KEY](url)
    <summary>
    <the 1-2 reasons -- priority, unblocked, staleness>
    ```
    A ranked runner-up list may follow underneath if useful, using the
    grouped-list line format above.

    These are shapes to adapt, not rigid schemas -- use judgment on which
    fields matter for the question asked, but keep the one-summary-line-
    then-detail structure and the single-icon-per-role rule above.
14. **Stay scoped to the current project; ask before broadening.**
    `my_work`, `sprint`, and `kanban_status` all default to
    `JIRA_DEFAULT_PROJECT` (or an explicit `--project`) rather than
    searching instance-wide -- don't pass `--all_projects` (`my_work`) or
    an unscoped `search`/`search_users` call just because a scoped result
    looks short or empty. If a scoped result is genuinely empty or
    doesn't answer the question, tell the user what you searched (state
    the project and query) and ask whether to broaden, rather than
    silently retrying wider or mixing in other projects' issues. This
    also means: don't assume every project is a Scrum board with sprints
    -- a project can be Kanban-only (`sprint` returns `"note"` saying so
    when it detects this; use `kanban_status` for that board's real
    state instead), so a missing/ended sprint on the default project
    isn't evidence there's no work to report, it's evidence to check
    `kanban_status` or a plain `my_work`/`search` instead.

## Commands

```bash
# Unresolved issues assigned to the current user. Scoped to --project (or
# JIRA_DEFAULT_PROJECT) by default (rule 14) -- pass --all_projects only if
# the user asked to broaden. --order_by is a JQL ORDER BY clause (default:
# "priority DESC, updated DESC"); --max_results caps how many come back.
# Use these instead of fetching everything and post-processing yourself --
# e.g. "what's the last task I worked on" is --order_by "updated DESC"
# --max_results 1, not a second script.
python3 scripts/jira_tool.py my_work [--project PAY] [--all_projects] \
  [--order_by "updated DESC"] [--max_results 1]

# Full context for one issue: fields, comments, worklogs, changelog, links.
# --sections limits which parts to fetch/return (default: all)
python3 scripts/jira_tool.py issue_summary --issue_key PAY-123 [--sections issue,worklogs]

# Blocking status + reasons for one issue
python3 scripts/jira_tool.py blockers --issue_key PAY-123

# Arbitrary JQL search. --only asks for exactly the named fields you need
# instead of everything (default: everything except description and
# time-tracking fields); "blocked" is always computed and returned.
# --only's names and --jql's field names are DIFFERENT vocabularies --
# see rule 11 (e.g. --jql uses "due", --only uses "due_date")
python3 scripts/jira_tool.py search --jql "assignee = currentUser() AND updated <= -14d" \
  [--fields customfield_10056] [--only summary,status,priority]

# Enumerate every field (incl. custom fields) to discover a custom field's id by name
python3 scripts/jira_tool.py list_fields

# Reference snapshot of a project: issue types, workflow statuses (overall
# and per issue type), components, instance priorities, assignable users,
# and a sample of labels in use -- call once per project, remember the
# result if you can (rule 12), don't re-fetch every turn
python3 scripts/jira_tool.py project_context [--project PAY]

# Look up a user by name/email fragment, to get an account_id for JQL
# assignee filters or create_issue/edit_issue's --assignee_account_id.
# --project scopes to that project's assignable users (narrower, resolves
# common-name collisions) -- falls back to JIRA_DEFAULT_PROJECT, then
# an unscoped instance-wide search
python3 scripts/jira_tool.py search_users --query john [--project PAY] [--all_projects]

# Active sprint / board / dates / goal. Board is resolved scoped to
# --project (or JIRA_DEFAULT_PROJECT) by default (rule 14). If the
# resolved board is kanban (no sprints), "sprint" comes back null with a
# "note" pointing at kanban_status instead.
python3 scripts/jira_tool.py sprint [--project PAY] [--board_id 42]

# Kanban board's columns and per-column issue counts -- the kanban
# equivalent of "sprint" for boards with no active sprint. Board scoped
# the same way as sprint (rule 14).
python3 scripts/jira_tool.py kanban_status [--project PAY] [--board_id 42]

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
Run `my_work` (scoped to `JIRA_DEFAULT_PROJECT`/`--project` by default,
rule 14). Reason over the returned `issues` (priority, status, `blocked`,
staleness) and recommend the best candidate using the recommendation
template (rule 13) -- lead with the pick and why, don't just dump the JSON
or bury the answer at the end of a ranked list. If `issues` is empty,
don't assume there's nothing to do -- check `sprint` for that project: if
its `"note"` says the board is kanban, or the sprint has ended, that's
not "no work", it's a reason to check `kanban_status` (or a plain
`my_work`/`search`) instead of telling the user they're done.

**"What's the last task I worked on?"**
Run `my_work --order_by "updated DESC" --max_results 1` -- it comes back
sorted with exactly the one issue you need, no further sorting or
scripting required (rule 9). Report it using the single-issue template
(rule 13).

**"What should I work on tomorrow?" (default project is kanban)**
Run `my_work` (rule 14 keeps it scoped to `JIRA_DEFAULT_PROJECT`). Don't
also reach for `sprint` first just because "tomorrow" sounds like a
planning question -- kanban projects have no sprints, so a "sprint
ended"/`null` result from `sprint` is expected there, not a sign
something's wrong or that `my_work` will come up empty too. If `my_work`
does come back empty, check `kanban_status` for that project's real board
state before concluding there's nothing to do.

**"What's blocking my board right now?" / "How many tickets are in review?"**
Run `kanban_status [--project PAY]`. Report `issue_counts_by_column`
against the board's real `columns` -- never assume a generic To Do/In
Progress/Done set; use the names the board actually returned.

**"Show me the backend tasks, grouped by status."**
Run `search --jql 'project = PAY AND labels = "backend"' --only
status,assignee,priority,summary`. The grouping itself is just reading the
returned list and organizing it by each issue's `status` field into the
grouped-list template (rule 13) -- one summary line up top, one status
group per section, every key linked (rule 8) -- reason over the JSON
directly, per rule 9. Never write a Python/jq script (piped, heredoc, or
`-c`) to sort/group/tabulate a result you already have in hand; besides
being unnecessary, that class of command is exactly what a security
scanner (Hermes' included) flags and blocks for approval.

**"What's blocking PAY-412?"**
Run `blockers --issue_key PAY-412`. If `blocked: true`, summarize
`reasons` using the single-issue template's 🔗 line (rule 13). If
`false`, say nothing is blocking it.

**"Summarize PAY-412."**
Run `issue_summary --issue_key PAY-412`. Produce a concise summary using
the single-issue template (rule 13): status/priority/assignee up top,
then only the sections that actually apply (blockers, worklogs, latest
comment) -- not a full dump of every field.

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
against the project's workflow first if unsure -- check `project_context`'s
`statuses` if you already have it for this project, otherwise fetch it,
per rules 11-12).

**"What statuses/labels does this project use?" / "Who's on this project?"**
Run `project_context --project PAY` (falls back to `JIRA_DEFAULT_PROJECT`).
Report `statuses`/`statuses_by_issue_type`, `labels` (note it's a sample
from unresolved issues, not exhaustive -- say so if asked "all labels"),
or `users` directly as fact. Remember the result per rule 12 rather than
calling this again later in the same project unless you have reason to
think it changed.

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
Per rule 9, chain `search_users` + `search` rather than writing new code --
but check remembered/already-fetched `project_context` first (rule 12): if
you already know this project's `users` and "John" unambiguously matches
one, use that `account_id` directly and skip `search_users` entirely.
Otherwise run `search_users --query john` (add `--project` if a project is
already known/relevant -- narrows the match and often resolves a
common-name collision on its own). If the scoped search comes back with
`count: 0`
(check the result's `project` field, not just what you passed, since
`JIRA_DEFAULT_PROJECT` may have applied silently), don't conclude there's
no such user -- ask the user whether to broaden to an instance-wide search
and only then retry with `--all_projects` (omitting `--project` isn't
enough to bypass `JIRA_DEFAULT_PROJECT`). If still ambiguous after a
scoped attempt, ask the user to disambiguate. Once resolved, resolve
"tomorrow" to an actual calendar date yourself, then run
`search --jql "assignee = <account_id> AND reporter = currentUser() AND due = <date>"`
-- note `reporter` and `due`, per rule 11: don't drift to `creator` or
`due_date` if this returns nothing, that's guessing, not verifying.

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
