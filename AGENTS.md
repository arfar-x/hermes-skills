# Agent instructions

This repo holds AI-agent skills (Hermes, Claude Code, claude.ai), not an
application. There is no build step and no server to run -- "testing a
change" means running the relevant toolset's pytest suite. The repo is
meant to hold multiple unrelated toolsets over time (Jira today, e.g. a
company back-office toolset later), each following the same layout.

## Repo layout

Per toolset `<toolset>` (e.g. `jira`):

- `skills/<toolset>/` -- the actual implementation: `lib/` (REST client,
  env-based config), `tools/` (thin per-action entry points),
  `scripts/<toolset>_tool.py` (CLI dispatcher), `tests/`.
- `skills/<toolset>-*/` -- thin `SKILL.md`-only skills, one per action,
  that shell out to `../<toolset>/scripts/<toolset>_tool.py`. They exist
  purely so each action gets its own Hermes slash command; they contain
  no Python of their own and nothing to test.

When changing behavior (auth, request handling, tool output shape) for
a toolset, edit its `skills/<toolset>/lib/` or `skills/<toolset>/tools/`,
then update `skills/<toolset>/tests/` and run:

```bash
cd skills/<toolset>
pip install -r requirements.txt pytest
pytest -q
```

When changing an action's CLI flags or output, update every
`<toolset>-*/SKILL.md` that documents that action's invocation -- they
hardcode example commands and are not generated from the CLI
dispatcher's argparse definitions.

When adding a brand-new toolset, follow the "Adding a toolset" section
in the top-level `README.md`.

## Conventions

These apply repo-wide, to every toolset, not just Jira:

- **Credentials only ever come from environment variables**, never
  hard-coded, never logged in plaintext.
- **No hardcoded local filesystem paths** in any `SKILL.md`, `README.md`,
  or Python source -- this repo is public. Use `../<toolset>/...`-relative
  paths or a generic `/path/to/...` placeholder in docs.
- **Write/mutating operations are confirmation-gated in code**, not just
  prompted -- e.g. the Jira toolset's `worklog`/`transition` refuse to
  execute without `--confirm` unless `JIRA_AUTO_CONFIRM_WRITES=true`.
  Any new toolset with side-effecting actions must gate them the same
  way, with an equivalent explicit `--confirm`/`*_AUTO_CONFIRM_WRITES`
  escape hatch, not just instructions in the skill's markdown body.
- Each skill's `required_environment_variables` frontmatter must list
  every env var that its code path actually reads -- Hermes uses that
  list to decide which vars are allowed to pass through to the sandboxed
  `terminal` tool that runs the CLI. An unlisted var will be silently
  stripped at runtime, not just undocumented.
- **Agent/runtime-specific details belong in `SKILL.md`'s frontmatter
  (`metadata.hermes.*`, `required_environment_variables`), never in the
  skill's body prose, `prompts/`, or the tool-invocation instructions
  themselves.** E.g. don't write "run this via `terminal`" in a
  `SKILL.md` body -- that's Hermes' tool name, and the same instruction
  text is read by Claude Code and claude.ai too. Say "run this from the
  skill's directory" instead, and declare `requires_toolsets: [terminal]`
  in frontmatter for Hermes to key off of. This keeps one `SKILL.md` per
  action usable, unmodified, across every runtime -- only the manifest
  varies by consumer, not the instructions.

Toolset-specific conventions (e.g. "Jira auth is Basic-only, don't
reintroduce PAT without being asked") belong in that toolset's own
`skills/<toolset>/README.md`, not here.
