"""The single reusable Jira REST client.

Every tool in this skill talks to Jira exclusively through
:class:`JiraClient`. No other module may issue HTTP requests to Jira.
This centralizes authentication, retries, pagination, rate-limit handling,
error normalization, and (optional) response caching, so that behavior is
consistent everywhere and never duplicated.

Supports both Jira Cloud and self-hosted Jira Server / Data Center via an
explicit ``base_url``, using HTTP Basic auth (username + password).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import JiraConfig, load_config
from .models import (
    Board,
    ChangelogEntry,
    Comment,
    Issue,
    IssueLink,
    Sprint,
    Transition,
    User,
    Worklog,
)
from .utils import adf_to_plain_text, safe_get

logger = logging.getLogger("jira_skill.client")

DEFAULT_ISSUE_FIELDS = [
    "summary",
    "status",
    "priority",
    "issuetype",
    "assignee",
    "reporter",
    "updated",
    "created",
    "duedate",
    "labels",
    "issuelinks",
    "description",
    "components",
    "subtasks",
]

#: Maps every named field in Issue.to_dict() (excluding "key"/"url"/
#: "custom_fields", which are always present) to the raw Jira field key
#: needed to populate it. This is the lookup table behind
#: resolve_issue_fields() -- the mechanism that lets a tool ask Jira for,
#: and return to the caller, only the fields actually needed instead of a
#: fixed set, which is the main lever for keeping bulk results token-cheap.
ISSUE_FIELD_MAP: Dict[str, str] = {
    "summary": "summary",
    "status": "status",
    "priority": "priority",
    "issue_type": "issuetype",
    "assignee": "assignee",
    "reporter": "reporter",
    "updated": "updated",
    "created": "created",
    "due_date": "duedate",
    "labels": "labels",
    "links": "issuelinks",
    "description": "description",
    "components": "components",
    "subtasks": "subtasks",
    "original_estimate_seconds": "timeoriginalestimate",
    "time_spent_seconds": "timespent",
    "remaining_estimate_seconds": "timeestimate",
}

#: The output-field selection used when a caller doesn't specify one --
#: everything except "description" (free text, often the largest single
#: field on an issue) and the time-tracking fields (rarely needed outside
#: worklog_report, which requests them explicitly).
DEFAULT_OUTPUT_FIELDS = [
    "summary",
    "status",
    "priority",
    "issue_type",
    "assignee",
    "reporter",
    "updated",
    "created",
    "due_date",
    "labels",
    "links",
    "components",
    "subtasks",
]


def resolve_issue_fields(
    only: Optional[List[str]] = None,
    *,
    always_fetch: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """Translate a caller's named-field selection into what to fetch/return.

    Args:
        only: Named output fields (keys of ``ISSUE_FIELD_MAP``) to fetch
            from Jira and include in the response, e.g.
            ``["summary", "status", "priority"]``. ``None`` selects
            ``DEFAULT_OUTPUT_FIELDS``.
        always_fetch: Extra named fields to fetch from Jira (needed to
            compute something derived, e.g. "blocked" needs "status" and
            "links") without forcing them into the caller-visible output.

    Returns:
        ``(jira_fields, output_keys)`` -- pass ``jira_fields`` as
        ``search()``/``get_issue()``'s ``fields=``, and ``output_keys`` as
        ``Issue.to_dict(only=...)``'s ``only=``.

    Raises:
        JiraValidationError: If ``only`` contains an unrecognized name.
    """
    output_keys = list(only) if only is not None else list(DEFAULT_OUTPUT_FIELDS)
    unknown = [name for name in output_keys if name not in ISSUE_FIELD_MAP]
    if unknown:
        raise JiraValidationError(
            f"Unknown field(s) {unknown}. Valid fields: {sorted(ISSUE_FIELD_MAP)}."
        )
    fetch_keys = list(dict.fromkeys(output_keys + list(always_fetch or [])))
    jira_fields = [ISSUE_FIELD_MAP[name] for name in fetch_keys]
    return jira_fields, output_keys

#: Raw Jira field keys already surfaced as named Issue attributes. Any other
#: key present in a response's ``fields`` (e.g. a custom field like "Figma
#: Link", customfield_10056) is passed through into Issue.custom_fields
#: instead of being silently dropped -- this lets the LLM discover and
#: request instance-specific fields (via list_fields()) without the client
#: needing to know their names or IDs ahead of time.
_NAMED_ISSUE_FIELDS = frozenset(
    {
        "summary",
        "status",
        "priority",
        "issuetype",
        "assignee",
        "reporter",
        "updated",
        "created",
        "duedate",
        "labels",
        "issuelinks",
        "description",
        "components",
        "subtasks",
        "timeoriginalestimate",
        "timespent",
        "timeestimate",
    }
)


class JiraApiError(RuntimeError):
    """Base class for all Jira client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class JiraAuthError(JiraApiError):
    """Raised on 401/403 responses -- invalid or insufficient credentials."""


