"""sprint: report the active sprint, its board, dates, and goal.

Thin tool: delegates entirely to the shared JiraClient's agile endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from lib.jira_client import get_client
from tools._common import run_tool


def sprint(board_id: Optional[int] = None) -> Dict[str, Any]:
    """Return the active sprint for a board.

    Args:
        board_id: Optional explicit board id. When omitted, the first
            board visible to the authenticated user is used.

    Returns:
        ``{"board": {...}, "sprint": {...} | null}``
    """

    def _run() -> Dict[str, Any]:
        client = get_client()
        board = client.current_board() if board_id is None else None
        resolved_board_id = board_id if board_id is not None else (board.id if board else None)

        active_sprint = client.current_sprint(resolved_board_id) if resolved_board_id is not None else None

        return {
            "board": board.to_dict() if board else ({"id": resolved_board_id} if resolved_board_id else None),
            "sprint": active_sprint.to_dict() if active_sprint else None,
        }

    return run_tool("sprint", _run)
