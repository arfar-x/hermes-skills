"""blockers: report whether an issue is blocked, and why, in structured form.

Thin tool: retrieves the issue (for links/status) and its comments, applies
the shared deterministic blocking rules from lib.utils, and returns JSON
only. It does not explain or narrate -- the LLM turns `reasons` into prose.
"""

from __future__ import annotations

from typing import Any, Dict

from lib.jira_client import get_client
from lib.utils import blocking_reasons
from tools._common import require_str, run_tool

#: Substring markers in comment text that flag a manually-reported blocker
#: (comments are free text, so this is best-effort, not authoritative).
_COMMENT_BLOCK_MARKERS = ("blocked by", "waiting on", "blocked on")


def _comment_reasons(issue_key: str, comments) -> list:
    reasons = []
    for comment in comments:
        body_lower = (comment.body or "").lower()
        if any(marker in body_lower for marker in _COMMENT_BLOCK_MARKERS):
            reasons.append(f"Comment by {comment.author or 'unknown'} on {comment.created}: {comment.body.strip()}")
    return reasons


def blockers(issue_key: str) -> Dict[str, Any]:
    """Return blocking status and reasons for a single issue.

    Args:
        issue_key: Issue key, e.g. ``PAY-412``.

    Returns:
        ``{"issue_key": "...", "blocked": bool, "reasons": [str, ...]}``
    """

    def _run() -> Dict[str, Any]:
        key = require_str(issue_key, "issue_key")
        client = get_client()
        issue = client.get_issue(key)
        comments = client.get_comments(key)

        reasons = blocking_reasons(issue) + _comment_reasons(key, comments)
        return {
            "issue_key": issue.key,
            "blocked": len(reasons) > 0,
            "reasons": reasons,
        }

    return run_tool("blockers", _run)
