"""Shared plumbing for tool entry points (not itself a tool).

Centralizes error-to-JSON conversion and input validation helpers so that
individual tool modules stay thin and never duplicate this logic.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from lib.jira_client import JiraApiError

logger = logging.getLogger("jira_skill.tools")


class ToolInputError(ValueError):
    """Raised by tools when caller-supplied arguments are invalid."""


def run_tool(tool_name: str, fn: Callable[[], Any]) -> Any:
    """Execute a tool body, normalizing all errors into structured JSON.

    Every tool entry point should return JSON even on failure -- the LLM
    must never receive a raw traceback. Errors are surfaced as
    ``{"error": {"type": ..., "message": ...}}`` so the model can react
    (e.g. ask the user to clarify) instead of hallucinating a result.
    """
    try:
        result = fn()
        logger.info("Tool %s succeeded", tool_name)
        return result
    except ToolInputError as exc:
        logger.warning("Tool %s rejected invalid input: %s", tool_name, exc)
        return {"error": {"type": "invalid_input", "message": str(exc)}}
    except JiraApiError as exc:
        logger.error("Tool %s failed calling Jira: %s", tool_name, exc)
        return {
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "status_code": exc.status_code,
            }
        }
    except Exception as exc:  # noqa: BLE001 - last-resort safety net for a tool boundary
        logger.exception("Tool %s failed unexpectedly", tool_name)
        return {"error": {"type": "internal_error", "message": str(exc)}}


def require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"'{field_name}' is required and must be a non-empty string.")
    return value.strip()
