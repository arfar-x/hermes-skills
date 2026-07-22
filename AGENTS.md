# Agent instructions

This repo holds Hermes Agent skills, not an application. There is no
build step and no server to run -- "testing a change" means running the
relevant skill's pytest suite.

## Repo layout

- `skills/jira/` -- the actual implementation: `lib/` (Jira REST client,
  env-based config), `tools/` (thin per-tool entry points), `scripts/jira_tool.py`
  (CLI dispatcher), `tests/`.
- `skills/jira-*/` -- thin `SKILL.md`-only skills, one per tool, that
  shell out to `../jira/scripts/jira_tool.py`. They exist purely so each
  tool gets its own Hermes slash command; they contain no Python of
  their own and nothing to test.

When changing behavior (auth, request handling, tool output shape),
edit `skills/jira/lib/` or `skills/jira/tools/`, then update
`skills/jira/tests/` and run:

```bash
cd skills/jira
pip install -r requirements.txt pytest
pytest -q
```

When changing a tool's CLI flags or output, update every `jira-*/SKILL.md`
that documents that tool's invocation -- they hardcode example commands
and are not generated from `scripts/jira_tool.py`'s argparse definitions.

## Conventions

- **Auth is Basic-only** (`JIRA_USERNAME` + `JIRA_PASSWORD`). There is no
  PAT/bearer-token mode -- don't reintroduce one without being asked.
- **Credentials only ever come from environment variables**, never
  hard-coded, never logged in plaintext.
- **No hardcoded local filesystem paths** in any `SKILL.md`, `README.md`,
  or Python source -- this repo is public. Use `../jira/...`-relative
  paths or a generic `/path/to/...` placeholder in docs.
- **Write operations (`worklog`, `transition`) are confirmation-gated in
  code**, not just prompted -- they refuse to execute without `--confirm`
  unless `JIRA_AUTO_CONFIRM_WRITES=true`. Preserve this if touching
  `tools/worklog.py` or `tools/transition.py`.
- Each skill's `required_environment_variables` frontmatter must list
  every env var that tool's code path actually reads -- Hermes uses that
  list to decide which vars are allowed to pass through to the sandboxed
  `terminal` tool that runs `jira_tool.py`. An unlisted var will be
  silently stripped at runtime, not just undocumented.
