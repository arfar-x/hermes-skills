"""edit_issue: update fields on an existing issue or subtask.

Thin tool: validates input and delegates to the shared JiraClient. This is
a write operation and follows the same confirmation gate as worklog() and
transition(). Works on subtasks the same way as parent issues -- pass the
subtask's own issue_key.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.jira_client import get_client
from tools._common import ToolInputError, require_str, run_tool


def edit_issue(
    issue_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignee_account_id: Optional[str] = None,
    priority: Optional[str] = None,
    components: Optional[List[str]] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Update one or more fields on an existing issue (or subtask).

    Args:
        issue_key: Issue key, e.g. ``PAY-412``.
        summary: New title (omit to leave unchanged).
        description: New plain-text description (omit to leave unchanged).
        labels: New label list, replacing the existing one (omit to leave
            unchanged).
        assignee_account_id: A user's ``account_id`` -- resolve a name via
            ``search_users`` first, never guess it from a display name.
        priority: New priority name, e.g. ``"High"``.
        components: New component name list, replacing the existing one.
        confirm: Must be ``True`` (or JIRA_AUTO_CONFIRM_WRITES=true) for
            the edit to actually execute. Hermes should set this only
            after the user has explicitly confirmed the action.

    Returns:
        On success: ``{"confirmed": true, "issue": {...}}``.
        When confirmation is required first: ``{"confirmed": false,
        "requires_confirmation": true, "pending_action": {...}}``.
    """

    def _run() -> Dict[str, Any]:
        key = require_str(issue_key, "issue_key")

        if (
            summary is None
            and description is None
            and labels is None
            and assignee_account_id is None
            and priority is None
            and components is None
        ):
            raise ToolInputError(
                "At least one of 'summary', 'description', 'labels', "
                "'assignee_account_id', 'priority', or 'components' must be provided."
            )

        client = get_client()

        if not confirm and not client.config.auto_confirm_writes:
            return {
                "confirmed": False,
                "requires_confirmation": True,
                "pending_action": {
                    "action": "edit_issue",
                    "issue_key": key,
                    "summary": summary,
                    "description": description,
                    "labels": labels,
                    "assignee_account_id": assignee_account_id,
                    "priority": priority,
                    "components": components,
                },
            }

        updated = client.edit_issue(
            key,
            summary=summary,
            description=description,
            labels=labels,
            assignee_account_id=assignee_account_id,
            priority=priority,
            components=components,
        )
        return {"confirmed": True, "issue": updated.to_dict()}

    return run_tool("edit_issue", _run)
