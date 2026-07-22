# Jira Assistant (Hermes Skill)

A production-ready Hermes skill that lets an LLM act as a high-level Jira
assistant -- answering questions like "what should I work on next?" or
"what's blocking PAY-123?" -- without ever exposing raw Jira REST APIs to
the model.

## Design

- **Thin tools, smart model.** Every tool in `tools/` only validates
  input, calls the shared Jira client, and returns structured JSON. No
  tool summarizes, prioritizes, or explains -- that reasoning happens in
  the agent, guided by `SKILL.md`.
- **One Jira client.** `lib/jira_client.py` is the only code in this
  skill that talks HTTP to Jira. It owns authentication, retries,
  pagination, rate-limit handling, error normalization, and optional
  response caching. No tool constructs its own HTTP request.
- **Deterministic "blocked" logic shared everywhere.** `lib/utils.py`
  defines the single rule set for what counts as "blocked" (status flags,
  unresolved "blocked by" links, flagged comments). `blockers()` and
  `my_work()` both use it, so they can never disagree.
- **Write operations are gated.** `worklog()` and `transition()` refuse
  to execute unless called with `confirm=true` (CLI: `--confirm`), or
  `JIRA_AUTO_CONFIRM_WRITES=true` is set. This backs up `SKILL.md`'s
  confirmation rule with an enforced safety net in code.

## Project layout

```
skills/jira/
├── SKILL.md                # Hermes manifest: frontmatter + agent instructions
├── scripts/
│   └── jira_tool.py         # CLI dispatcher the agent runs via `terminal`
├── prompts/                 # Source material SKILL.md was authored from
│   ├── system.md
│   └── examples.md
├── tools/                   # Thin, agent-facing entry points (Python functions)
│   ├── my_work.py
│   ├── issue_summary.py
│   ├── blockers.py
│   ├── worklog.py
│   ├── transition.py
│   ├── search.py
│   └── sprint.py
├── lib/                     # Shared implementation, not directly agent-facing
│   ├── jira_client.py       # The single Jira REST client
│   ├── auth.py              # Env-based configuration + validation
│   ├── models.py            # Typed, JSON-serializable data models
│   └── utils.py             # Duration parsing, ADF text extraction, blocking rules
├── skill.yaml                # Generic tool-schema manifest, kept for non-Hermes
│                              # integrations that consume function-calling schemas
└── tests/                    # Unit tests for the client and every tool
```

## Configuration

All configuration comes from environment variables. **No credentials are
ever hard-coded.**

| Variable | Required | Default | Description |
|---|---|---|---|
| `JIRA_BASE_URL` | Yes | -- | Root URL of your Jira instance, e.g. `https://jira.mycompany.com` |
| `JIRA_USERNAME` | Yes | -- | Basic-auth username |
| `JIRA_PASSWORD` | Yes | -- | Basic-auth password |
| `JIRA_TIMEOUT_SECONDS` | No | `30` | Per-request timeout |
| `JIRA_MAX_RETRIES` | No | `3` | Retries for `429`/`5xx` responses |
| `JIRA_VERIFY_SSL` | No | `true` | Disable only for trusted self-signed internal instances |
| `JIRA_AUTO_CONFIRM_WRITES` | No | `false` | Skip the confirmation gate for `worklog`/`transition` |
| `JIRA_CACHE_TTL_SECONDS` | No | `0` | Optional TTL cache for idempotent GET requests; `0` disables caching |

Configuration is validated eagerly: `lib.auth.load_config()` raises a
`ConfigurationError` with a specific, actionable message if required
variables are missing (e.g. `JIRA_PASSWORD` not set). Wire this into
your Hermes installation's startup/health check so misconfiguration
fails fast instead of at first tool call.

This skill only supports HTTP Basic auth (`JIRA_USERNAME` +
`JIRA_PASSWORD`), which works against both Jira Cloud and self-hosted
Jira Server/Data Center.

## Tools

| Tool | Read/Write | Description |
|---|---|---|
| `my_work()` | Read | Unresolved issues assigned to the current user |
| `issue_summary(issue_key)` | Read | Issue + comments + worklogs + changelog + links, as one document |
| `blockers(issue_key)` | Read | `{"blocked": bool, "reasons": [...]}` from links/status/comments |
| `search(jql)` | Read | Arbitrary JQL, structured issue results |
| `transition(issue_key, status, confirm)` | Write (gated) | Move an issue to a status; transition IDs resolved automatically |
| `worklog(issue_key, duration, description, confirm)` | Write (gated) | Log time against an issue |
| `sprint(board_id)` | Read | Active sprint, board, dates, and goal |

Each tool is reachable both as a Python function (`tools/<name>.py`) and
as a CLI subcommand (`scripts/jira_tool.py <name>`). See `skill.yaml` for
exact JSON Schemas and `SKILL.md` for the CLI invocation the agent uses.

## Running tests

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
```

Tests mock the HTTP layer (`requests.Session`) so they run without a real
Jira instance, and cover: configuration validation, duration/ADF
parsing, blocking-rule logic, pagination, error-code mapping (401/403/
404/429/5xx), transition resolution, and every tool's success/validation/
confirmation-gate paths.

## Installing into Hermes

This is a manual, one-time setup step that a human operator performs in
their own local Hermes installation. Nothing in this repository -- no
script, no `SKILL.md` instruction, no tool -- edits Hermes configuration
on its own; the steps below are for you to carry out by hand.

Hermes discovers skills as `SKILL.md`-fronted directories, either under
`~/.hermes/skills/<skill-name>/` or under a directory of your own
choosing that you list in your local Hermes settings (see Hermes' own
docs for the exact setting name). Doing the latter and pointing it at
the `skills/` directory that contains `jira/` means you don't
need to copy this repo anywhere -- it's available immediately, with live
edits.

1. In your own Hermes settings file, list the absolute path to this
   repo's `skills/` directory under the setting that holds
   operator-defined skill locations, for example:

   ```yaml
   skills:
     external_dirs:
       - /path/to/your/local/checkout/of/hermes-jira/skills
   ```

2. Install dependencies (into whatever Python environment Hermes' sandbox
   uses to run `terminal`/`execute_code`):

   ```bash
   pip install -r /path/to/your/local/checkout/of/hermes-jira/skills/jira/requirements.txt
   ```

3. Set the environment variables from the table above wherever Hermes'
   sandbox inherits its environment (`SKILL.md`'s
   `required_environment_variables` will also prompt for them on first
   use if Hermes' onboarding flow supports it).

4. In a Hermes chat, run `/skills` to confirm `jira` is listed,
   or invoke it directly with `/jira`.

Alternatively, if your Hermes deployment can't use `external_dirs` (e.g.
a remote/managed instance), install by copying:
`cp -r skills/jira ~/.hermes/skills/jira`. Note this
creates a disconnected copy -- future changes to this repo won't apply
until you re-copy.

Hermes' skill mechanism (`SKILL.md` + on-demand instructions run via its
own `terminal` tool) is different from the generic function-calling
`skill.yaml` manifest also included here -- that file is kept for any
other agent runtime you might integrate with that expects structured
tool schemas instead of a markdown-instructed CLI.
