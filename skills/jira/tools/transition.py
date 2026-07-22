"""transition: move an issue to a requested status.

Thin tool: delegates transition-id resolution and execution to the shared
JiraClient. This is a write operation and follows the same confirmation
gate as worklog().
"""

from __future__ import annotations

from typing import Any, Dict

from lib.jira_client import get_client
from tools._common import require_str, run_tool


def transition(issue_key: str, status: str, confirm: bool = False) -> Dict[str, Any]:
    """Move an issue to a new status.

    Args:
        issue_key: Issue key, e.g. ``PAY-412``.
        status: Desired transition or target status name, e.g. ``"Review"``.
            Transition IDs are resolved automatically.
        confirm: Must be ``True`` (or JIRA_AUTO_CONFIRM_WRITES=true) for
            the transition to actually execute. Hermes should set this
            only after the user has explicitly confirmed the action.

    Returns:
        On success: ``{"confirmed": true, "issue_key": ..., "transitioned_to": ...}``.
        When confirmation is required first: ``{"confirmed": false,
        "requires_confirmation": true, "pending_action": {...}}``.
    """

    def _run() -> Dict[str, Any]:
        key = require_str(issue_key, "issue_key")
        target = require_str(status, "status")
        client = get_client()

        if not confirm and not client.config.auto_confirm_writes:
            return {
                "confirmed": False,
                "requires_confirmation": True,
                "pending_action": {"action": "transition", "issue_key": key, "status": target},
            }

        result = client.transition_issue(key, target)
        return {"confirmed": True, **result}

    return run_tool("transition", _run)
