"""triage: group unresolved parent issues (Story/Bug/Task/...) with their
subtasks, so the LLM can determine which ones still need frontend/backend
work, design-readiness, or haven't been broken into subtasks yet.

Thin tool: the grouping of subtasks under their parent (and the
frontend/backend label check) is deterministic bookkeeping done here, but
whether a parent *without* subtasks needs frontend/backend/design work is
never decided here -- that's inferred by the LLM from ``description`` (or
``summary`` if there's no description), per this skill's SKILL.md.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import get_client
from tools._common import run_tool


def triage(
    project: Optional[str] = None,
    parent_issue_types: Optional[List[str]] = None,
    max_results: int = 200,
) -> Dict[str, Any]:
    """Group unresolved parent issues with their labeled subtasks.

    Args:
        project: Jira project key (e.g. ``PAYKAN``). Falls back to
            ``JIRA_DEFAULT_PROJECT`` if omitted; errors if neither is set.
        parent_issue_types: Issue types treated as "parent" work items.
            Defaults to ``["Story", "Bug", "Task"]``.
        max_results: Safety cap on parent issues scanned.

    Returns:
        ``{"project": ..., "issue_count": N, "stories": [...]}`` -- see
        ``JiraClient.triage`` for the full shape.
    """

    def _run() -> Dict[str, Any]:
        client = get_client()
        return client.triage(
            project=project, parent_issue_types=parent_issue_types, max_results=max_results
        )

    return run_tool("triage", _run)