class JiraNotFoundError(JiraApiError):
    """Raised on 404 responses -- issue, board, or resource does not exist."""


class JiraRateLimitError(JiraApiError):
    """Raised when Jira rate limiting could not be resolved via retries."""


class JiraValidationError(JiraApiError):
    """Raised on 400 responses -- typically invalid JQL or field values."""


class _TTLCache:
    """A minimal thread-safe in-memory TTL cache for idempotent GET requests."""

    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class JiraClient:
    """High-level, typed client wrapping the Jira REST API.

    All public methods return the typed models defined in
    :mod:`lib.models` (or primitive JSON-safe structures) -- never raw
    Jira REST payloads. This is what lets every tool stay "thin": tools
    only validate input, call this client, and hand back the result.
    """

    API_V2 = "/rest/api/2"
    AGILE_V1 = "/rest/agile/1.0"

    def __init__(
        self,
        config: Optional[JiraConfig] = None,
        session: Optional[requests.Session] = None,
        cache_ttl_seconds: Optional[float] = None,
    ):
        self.config = config or load_config()
        self.session = session or self._build_session()
        if cache_ttl_seconds is None:
            cache_ttl_seconds = float(os.environ.get("JIRA_CACHE_TTL_SECONDS", "0") or 0)
        self._cache = _TTLCache(cache_ttl_seconds)
        logger.debug("JiraClient initialized against %s", self.config.base_url)

    # ------------------------------------------------------------------
    # Session / transport setup
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=self.config.max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST", "PUT", "DELETE"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

        session.auth = (self.config.username, self.config.password)
        session.verify = self.config.verify_ssl
        return session

    # ------------------------------------------------------------------
    # Low-level request plumbing
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        cache: bool = False,
    ) -> Any:
        url = f"{self.config.base_url}{path}"
        cache_key = f"{method}:{url}:{sorted((params or {}).items())}"

        if cache and method == "GET":
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", url)
                return cached

        logger.info("Jira request: %s %s", method, path)
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=self.config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise JiraApiError(
                f"Timed out contacting Jira at {url} after {self.config.timeout_seconds}s"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise JiraApiError(f"Could not connect to Jira at {self.config.base_url}: {exc}") from exc

        self._raise_for_status(response)

        if response.status_code == 204 or not response.content:
            result: Any = {}
        else:
            try:
                result = response.json()
            except ValueError as exc:
                raise JiraApiError(
                    f"Jira returned a non-JSON response ({response.status_code}) for {url}"
                ) from exc

        if cache and method == "GET":
            self._cache.set(cache_key, result)

        return result

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.ok:
            return

        status = response.status_code
        message = self._extract_error_message(response)

        if status == 401:
            raise JiraAuthError(
                f"Jira authentication failed (401). Check JIRA_USERNAME/JIRA_PASSWORD. "
                f"Details: {message}",
                status_code=status,
            )
        if status == 403:
            raise JiraAuthError(
                f"Jira denied access (403) -- the configured account lacks permission. "
                f"Details: {message}",
                status_code=status,
            )
        if status == 404:
            raise JiraNotFoundError(f"Jira resource not found (404): {message}", status_code=status)
        if status == 400:
            raise JiraValidationError(f"Jira rejected the request (400): {message}", status_code=status)
        if status == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise JiraRateLimitError(
                f"Jira rate limit exceeded (429) even after retries. "
                f"Retry-After={retry_after}. Details: {message}",
                status_code=status,
            )
        if status >= 500:
            raise JiraApiError(
                f"Jira server error ({status}) after exhausting retries: {message}",
                status_code=status,
            )
        raise JiraApiError(f"Unexpected Jira response ({status}): {message}", status_code=status)

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500] if response.text else response.reason

        messages = payload.get("errorMessages") or []
        errors = payload.get("errors") or {}
        parts = list(messages) + [f"{k}: {v}" for k, v in errors.items()]
        return "; ".join(parts) if parts else str(payload)[:500]

    def _paginate(
        self,
        path: str,
        *,
        params: Dict[str, Any],
        items_key: Optional[str] = None,
        max_results_total: Optional[int] = None,
        page_size: int = 50,
        method: str = "GET",
    ) -> List[Dict[str, Any]]:
        """Transparently walk paginated Jira endpoints and return all items.

        Handles both the "startAt/maxResults/total" style (search, worklogs,
        comments) and the "isLast" style (agile boards/sprints).

        ``method="POST"`` sends ``params`` as the JSON body instead of the
        query string -- Jira's ``/search`` endpoint supports this, and it
        avoids putting a JQL query in the URL, which some reverse
        proxies/WAFs in front of self-hosted Jira instances reject (403)
        even for otherwise-valid, correctly-authenticated requests.
        """
        collected: List[Dict[str, Any]] = []
        start_at = int(params.get("startAt", 0))
        params = dict(params)

        while True:
            remaining = None
            if max_results_total is not None:
                remaining = max_results_total - len(collected)
                if remaining <= 0:
                    break
            batch_size = page_size if remaining is None else min(page_size, remaining)
            params["startAt"] = start_at
            params["maxResults"] = batch_size

            if method == "POST":
                payload = self._request("POST", path, json_body=params)
            else:
                payload = self._request("GET", path, params=params)
            items = payload.get(items_key, payload) if items_key else payload.get("values", [])
            collected.extend(items)

            total = payload.get("total")
            is_last = payload.get("isLast")
            fetched_count = len(items)

            start_at += fetched_count

            if is_last is True:
                break
            if fetched_count == 0:
                break
            if total is not None and start_at >= total:
                break
            if total is None and is_last is None and fetched_count < batch_size:
                # Neither pagination convention supplied a stop signal;
                # a short page is the only remaining indicator of the end.
                break

        if max_results_total is not None:
            collected = collected[:max_results_total]
        return collected

    # ------------------------------------------------------------------
    # Model builders (translate raw Jira JSON -> typed models)
    # ------------------------------------------------------------------

    def _browse_url(self, issue_key: str) -> Optional[str]:
        if not issue_key:
            return None
        return f"{self.config.base_url}/browse/{issue_key}"

    def resolve_project(self, project: Optional[str] = None) -> Optional[str]:
        """Resolve an explicit ``project`` against ``JIRA_DEFAULT_PROJECT``.

        Returns ``None`` (not a guess) if neither is available -- callers
        that require a project (e.g. ``triage``) should raise on ``None``
        themselves; callers where a project is only an optional narrowing
        (e.g. ``search_users``) can fall back to an unscoped call.
        """
        resolved = (project or self.config.default_project or "").strip()
        return resolved or None

    def _build_issue_links(self, raw_links: List[Dict[str, Any]]) -> List[IssueLink]:
        links: List[IssueLink] = []
        for raw_link in raw_links or []:
            link_type = safe_get(raw_link, "type", "name", default="Related")
            if "outwardIssue" in raw_link:
                direction = "outward"
                related = raw_link["outwardIssue"]
                type_label = safe_get(raw_link, "type", "outward", default=link_type)
            elif "inwardIssue" in raw_link:
                direction = "inward"
                related = raw_link["inwardIssue"]
                type_label = safe_get(raw_link, "type", "inward", default=link_type)
            else:
                continue
            related_key = related.get("key", "")
            links.append(
                IssueLink(
                    link_type=type_label,
                    direction=direction,
                    related_key=related_key,
                    related_summary=safe_get(related, "fields", "summary"),
                    related_status=safe_get(related, "fields", "status", "name"),
                    related_url=self._browse_url(related_key),
                )
            )
        return links

    def _build_subtasks(self, raw_subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "key": raw.get("key", ""),
                "url": self._browse_url(raw.get("key", "")),
                "summary": safe_get(raw, "fields", "summary"),
                "status": safe_get(raw, "fields", "status", "name"),
                "issue_type": safe_get(raw, "fields", "issuetype", "name"),
            }
            for raw in raw_subtasks or []
        ]

    def _build_issue(self, raw: Dict[str, Any]) -> Issue:
        fields = raw.get("fields", {}) or {}
        description = fields.get("description")
        custom_fields = {
            key: value
            for key, value in fields.items()
            if key not in _NAMED_ISSUE_FIELDS and value is not None
        }
        key = raw.get("key", "")
        return Issue(
            key=key,
            url=self._browse_url(key),
            summary=fields.get("summary", "") or "",
            status=safe_get(fields, "status", "name", default="Unknown"),
            priority=safe_get(fields, "priority", "name"),
            issue_type=safe_get(fields, "issuetype", "name"),
            assignee=safe_get(fields, "assignee", "displayName"),
            reporter=safe_get(fields, "reporter", "displayName"),
            updated=fields.get("updated"),
            created=fields.get("created"),
            due_date=fields.get("duedate"),
            labels=list(fields.get("labels") or []),
            links=self._build_issue_links(fields.get("issuelinks", [])),
            raw=raw,
            original_estimate_seconds=fields.get("timeoriginalestimate"),
            time_spent_seconds=fields.get("timespent"),
            remaining_estimate_seconds=fields.get("timeestimate"),
            description=adf_to_plain_text(description) if description else None,
            components=[c.get("name") for c in fields.get("components") or [] if c.get("name")],
            subtasks=self._build_subtasks(fields.get("subtasks")),
            custom_fields=custom_fields,
        )

    @staticmethod
    def _build_comment(raw: Dict[str, Any]) -> Comment:
        body = raw.get("body")
        text_body = adf_to_plain_text(body) if isinstance(body, dict) else str(body or "")
        return Comment(
            id=raw.get("id", ""),
            author=safe_get(raw, "author", "displayName"),
            body=text_body,
            created=raw.get("created"),
            updated=raw.get("updated"),
        )

    @staticmethod
    def _build_worklog(raw: Dict[str, Any]) -> Worklog:
        comment = raw.get("comment")
        text_comment = adf_to_plain_text(comment) if isinstance(comment, dict) else comment
        return Worklog(
            id=raw.get("id", ""),
            author=safe_get(raw, "author", "displayName"),
            time_spent=raw.get("timeSpent", ""),
            time_spent_seconds=int(raw.get("timeSpentSeconds", 0) or 0),
            comment=text_comment,
            started=raw.get("started"),
        )

    @staticmethod
    def _build_user(raw: Dict[str, Any]) -> User:
        return User(
            account_id=raw.get("accountId") or raw.get("key") or raw.get("name"),
            display_name=raw.get("displayName"),
            email=raw.get("emailAddress"),
            active=raw.get("active"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        jql: str,
        *,
        fields: Optional[List[str]] = None,
        max_results: Optional[int] = 200,
        expand: Optional[List[str]] = None,
    ) -> List[Issue]:
        """Run a JQL query and return all matching issues (auto-paginated).

        Args:
            jql: A valid JQL query string.
            fields: Jira fields to request. Defaults to a curated set
                sufficient for summaries; pass ``["*all"]`` for everything.
            max_results: Safety cap on total issues fetched (``None`` for
                unlimited, subject to Jira's own hard limits).
            expand: Optional expand parameters (e.g. ``["changelog"]``).
        """
        if not jql or not jql.strip():
            raise JiraValidationError("JQL query must not be empty.")

        params: Dict[str, Any] = {
            "jql": jql,
            "fields": list(fields or DEFAULT_ISSUE_FIELDS),
        }
        if expand:
            params["expand"] = list(expand)

        raw_issues = self._paginate(
            f"{self.API_V2}/search",
            params=params,
            items_key="issues",
            max_results_total=max_results,
            page_size=50,
            method="POST",
        )
        return [self._build_issue(raw) for raw in raw_issues]

    def get_issue(
        self,
        issue_key: str,
        *,
        fields: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> Issue:
        """Fetch a single issue by key (e.g. ``PAY-123``)."""
        self._require_issue_key(issue_key)
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = ",".join(expand)
        raw = self._request("GET", f"{self.API_V2}/issue/{issue_key}", params=params, cache=True)
        return self._build_issue(raw)

    def get_comments(self, issue_key: str, *, max_results: Optional[int] = None) -> List[Comment]:
        """Fetch all comments on an issue, oldest first."""
        self._require_issue_key(issue_key)
        raw_comments = self._paginate(
            f"{self.API_V2}/issue/{issue_key}/comment",
            params={},
            items_key="comments",
            max_results_total=max_results,
        )
        return [self._build_comment(raw) for raw in raw_comments]

    def get_worklogs(self, issue_key: str, *, max_results: Optional[int] = None) -> List[Worklog]:
        """Fetch all worklogs recorded against an issue."""
        self._require_issue_key(issue_key)
        raw_worklogs = self._paginate(
            f"{self.API_V2}/issue/{issue_key}/worklog",
            params={},
            items_key="worklogs",
            max_results_total=max_results,
        )
        return [self._build_worklog(raw) for raw in raw_worklogs]

    def get_changelog(self, issue_key: str, *, max_results: Optional[int] = None) -> List[ChangelogEntry]:
        """Fetch the field-change history of an issue."""
        self._require_issue_key(issue_key)
        raw_histories = self._paginate(
            f"{self.API_V2}/issue/{issue_key}/changelog",
            params={},
            items_key="values",
            max_results_total=max_results,
        )
        entries: List[ChangelogEntry] = []
        for history in raw_histories:
            author = safe_get(history, "author", "displayName")
            created = history.get("created")
            for item in history.get("items", []):
                entries.append(
                    ChangelogEntry(
                        id=history.get("id", ""),
                        author=author,
                        created=created,
                        field=item.get("field", ""),
                        from_value=item.get("fromString"),
                        to_value=item.get("toString"),
                    )
                )
        return entries

    def add_worklog(
        self,
        issue_key: str,
        duration_seconds: int,
        description: str,
        *,
        started: Optional[str] = None,
    ) -> Worklog:
        """Submit a worklog entry against an issue.

        Args:
            issue_key: Target issue, e.g. ``PAY-123``.
            duration_seconds: Time spent, in seconds (already parsed/validated).
            description: Free-text worklog comment.
            started: Optional ISO-8601 start timestamp; defaults to now on Jira's side.
        """
        self._require_issue_key(issue_key)
        if duration_seconds <= 0:
            raise JiraValidationError("Worklog duration_seconds must be positive.")

        body: Dict[str, Any] = {"timeSpentSeconds": duration_seconds, "comment": description}
        if started:
            body["started"] = started

        raw = self._request("POST", f"{self.API_V2}/issue/{issue_key}/worklog", json_body=body)
        return self._build_worklog(raw)

    def update_worklog(
        self,
        issue_key: str,
        worklog_id: str,
        *,
        duration_seconds: Optional[int] = None,
        description: Optional[str] = None,
        started: Optional[str] = None,
    ) -> Worklog:
        """Update an existing worklog entry. Only the given fields are changed."""
        self._require_issue_key(issue_key)
        if not worklog_id or not str(worklog_id).strip():
            raise JiraValidationError("worklog_id is required.")
        if duration_seconds is not None and duration_seconds <= 0:
            raise JiraValidationError("Worklog duration_seconds must be positive.")

        body: Dict[str, Any] = {}
        if duration_seconds is not None:
            body["timeSpentSeconds"] = duration_seconds
        if description is not None:
            body["comment"] = description
        if started is not None:
            body["started"] = started
        if not body:
            raise JiraValidationError(
                "At least one of duration_seconds/description/started must be provided."
            )

        raw = self._request(
            "PUT", f"{self.API_V2}/issue/{issue_key}/worklog/{worklog_id}", json_body=body
        )
        return self._build_worklog(raw)

    def delete_worklog(self, issue_key: str, worklog_id: str) -> None:
        """Permanently delete a worklog entry. Cannot be undone."""
        self._require_issue_key(issue_key)
        if not worklog_id or not str(worklog_id).strip():
            raise JiraValidationError("worklog_id is required.")
        self._request("DELETE", f"{self.API_V2}/issue/{issue_key}/worklog/{worklog_id}")

    def get_transitions(self, issue_key: str) -> List[Transition]:
        """List transitions currently available for an issue."""
        self._require_issue_key(issue_key)
        payload = self._request("GET", f"{self.API_V2}/issue/{issue_key}/transitions", params={})
        transitions = []
        for raw in payload.get("transitions", []):
            transitions.append(
                Transition(
                    id=raw.get("id", ""),
                    name=raw.get("name", ""),
                    to_status=safe_get(raw, "to", "name", default=""),
                )
            )
        return transitions

    def transition_issue(self, issue_key: str, transition: str) -> Dict[str, Any]:
        """Move an issue to a new status.

        Args:
            issue_key: Target issue, e.g. ``PAY-123``.
            transition: Either a transition id, a transition name (e.g.
                "Start Progress"), or a target status name (e.g. "Review").
                Resolved automatically against the issue's available
                transitions -- callers never need to know Jira transition ids.

        Raises:
            JiraValidationError: If no transition matches ``transition``.
        """
        self._require_issue_key(issue_key)
        available = self.get_transitions(issue_key)
        if not available:
            raise JiraValidationError(
                f"{issue_key} has no available transitions for the current user/status."
            )

        resolved = self._resolve_transition(transition, available)
        if resolved is None:
            options = ", ".join(f"{t.name} (-> {t.to_status})" for t in available)
            raise JiraValidationError(
                f"'{transition}' does not match any available transition for {issue_key}. "
                f"Available transitions: {options}"
            )

        self._request(
            "POST",
            f"{self.API_V2}/issue/{issue_key}/transitions",
            json_body={"transition": {"id": resolved.id}},
        )
        return {
            "issue_key": issue_key,
            "url": self._browse_url(issue_key),
            "transitioned_to": resolved.to_status,
            "transition_name": resolved.name,
            "success": True,
        }

    @staticmethod
    def _resolve_transition(requested: str, available: List[Transition]) -> Optional[Transition]:
        requested_norm = requested.strip().lower()
        for t in available:
            if t.id == requested.strip():
                return t
        for t in available:
            if t.name.lower() == requested_norm:
                return t
        for t in available:
            if t.to_status.lower() == requested_norm:
                return t
        # Fuzzy fallback: substring match against target status name.
        for t in available:
            if requested_norm in t.to_status.lower() or requested_norm in t.name.lower():
                return t
        return None

    def current_sprint(self, board_id: Optional[int] = None) -> Optional[Sprint]:
        """Return the active sprint for a board (auto-detected if not given)."""
        resolved_board_id = board_id if board_id is not None else self._require_default_board_id()
        payload = self._request(
            "GET",
            f"{self.AGILE_V1}/board/{resolved_board_id}/sprint",
            params={"state": "active"},
        )
        values = payload.get("values", [])
        if not values:
            return None
        raw = values[0]
        return Sprint(
            id=raw.get("id"),
            name=raw.get("name", ""),
            state=raw.get("state", ""),
            start_date=raw.get("startDate"),
            end_date=raw.get("endDate"),
            goal=raw.get("goal"),
            board_id=raw.get("originBoardId", resolved_board_id),
        )

    def current_board(self) -> Optional[Board]:
        """Return the first board visible to the authenticated user.

        In multi-board Jira instances, prefer calling agile endpoints with
        an explicit ``board_id`` obtained via a project-scoped lookup.
        """
        payload = self._request("GET", f"{self.AGILE_V1}/board", params={"maxResults": 1})
        values = payload.get("values", [])
        if not values:
            return None
        raw = values[0]
        return Board(id=raw.get("id"), name=raw.get("name", ""), type=raw.get("type", ""))

    def kanban_status(self, board_id: Optional[int] = None) -> Dict[str, Any]:
        """Return the kanban board's column configuration and per-column issue counts."""
        resolved_board_id = board_id if board_id is not None else self._require_default_board_id()
        config = self._request("GET", f"{self.AGILE_V1}/board/{resolved_board_id}/configuration", params={})
        columns = config.get("columnConfig", {}).get("columns", [])

        column_names = [c.get("name") for c in columns]
        issues_payload = self._request(
            "GET",
            f"{self.AGILE_V1}/board/{resolved_board_id}/issue",
            params={"fields": "status", "maxResults": 500},
        )
        counts: Dict[str, int] = {name: 0 for name in column_names}
        for raw_issue in issues_payload.get("issues", []):
            status_name = safe_get(raw_issue, "fields", "status", "name")
            if status_name in counts:
                counts[status_name] += 1

        return {
            "board_id": resolved_board_id,
            "columns": column_names,
            "issue_counts_by_column": counts,
        }

    def search_users(
        self,
        query: str,
        *,
        project: Optional[str] = None,
        all_projects: bool = False,
        max_results: int = 25,
    ) -> List[User]:
        """Search for users by name/email fragment (for assignee lookups).

        Sends both ``query`` and ``username`` for the same value: Jira
        Cloud's ``/user/search`` accepts ``query`` (matches display name or
        email); Jira Server/Data Center's pre-8.4 endpoint only recognizes
        ``username`` and 400s without it ("The username query parameter is
        required") even when ``query`` is also present. Sending both is the
        cheapest way to support both flavors without knowing which one a
        given ``base_url`` points at.

        Args:
            query: Name, username, or email fragment, e.g. ``"sam"``.
            project: When given (or falling back to ``JIRA_DEFAULT_PROJECT``
                if set), scopes the search to users assignable in that
                project instead of every user on the instance -- narrower,
                and disambiguates common names that only collide globally
                (e.g. two "Sam"es instance-wide, one of them not on this
                project). Falls back to an unscoped search if neither is
                available.
            all_projects: Force an unscoped, instance-wide search, ignoring
                both ``project`` and ``JIRA_DEFAULT_PROJECT``. Use this to
                broaden after a scoped search comes back empty -- merely
                omitting ``project`` is not enough to do that when
                ``JIRA_DEFAULT_PROJECT`` is configured, since it would still
                apply.
            max_results: Safety cap on the number of users returned.
        """
        if not query or not query.strip():
            raise JiraValidationError("search_users query must not be empty.")

        resolved_project = None if all_projects else self.resolve_project(project)
        if resolved_project:
            path = f"{self.API_V2}/user/assignable/search"
            params: Dict[str, Any] = {
                "project": resolved_project,
                "query": query,
                "username": query,
                "maxResults": max_results,
            }
        else:
            path = f"{self.API_V2}/user/search"
            params = {"query": query, "username": query, "maxResults": max_results}

        payload = self._request("GET", path, params=params)
        raw_users = payload if isinstance(payload, list) else payload.get("values", [])
        return [self._build_user(raw) for raw in raw_users]

    def get_current_user(self) -> User:
        """Return the authenticated user (used to resolve ``currentUser()``)."""
        raw = self._request("GET", f"{self.API_V2}/myself", params={}, cache=True)
        return self._build_user(raw)

    def triage(
        self,
        *,
        project: Optional[str] = None,
        parent_issue_types: Optional[List[str]] = None,
        max_results: int = 200,
    ) -> Dict[str, Any]:
        """Group unresolved parent issues with their subtasks for FE/BE triage.

        In this workflow, PMs create parent issues (Story/Bug/Task/Epic) and
        developers/designers create+label subtasks (e.g. "Frontend",
        "Backend") under them. A parent's own ``fields.subtasks`` only
        contains a lightweight stub (no ``labels``), so this method fetches
        subtasks as their own top-level search (which does carry ``labels``)
        and groups them by parent key -- this is deterministic bookkeeping,
        not judgment. Whether a parent *without* any subtasks needs
        frontend/backend/design work is left entirely to the caller (the
        LLM) to infer from ``description``/``summary``; this method only
        flags that fact (``needs_triage: true``), it never guesses.

        Args:
            project: Jira project key to scope both searches to (e.g.
                ``PAYKAN``). Falls back to ``JIRA_DEFAULT_PROJECT`` if unset.
                Raises if neither is available -- never guessed.
            parent_issue_types: Issue types treated as "parent" work items.
                Defaults to ``["Story", "Bug", "Task"]`` (excludes Epic and
                Sub-task).
            max_results: Safety cap on parent issues scanned.

        Returns:
            ``{"project": ..., "issue_count": N, "stories": [{"key", "url",
               "summary", "status", "description", "components",
               "has_frontend_subtask", "has_backend_subtask", "needs_triage",
               "subtasks": [{"key", "url", "summary", "status", "labels"}, ...]},
               ...]}``
        """
        resolved_project = self.resolve_project(project)
        if not resolved_project:
            raise JiraValidationError(
                "No project given and JIRA_DEFAULT_PROJECT is not set. Pass an explicit "
                "project key, e.g. determined from prior search results or by asking the user."
            )
        types = list(parent_issue_types or ["Story", "Bug", "Task"])
        types_jql = ", ".join(types)

        parents = self.search(
            f"project = {resolved_project} AND issuetype in ({types_jql}) AND resolution = Unresolved",
            fields=["summary", "status", "description", "components"],
            max_results=max_results,
        )
        subtask_issues = self.search(
            f"project = {resolved_project} AND issuetype = Sub-task AND resolution = Unresolved",
            fields=["summary", "status", "labels", "parent"],
            max_results=max_results,
        )

        subtasks_by_parent: Dict[str, List[Dict[str, Any]]] = {}
        for sub in subtask_issues:
            parent_key = safe_get(sub.custom_fields, "parent", "key")
            if not parent_key:
                continue
            subtasks_by_parent.setdefault(parent_key, []).append(
                {
                    "key": sub.key,
                    "url": sub.url,
                    "summary": sub.summary,
                    "status": sub.status,
                    "labels": list(sub.labels),
                }
            )

        stories: List[Dict[str, Any]] = []
        for parent in parents:
            subs = subtasks_by_parent.get(parent.key, [])
            labels_lower = [label.lower() for sub in subs for label in sub["labels"]]
            stories.append(
                {
                    "key": parent.key,
                    "url": parent.url,
                    "summary": parent.summary,
                    "status": parent.status,
                    "description": parent.description,
                    "components": list(parent.components),
                    "has_frontend_subtask": any("frontend" in label for label in labels_lower),
                    "has_backend_subtask": any("backend" in label for label in labels_lower),
                    "needs_triage": len(subs) == 0,
                    "subtasks": subs,
                }
            )

        return {
            "project": resolved_project,
            "issue_count": len(stories),
            "stories": stories,
        }

    def list_fields(self) -> List[Dict[str, Any]]:
        """Return every field this Jira instance knows about.

        Used to discover a custom field's ID by its display name (e.g. a
        "Figma Link" URL field is typically ``customfield_XXXXX`` and
        varies per instance) so it can be requested explicitly via
        ``search(..., fields=[...])`` -- the client never hardcodes
        instance-specific custom field IDs itself.
        """
        payload = self._request("GET", f"{self.API_V2}/field", params={}, cache=True)
        return [
            {"id": f.get("id"), "name": f.get("name"), "custom": bool(f.get("custom"))}
            for f in payload or []
        ]

    def create_issue(
        self,
        project: str,
        summary: str,
        issue_type: str,
        *,
        description: Optional[str] = None,
        parent_key: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignee_account_id: Optional[str] = None,
        priority: Optional[str] = None,
        components: Optional[List[str]] = None,
    ) -> Issue:
        """Create a new issue -- a parent work item, or a subtask.

        In this workflow PMs create parent issues (Story/Bug/Task/Epic) and
        developers/designers create subtasks under them, so this single
        method covers both: pass ``issue_type="Sub-task"`` and
        ``parent_key`` to create a subtask instead of a separate method.

        Args:
            project: Project key, e.g. ``PAYKAN``.
            summary: Issue title.
            issue_type: e.g. ``"Story"``, ``"Bug"``, ``"Task"``, ``"Sub-task"``.
            description: Plain-text description.
            parent_key: Required when ``issue_type`` is ``"Sub-task"``.
            labels: Labels to apply, e.g. ``["Frontend"]``.
            assignee_account_id: A user's ``account_id`` (resolve a name to
                this via ``search_users`` first -- never guessed from a
                display name).
            priority: Priority name, e.g. ``"High"``.
            components: Component names.

        Raises:
            JiraValidationError: If required fields are missing, or
                ``issue_type`` is ``"Sub-task"`` without ``parent_key``.
        """
        project = (project or "").strip()
        if not project:
            raise JiraValidationError("project is required.")
        summary = (summary or "").strip()
        if not summary:
            raise JiraValidationError("summary is required.")
        issue_type = (issue_type or "").strip()
        if not issue_type:
            raise JiraValidationError("issue_type is required.")
        if issue_type.lower() == "sub-task" and not parent_key:
            raise JiraValidationError("parent_key is required when issue_type is 'Sub-task'.")

        fields: Dict[str, Any] = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = description
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if labels:
            fields["labels"] = list(labels)
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority:
            fields["priority"] = {"name": priority}
        if components:
            fields["components"] = [{"name": c} for c in components]

        raw = self._request("POST", f"{self.API_V2}/issue", json_body={"fields": fields})
        return self.get_issue(raw.get("key", ""))

    def edit_issue(
        self,
        issue_key: str,
        *,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignee_account_id: Optional[str] = None,
        priority: Optional[str] = None,
        components: Optional[List[str]] = None,
    ) -> Issue:
        """Update fields on an existing issue (or subtask). Only given fields change.

        Args:
            issue_key: Target issue, e.g. ``PAY-123``.
            assignee_account_id: A user's ``account_id`` (resolve via
                ``search_users`` first -- never guessed).

        Raises:
            JiraValidationError: If no field is given to update.
        """
        self._require_issue_key(issue_key)
        fields: Dict[str, Any] = {}
        if summary is not None:
            fields["summary"] = summary
        if description is not None:
            fields["description"] = description
        if labels is not None:
            fields["labels"] = list(labels)
        if assignee_account_id is not None:
            fields["assignee"] = {"accountId": assignee_account_id}
        if priority is not None:
            fields["priority"] = {"name": priority}
        if components is not None:
            fields["components"] = [{"name": c} for c in components]
        if not fields:
            raise JiraValidationError(
                "At least one of summary/description/labels/assignee_account_id/"
                "priority/components must be provided."
            )

        self._request("PUT", f"{self.API_V2}/issue/{issue_key}", json_body={"fields": fields})
        return self.get_issue(issue_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _default_board_id: Optional[int] = None

    def _require_default_board_id(self) -> int:
        if self._default_board_id is not None:
            return self._default_board_id
        board = self.current_board()
        if board is None:
            raise JiraNotFoundError("No boards are visible to the authenticated user.")
        self._default_board_id = board.id
        return board.id

    @staticmethod
    def _require_issue_key(issue_key: str) -> None:
        if not issue_key or not issue_key.strip():
            raise JiraValidationError("issue_key must not be empty.")
        if "-" not in issue_key:
            raise JiraValidationError(
                f"issue_key {issue_key!r} does not look like a valid Jira key (e.g. PAY-123)."
            )


_client_lock = threading.Lock()
_client_singleton: Optional[JiraClient] = None


def get_client() -> JiraClient:
    """Return a process-wide singleton :class:`JiraClient`.

    Tools should use this instead of constructing their own client, so
    that configuration is validated once and the underlying HTTP session
    (with its connection pool and retry policy) is reused across calls.
    """
    global _client_singleton
    with _client_lock:
        if _client_singleton is None:
            _client_singleton = JiraClient()
        return _client_singleton


def reset_client() -> None:
    """Drop the cached singleton client (primarily for tests)."""
    global _client_singleton
    with _client_lock:
        _client_singleton = None
