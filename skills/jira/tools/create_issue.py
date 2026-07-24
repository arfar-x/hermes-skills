"""create_issue: create a new Jira issue -- a parent work item or a subtask.

Thin tool: validates input and delegates to the shared JiraClient. This is
a write operation and follows the same confirmation gate as worklog() and
transition(). Pass issue_type="Sub-task" and parent_key to create a
subtask instead of a parent issue -- there is no separate subtask tool.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import get_client
from tools._common import require_str, run_tool


def create_issue(
    project: str,
    summary: str,
    issue_type: str,
    description: Optional[str] = None,
    parent_key: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignee_account_id: Optional[str] = None,
    priority: Optional[str] = None,
    components: Optional[List[str]] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Create a new issue.

    Args:
        project: Project key, e.g. ``PAYKAN``.
        summary: Issue title.
        issue_type: e.g. ``"Story"``, ``"Bug"``, ``"Task"``, ``"Sub-task"``.
        description: Plain-text description.
        parent_key: Required when ``issue_type`` is ``"Sub-task"``.
        labels: Labels to apply, e.g. ``["Frontend"]``.
        assignee_account_id: A user's ``account_id`` -- resolve a name via
            ``search_users`` first, never guess it from a display name.
        priority: Priority name, e.g. ``"High"``.
        components: Component names.
        confirm: Must be ``True`` (or JIRA_AUTO_CONFIRM_WRITES=true) for
            the issue to actually be created. Hermes should set this only
            after the user has explicitly confirmed the action.

    Returns:
        On success: ``{"confirmed": true, "issue": {...}}``.
        When confirmation is required first: ``{"confirmed": false,
        "requires_confirmation": true, "pending_action": {...}}``.
    """

    def _run() -> Dict[str, Any]:
        proj = require_str(project, "project")
        summ = require_str(summary, "summary")
        itype = require_str(issue_type, "issue_type")
        client = get_client()

        if not confirm and not client.config.auto_confirm_writes:
            return {
                "confirmed": False,
                "requires_confirmation": True,
                "pending_action": {
                    "action": "create_issue",
                    "project": proj,
                    "summary": summ,
                    "issue_type": itype,
                    "description": description,
                    "parent_key": parent_key,
                    "labels": labels,
                    "assignee_account_id": assignee_account_id,
                    "priority": priority,
                    "components": components,
                },
            }

        created = client.create_issue(
            proj,
            summ,
            itype,
            description=description,
            parent_key=parent_key,
            labels=labels,
            assignee_account_id=assignee_account_id,
            priority=priority,
            components=components,
        )
        return {"confirmed": True, "issue": created.to_dict()}

    return run_tool("create_issue", _run)
