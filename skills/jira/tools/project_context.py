"""project_context: a reference snapshot of a project's workflow.

Thin tool: delegates entirely to the shared JiraClient. Exists so the LLM
can fetch a project's real issue types, statuses, components, priorities,
assignable users, and in-use labels in one shot -- to remember (via its
own runtime's persistent-memory feature, if any) and consult before
guessing a status/label/name a user mentioned, instead of inventing a
plausible-sounding value or re-querying Jira every turn for facts that
rarely change.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from lib.jira_client import get_client
from tools._common import run_tool


def project_context(project: Optional[str] = None) -> Dict[str, Any]:
    """Return a project's identity, workflow, and team as one reference document.

    Args:
        project: Jira project key, e.g. ``PAY``. Falls back to
            ``JIRA_DEFAULT_PROJECT`` if omitted; errors if neither is
            available.

    Returns:
        ``{"project": "PAY", "name": ..., "lead": ..., "issue_types": [...],
           "statuses": [...], "statuses_by_issue_type": {"Bug": [...], ...},
           "components": [...], "priorities": [...],
           "users": [{"account_id", "display_name", "email", "active"}, ...],
           "labels": [...]}``.

        ``labels`` is a sample drawn from unresolved issues, not an
        exhaustive list -- Jira has no endpoint that enumerates every label
        ever used in a project. ``priorities`` is instance-wide (Jira
        priority schemes are rarely project-specific), in Jira's own
        configured order.
    """

    def _run() -> Dict[str, Any]:
        client = get_client()
        return client.project_context(project=project)

    return run_tool("project_context", _run)
