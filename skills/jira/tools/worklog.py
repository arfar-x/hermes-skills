"""worklog: submit a worklog entry against an issue.

Thin tool: validates input, parses the duration, and delegates to the
shared JiraClient. This is a write operation -- per the skill's prompting
rules, Hermes must ask the user for confirmation before calling this tool
unless auto-confirm is configured. As a safety net independent of prompt
adherence, the tool itself also refuses to execute without `confirm=True`
unless JIRA_AUTO_CONFIRM_WRITES is enabled.
"""

from __future__ import annotations

from typing import Any, Dict

from lib.jira_client import get_client
from lib.utils import InvalidDurationError, parse_duration_to_seconds
from tools._common import ToolInputError, require_str, run_tool


def worklog(issue_key: str, duration: str, description: str, confirm: bool = False) -> Dict[str, Any]:
    """Submit a worklog entry.

    Args:
        issue_key: Issue key, e.g. ``PAY-412``.
        duration: Jira-style duration string, e.g. ``"2h"``, ``"1d 30m"``.
        description: Free-text description of the work performed.
        confirm: Must be ``True`` (or JIRA_AUTO_CONFIRM_WRITES=true) for
            the worklog to actually be submitted. Hermes should set this
            only after the user has explicitly confirmed the action.

    Returns:
        On success: ``{"confirmed": true, "issue_key": ..., "worklog": {...}}``.
        When confirmation is required first: ``{"confirmed": false,
        "requires_confirmation": true, "pending_action": {...}}``.
    """

    def _run() -> Dict[str, Any]:
        key = require_str(issue_key, "issue_key")
        desc = require_str(description, "description")
        if not isinstance(duration, str) or not duration.strip():
            raise ToolInputError("'duration' is required, e.g. '2h', '1d 30m'.")

        try:
            seconds = parse_duration_to_seconds(duration)
        except InvalidDurationError as exc:
            raise ToolInputError(str(exc)) from exc

        client = get_client()

        if not confirm and not client.config.auto_confirm_writes:
            return {
                "confirmed": False,
                "requires_confirmation": True,
                "pending_action": {
                    "action": "worklog",
                    "issue_key": key,
                    "duration": duration,
                    "duration_seconds": seconds,
                    "description": desc,
                },
            }

        created = client.add_worklog(key, seconds, desc)
        return {"confirmed": True, "issue_key": key, "worklog": created.to_dict()}

    return run_tool("worklog", _run)
