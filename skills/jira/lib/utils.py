"""Small stateless helpers shared across the Jira client and tools.

Keeping these in one place avoids duplicating parsing/formatting logic
across tool modules (each tool should stay a thin wrapper).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .models import Issue

_DURATION_RE = re.compile(
    r"""
    ^\s*
    (?:(?P<weeks>\d+(?:\.\d+)?)\s*w)?\s*
    (?:(?P<days>\d+(?:\.\d+)?)\s*d)?\s*
    (?:(?P<hours>\d+(?:\.\d+)?)\s*h)?\s*
    (?:(?P<minutes>\d+(?:\.\d+)?)\s*m)?\s*
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Jira's default working-time conventions, used to convert weeks/days to seconds.
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 60 * _SECONDS_PER_MINUTE
_SECONDS_PER_DAY = 8 * _SECONDS_PER_HOUR
_SECONDS_PER_WEEK = 5 * _SECONDS_PER_DAY


class InvalidDurationError(ValueError):
    """Raised when a worklog duration string cannot be parsed."""


def parse_duration_to_seconds(duration: str) -> int:
    """Parse a Jira-style duration string (e.g. "2h", "1d 4h", "45m") into seconds.

    Follows Jira's default time-tracking convention: 1d = 8h, 1w = 5d.

    Raises:
        InvalidDurationError: If the string does not match Jira duration syntax
            or evaluates to zero seconds.
    """
    if not duration or not duration.strip():
        raise InvalidDurationError("Duration must not be empty (e.g. '2h', '1d 30m').")

    match = _DURATION_RE.match(duration)
    if not match or not any(match.groupdict().values()):
        raise InvalidDurationError(
            f"Could not parse duration {duration!r}. Expected a format like "
            "'2h', '1d 4h', '30m', or '1w 2d'."
        )

    parts = match.groupdict()
    total_seconds = 0.0
    total_seconds += float(parts["weeks"] or 0) * _SECONDS_PER_WEEK
    total_seconds += float(parts["days"] or 0) * _SECONDS_PER_DAY
    total_seconds += float(parts["hours"] or 0) * _SECONDS_PER_HOUR
    total_seconds += float(parts["minutes"] or 0) * _SECONDS_PER_MINUTE

    if total_seconds <= 0:
        raise InvalidDurationError(f"Duration {duration!r} evaluates to zero seconds.")

    return int(total_seconds)


def normalize_jql_for_user(jql_fragment: str, current_user_token: str = "currentUser()") -> str:
    """Return the JQL fragment unchanged; kept as an explicit seam for future
    per-user JQL rewriting (e.g. substituting an explicit account id)."""
    return jql_fragment.replace("{currentUser}", current_user_token)


def adf_to_plain_text(node: Any) -> str:
    """Best-effort conversion of Atlassian Document Format (Jira Cloud comment
    bodies) into plain text. Falls back to str() for non-ADF (Jira Server/DC
    wiki-markup) bodies, which are already plain strings.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return str(node)

    if node.get("type") == "text":
        return str(node.get("text", ""))

    pieces = []
    for child in node.get("content", []) or []:
        pieces.append(adf_to_plain_text(child))

    text = "".join(pieces) if node.get("type") == "text" else " ".join(p for p in pieces if p)
    if node.get("type") in {"paragraph", "heading"}:
        text += "\n"
    return text.strip()


def safe_get(mapping: Optional[Dict[str, Any]], *path: str, default: Any = None) -> Any:
    """Safely walk a chain of nested dict keys, returning ``default`` on any miss."""
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current if current is not None else default


#: Statuses that mark an issue as explicitly blocked, independent of links.
BLOCKED_STATUS_NAMES = {"blocked", "on hold", "blocked/on hold"}

#: Substrings of a Jira link-type name that indicate a "blocked by" relationship.
BLOCKING_LINK_KEYWORDS = ("blocked by", "is blocked by")

#: Substrings of a status name that indicate the blocking issue is resolved,
#: and therefore no longer actually blocking anything.
DONE_STATUS_KEYWORDS = ("done", "closed", "resolved", "cancelled", "canceled")


def blocking_reasons(issue: "Issue") -> List[str]:
    """Return deterministic, rule-based reasons an issue is blocked.

    This is retrieval-shaped logic (fixed rules over structured link/status
    data), not LLM-style reasoning or prose explanation -- it is the single
    source of truth used by both ``blockers()`` and ``my_work()`` so the two
    tools never disagree about what "blocked" means.
    """
    reasons: List[str] = []
    status_name = (issue.status or "").strip().lower()
    if status_name in BLOCKED_STATUS_NAMES:
        reasons.append(f"Status is '{issue.status}'")

    for link in issue.links:
        link_type = (link.link_type or "").lower()
        if not any(kw in link_type for kw in BLOCKING_LINK_KEYWORDS):
            continue
        related_status = (link.related_status or "").lower()
        if any(done_kw in related_status for done_kw in DONE_STATUS_KEYWORDS):
            continue
        reasons.append(
            f"Blocked by {link.related_key} (status: {link.related_status or 'unknown'})"
        )

    return reasons


def is_issue_blocked(issue: "Issue") -> bool:
    """Return whether ``issue`` is blocked, per :func:`blocking_reasons`."""
    return len(blocking_reasons(issue)) > 0
