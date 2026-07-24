import pytest

from lib.jira_client import (
    JiraAuthError,
    JiraNotFoundError,
    JiraRateLimitError,
    JiraValidationError,
)
from tests.conftest import make_response


def test_search_empty_jql_rejected(client):
    with pytest.raises(JiraValidationError):
        client.search("")


def test_search_paginates_until_total_reached(client, mock_session):
    page1 = make_response(json_data={"issues": [{"key": "PAY-1", "fields": {}}], "total": 3})
    page2 = make_response(json_data={"issues": [{"key": "PAY-2", "fields": {}}], "total": 3})
    page3 = make_response(json_data={"issues": [{"key": "PAY-3", "fields": {}}], "total": 3})
    mock_session.request.side_effect = [page1, page2, page3]

    issues = client.search("project = PAY", max_results=None)

    assert [i.key for i in issues] == ["PAY-1", "PAY-2", "PAY-3"]
    assert mock_session.request.call_count == 3


def test_search_respects_max_results_cap(client, mock_session):
    page1 = make_response(json_data={"issues": [{"key": f"PAY-{i}", "fields": {}} for i in range(50)], "total": 200})
    mock_session.request.return_value = page1

    issues = client.search("project = PAY", max_results=10)

    assert len(issues) == 10


def test_get_issue_builds_typed_model(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "key": "PAY-1",
            "fields": {
                "summary": "Fix bug",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "issuetype": {"name": "Bug"},
                "assignee": {"displayName": "Alice"},
                "reporter": {"displayName": "Bob"},
                "updated": "2026-07-20T10:00:00Z",
                "created": "2026-07-01T10:00:00Z",
                "duedate": None,
                "labels": ["backend"],
                "issuelinks": [],
            },
        }
    )
    issue = client.get_issue("PAY-1")
    assert issue.key == "PAY-1"
    assert issue.summary == "Fix bug"
    assert issue.status == "In Progress"
    assert issue.priority == "High"
    assert issue.assignee == "Alice"
    assert issue.labels == ["backend"]


def test_get_issue_builds_description_subtasks_components_and_custom_fields(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "key": "PAY-1",
            "fields": {
                "summary": "Fix bug",
                "status": {"name": "In Progress"},
                "description": "Needs a frontend fix.",
                "components": [{"name": "Frontend"}, {"name": "API"}],
                "subtasks": [
                    {
                        "key": "PAY-2",
                        "fields": {
                            "summary": "Sub-task",
                            "status": {"name": "To Do"},
                            "issuetype": {"name": "Sub-task"},
                        },
                    }
                ],
                "customfield_10056": "https://figma.com/file/abc",
            },
        }
    )
    issue = client.get_issue("PAY-1")
    assert issue.description == "Needs a frontend fix."
    assert issue.components == ["Frontend", "API"]
    assert issue.subtasks == [
        {
            "key": "PAY-2",
            "url": "https://jira.example.com/browse/PAY-2",
            "summary": "Sub-task",
            "status": "To Do",
            "issue_type": "Sub-task",
        }
    ]
    assert issue.custom_fields == {"customfield_10056": "https://figma.com/file/abc"}


def test_get_issue_rejects_bad_key(client):
    with pytest.raises(JiraValidationError):
        client.get_issue("")
    with pytest.raises(JiraValidationError):
        client.get_issue("nokeyformat")


def test_401_raises_auth_error(client, mock_session):
    mock_session.request.return_value = make_response(status_code=401, json_data={"errorMessages": ["bad creds"]})
    with pytest.raises(JiraAuthError):
        client.get_issue("PAY-1")


def test_404_raises_not_found(client, mock_session):
    mock_session.request.return_value = make_response(status_code=404, json_data={"errorMessages": ["no such issue"]})
    with pytest.raises(JiraNotFoundError):
        client.get_issue("PAY-1")


def test_429_raises_rate_limit_error(client, mock_session):
    mock_session.request.return_value = make_response(
        status_code=429, json_data={"errorMessages": ["slow down"]}, headers={"Retry-After": "5"}
    )
    with pytest.raises(JiraRateLimitError):
        client.get_issue("PAY-1")


def test_add_worklog_builds_request_body(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "id": "1",
            "author": {"displayName": "Alice"},
            "timeSpent": "2h",
            "timeSpentSeconds": 7200,
            "comment": "did work",
            "started": "2026-07-21T10:00:00Z",
        }
    )
    worklog = client.add_worklog("PAY-1", 7200, "did work")
    assert worklog.time_spent_seconds == 7200

    _, kwargs = mock_session.request.call_args
    assert kwargs["json"] == {"timeSpentSeconds": 7200, "comment": "did work"}


def test_add_worklog_includes_started_when_given(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "id": "1",
            "author": {"displayName": "Alice"},
            "timeSpent": "2h",
            "timeSpentSeconds": 7200,
            "comment": "did work",
            "started": "2026-07-20T09:00:00.000+0000",
        }
    )
    client.add_worklog("PAY-1", 7200, "did work", started="2026-07-20T09:00:00.000+0000")

    _, kwargs = mock_session.request.call_args
    assert kwargs["json"] == {
        "timeSpentSeconds": 7200,
        "comment": "did work",
        "started": "2026-07-20T09:00:00.000+0000",
    }


def test_update_worklog_sends_only_provided_fields(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "id": "28459",
            "author": {"displayName": "Alice"},
            "timeSpent": "1h",
            "timeSpentSeconds": 3600,
            "comment": "did work",
            "started": "2026-07-20T09:00:00.000+0000",
        }
    )
    worklog = client.update_worklog("PAY-1", "28459", duration_seconds=3600)
    assert worklog.time_spent_seconds == 3600

    method, url = mock_session.request.call_args[0][:2]
    _, kwargs = mock_session.request.call_args
    assert method == "PUT"
    assert url.endswith("/issue/PAY-1/worklog/28459")
    assert kwargs["json"] == {"timeSpentSeconds": 3600}


def test_update_worklog_rejects_when_no_fields_given(client):
    with pytest.raises(JiraValidationError):
        client.update_worklog("PAY-1", "28459")


def test_update_worklog_rejects_missing_worklog_id(client):
    with pytest.raises(JiraValidationError):
        client.update_worklog("PAY-1", "", duration_seconds=3600)


def test_delete_worklog_issues_delete_request(client, mock_session):
    mock_session.request.return_value = make_response(status_code=204)
    client.delete_worklog("PAY-1", "28459")

    method, url = mock_session.request.call_args[0][:2]
    assert method == "DELETE"
    assert url.endswith("/issue/PAY-1/worklog/28459")


def test_delete_worklog_rejects_missing_worklog_id(client):
    with pytest.raises(JiraValidationError):
        client.delete_worklog("PAY-1", "")


def test_add_worklog_rejects_non_positive_duration(client):
    with pytest.raises(JiraValidationError):
        client.add_worklog("PAY-1", 0, "no time")


def test_get_transitions_builds_models(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={
            "transitions": [
                {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Move to Review", "to": {"name": "Review"}},
            ]
        }
    )
    transitions = client.get_transitions("PAY-1")
    assert [t.name for t in transitions] == ["Start Progress", "Move to Review"]


def test_transition_issue_resolves_by_target_status_name(client, mock_session):
    transitions_response = make_response(
        json_data={
            "transitions": [
                {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                {"id": "21", "name": "Move to Review", "to": {"name": "Review"}},
            ]
        }
    )
    post_response = make_response(status_code=204)
    mock_session.request.side_effect = [transitions_response, post_response]

    result = client.transition_issue("PAY-1", "Review")

    assert result == {
        "issue_key": "PAY-1",
        "url": "https://jira.example.com/browse/PAY-1",
        "transitioned_to": "Review",
        "transition_name": "Move to Review",
        "success": True,
    }
    post_call_kwargs = mock_session.request.call_args_list[1].kwargs
    assert post_call_kwargs["json"] == {"transition": {"id": "21"}}


def test_transition_issue_unmatched_raises_with_options(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data={"transitions": [{"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}}]}
    )
    with pytest.raises(JiraValidationError, match="Start Progress"):
        client.transition_issue("PAY-1", "Nonexistent Status")


def test_search_users_handles_list_payload(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data=[{"accountId": "1", "displayName": "Alice", "emailAddress": "a@example.com", "active": True}]
    )
    users = client.search_users("alice")
    assert users[0].display_name == "Alice"


def test_search_users_rejects_empty_query(client):
    with pytest.raises(JiraValidationError):
        client.search_users("")


def test_list_fields_returns_id_name_custom(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data=[
            {"id": "summary", "name": "Summary", "custom": False},
            {"id": "customfield_10056", "name": "Figma Link", "custom": True},
        ]
    )
    fields = client.list_fields()
    assert fields == [
        {"id": "summary", "name": "Summary", "custom": False},
        {"id": "customfield_10056", "name": "Figma Link", "custom": True},
    ]


def test_triage_requires_a_project(client):
    with pytest.raises(JiraValidationError):
        client.triage()


def test_triage_uses_default_project_from_config(jira_config, mock_session):
    from dataclasses import replace

    from lib.jira_client import JiraClient

    configured_client = JiraClient(config=replace(jira_config, default_project="PAYKAN"), session=mock_session)
    mock_session.request.side_effect = [
        make_response(json_data={"issues": []}),
        make_response(json_data={"issues": []}),
    ]
    result = configured_client.triage()
    assert result["project"] == "PAYKAN"


def test_triage_groups_subtasks_by_parent_and_flags_labels(client, mock_session):
    parents_page = make_response(
        json_data={
            "issues": [
                {
                    "key": "PAYKAN-100",
                    "fields": {"summary": "Add checkout flow", "status": {"name": "To Do"}},
                },
                {
                    "key": "PAYKAN-200",
                    "fields": {"summary": "No subtasks yet", "status": {"name": "To Do"}},
                },
            ]
        }
    )
    subtasks_page = make_response(
        json_data={
            "issues": [
                {
                    "key": "PAYKAN-101",
                    "fields": {
                        "summary": "Build checkout UI",
                        "status": {"name": "To Do"},
                        "labels": ["Frontend"],
                        "parent": {"key": "PAYKAN-100"},
                    },
                },
                {
                    "key": "PAYKAN-102",
                    "fields": {
                        "summary": "Checkout API",
                        "status": {"name": "Done"},
                        "labels": ["Backend"],
                        "parent": {"key": "PAYKAN-100"},
                    },
                },
            ]
        }
    )
    mock_session.request.side_effect = [parents_page, subtasks_page]

    result = client.triage(project="PAYKAN")

    assert result["project"] == "PAYKAN"
    assert result["issue_count"] == 2
    story_100 = next(s for s in result["stories"] if s["key"] == "PAYKAN-100")
    assert story_100["has_frontend_subtask"] is True
    assert story_100["has_backend_subtask"] is True
    assert story_100["needs_triage"] is False
    assert {s["key"] for s in story_100["subtasks"]} == {"PAYKAN-101", "PAYKAN-102"}

    story_200 = next(s for s in result["stories"] if s["key"] == "PAYKAN-200")
    assert story_200["needs_triage"] is True
    assert story_200["subtasks"] == []
    assert story_200["has_frontend_subtask"] is False
    assert story_200["has_backend_subtask"] is False


def test_search_users_maps_display_name_email_and_active(client, mock_session):
    mock_session.request.return_value = make_response(
        json_data=[
            {"accountId": "abc123", "displayName": "John Smith", "emailAddress": "john@example.com", "active": True}
        ]
    )
    users = client.search_users("john")
    assert users[0].account_id == "abc123"
    assert users[0].display_name == "John Smith"


def test_search_users_sends_both_query_and_username_params(client, mock_session):
    mock_session.request.return_value = make_response(json_data=[])
    client.search_users("john")
    _, kwargs = mock_session.request.call_args
    assert kwargs["params"]["query"] == "john"
    assert kwargs["params"]["username"] == "john"


def test_search_users_unscoped_hits_plain_user_search(client, mock_session):
    mock_session.request.return_value = make_response(json_data=[])
    client.search_users("sam")
    method, url = mock_session.request.call_args[0][:2]
    assert url.endswith("/user/search")


def test_search_users_scoped_by_explicit_project_hits_assignable_search(client, mock_session):
    mock_session.request.return_value = make_response(json_data=[])
    client.search_users("sam", project="PAYKAN")
    method, url = mock_session.request.call_args[0][:2]
    assert url.endswith("/user/assignable/search")
    _, kwargs = mock_session.request.call_args
    assert kwargs["params"]["project"] == "PAYKAN"
    assert kwargs["params"]["query"] == "sam"
    assert kwargs["params"]["username"] == "sam"


def test_search_users_scoped_by_default_project_from_config(jira_config, mock_session):
    from dataclasses import replace

    from lib.jira_client import JiraClient

    configured_client = JiraClient(config=replace(jira_config, default_project="PAYKAN"), session=mock_session)
    mock_session.request.return_value = make_response(json_data=[])
    configured_client.search_users("sam")
    method, url = mock_session.request.call_args[0][:2]
    assert url.endswith("/user/assignable/search")
    _, kwargs = mock_session.request.call_args
    assert kwargs["params"]["project"] == "PAYKAN"


def test_search_users_explicit_project_overrides_default_project(jira_config, mock_session):
    from dataclasses import replace

    from lib.jira_client import JiraClient

    configured_client = JiraClient(config=replace(jira_config, default_project="PAYKAN"), session=mock_session)
    mock_session.request.return_value = make_response(json_data=[])
    configured_client.search_users("sam", project="OTHER")
    _, kwargs = mock_session.request.call_args
    assert kwargs["params"]["project"] == "OTHER"


def test_search_users_all_projects_ignores_explicit_and_default_project(jira_config, mock_session):
    from dataclasses import replace

    from lib.jira_client import JiraClient

    configured_client = JiraClient(config=replace(jira_config, default_project="PAYKAN"), session=mock_session)
    mock_session.request.return_value = make_response(json_data=[])
    configured_client.search_users("sam", project="OTHER", all_projects=True)
    method, url = mock_session.request.call_args[0][:2]
    assert url.endswith("/user/search")
    _, kwargs = mock_session.request.call_args
    assert "project" not in kwargs["params"]


def test_resolve_project_returns_none_when_neither_given(client):
    assert client.resolve_project(None) is None


def test_resolve_project_falls_back_to_config_default(jira_config, mock_session):
    from dataclasses import replace

    from lib.jira_client import JiraClient

    configured_client = JiraClient(config=replace(jira_config, default_project="PAYKAN"), session=mock_session)
    assert configured_client.resolve_project(None) == "PAYKAN"
    assert configured_client.resolve_project("OTHER") == "OTHER"


def test_create_issue_requires_project_summary_and_type(client):
    with pytest.raises(JiraValidationError):
        client.create_issue("", "Fix bug", "Bug")
    with pytest.raises(JiraValidationError):
        client.create_issue("PAYKAN", "", "Bug")
    with pytest.raises(JiraValidationError):
        client.create_issue("PAYKAN", "Fix bug", "")


def test_create_issue_subtask_requires_parent_key(client):
    with pytest.raises(JiraValidationError, match="parent_key"):
        client.create_issue("PAYKAN", "Build UI", "Sub-task")


def test_create_issue_builds_request_body_and_refetches(client, mock_session):
    create_response = make_response(status_code=201, json_data={"key": "PAYKAN-500"})
    get_response = make_response(
        json_data={"key": "PAYKAN-500", "fields": {"summary": "Build UI", "status": {"name": "To Do"}}}
    )
    mock_session.request.side_effect = [create_response, get_response]

    issue = client.create_issue(
        "PAYKAN",
        "Build UI",
        "Sub-task",
        description="Needs a modal",
        parent_key="PAYKAN-100",
        labels=["Frontend"],
        assignee_account_id="abc123",
        priority="High",
        components=["Web"],
    )

    assert issue.key == "PAYKAN-500"
    post_call = mock_session.request.call_args_list[0]
    method, url = post_call.args[:2]
    assert method == "POST"
    assert url.endswith("/issue")
    body = post_call.kwargs["json"]["fields"]
    assert body == {
        "project": {"key": "PAYKAN"},
        "summary": "Build UI",
        "issuetype": {"name": "Sub-task"},
        "description": "Needs a modal",
        "parent": {"key": "PAYKAN-100"},
        "labels": ["Frontend"],
        "assignee": {"accountId": "abc123"},
        "priority": {"name": "High"},
        "components": [{"name": "Web"}],
    }


def test_edit_issue_rejects_when_no_fields_given(client):
    with pytest.raises(JiraValidationError):
        client.edit_issue("PAYKAN-1")


def test_edit_issue_sends_only_provided_fields_and_refetches(client, mock_session):
    put_response = make_response(status_code=204)
    get_response = make_response(
        json_data={"key": "PAYKAN-1", "fields": {"summary": "New title", "status": {"name": "To Do"}}}
    )
    mock_session.request.side_effect = [put_response, get_response]

    issue = client.edit_issue("PAYKAN-1", summary="New title")

    assert issue.summary == "New title"
    put_call = mock_session.request.call_args_list[0]
    method, url = put_call.args[:2]
    assert method == "PUT"
    assert url.endswith("/issue/PAYKAN-1")
    assert put_call.kwargs["json"] == {"fields": {"summary": "New title"}}


def test_default_output_fields_omit_description_and_time_tracking():
    from lib.jira_client import DEFAULT_OUTPUT_FIELDS, ISSUE_FIELD_MAP

    assert "description" not in DEFAULT_OUTPUT_FIELDS
    assert "original_estimate_seconds" not in DEFAULT_OUTPUT_FIELDS
    assert set(DEFAULT_OUTPUT_FIELDS).issubset(ISSUE_FIELD_MAP.keys())


def test_resolve_issue_fields_defaults_when_only_omitted():
    from lib.jira_client import DEFAULT_OUTPUT_FIELDS, ISSUE_FIELD_MAP, resolve_issue_fields

    jira_fields, output_keys = resolve_issue_fields(None)
    assert output_keys == DEFAULT_OUTPUT_FIELDS
    assert jira_fields == [ISSUE_FIELD_MAP[name] for name in DEFAULT_OUTPUT_FIELDS]


def test_resolve_issue_fields_honors_only_and_dedups_always_fetch():
    from lib.jira_client import resolve_issue_fields

    jira_fields, output_keys = resolve_issue_fields(["summary", "status"], always_fetch=["status", "links"])
    assert output_keys == ["summary", "status"]
    assert jira_fields == ["summary", "status", "issuelinks"]


def test_resolve_issue_fields_rejects_unknown_name():
    from lib.jira_client import resolve_issue_fields

    with pytest.raises(JiraValidationError):
        resolve_issue_fields(["not_a_real_field"])


def test_issue_to_dict_only_filters_but_keeps_key_url_custom_fields():
    from lib.models import Issue

    issue = Issue(
        key="PAY-1",
        summary="Fix bug",
        status="To Do",
        priority="High",
        issue_type="Bug",
        assignee="Alice",
        reporter="Bob",
        updated="2026-07-20",
        created="2026-07-01",
        due_date=None,
        url="https://jira.example.com/browse/PAY-1",
        custom_fields={"customfield_10056": "https://figma.com/x"},
    )
    d = issue.to_dict(only=["summary"])
    assert d == {
        "key": "PAY-1",
        "url": "https://jira.example.com/browse/PAY-1",
        "custom_fields": {"customfield_10056": "https://figma.com/x"},
        "summary": "Fix bug",
    }


def test_project_context_requires_a_project(client):
    with pytest.raises(JiraValidationError):
        client.project_context()


def _empty_project_context_responses(project_name="Payment Platform", lead="Alice"):
    return [
        make_response(json_data={"name": project_name, "lead": {"displayName": lead}}),
        make_response(json_data=[]),  # statuses
        make_response(json_data=[]),  # components
        make_response(json_data=[]),  # priorities
        make_response(json_data=[]),  # users (single short page)
        make_response(json_data={"issues": [], "total": 0}),  # labels
    ]


def test_project_context_uses_default_project_from_config(jira_config, mock_session):
    from dataclasses import replace

    from lib.jira_client import JiraClient

    configured_client = JiraClient(config=replace(jira_config, default_project="PAYKAN"), session=mock_session)
    mock_session.request.side_effect = _empty_project_context_responses()
    result = configured_client.project_context()
    assert result["project"] == "PAYKAN"


def test_project_context_builds_full_reference_snapshot(client, mock_session):
    project_info_response = make_response(
        json_data={"name": "Payment Platform", "lead": {"displayName": "Alice"}}
    )
    statuses_response = make_response(
        json_data=[
            {"name": "Story", "statuses": [{"name": "To Do"}, {"name": "In Progress"}]},
            {"name": "Bug", "statuses": [{"name": "To Do"}, {"name": "Done"}]},
        ]
    )
    components_response = make_response(
        json_data=[{"name": "API"}, {"name": "Web"}]
    )
    priorities_response = make_response(
        json_data=[{"name": "Highest"}, {"name": "High"}, {"name": "Low"}]
    )
    users_response = make_response(
        json_data=[
            {"accountId": "abc123", "displayName": "Alice", "emailAddress": "alice@example.com", "active": True},
            {"accountId": "def456", "displayName": "Bob", "emailAddress": "bob@example.com", "active": True},
        ]
    )
    labels_response = make_response(
        json_data={
            "issues": [
                {"key": "PAY-1", "fields": {"labels": ["Frontend", "Backend"]}},
                {"key": "PAY-2", "fields": {"labels": ["Frontend"]}},
            ],
            "total": 2,
        }
    )
    mock_session.request.side_effect = [
        project_info_response,
        statuses_response,
        components_response,
        priorities_response,
        users_response,
        labels_response,
    ]

    result = client.project_context(project="PAYKAN")

    assert result == {
        "project": "PAYKAN",
        "name": "Payment Platform",
        "lead": "Alice",
        "issue_types": ["Bug", "Story"],
        "statuses": ["Done", "In Progress", "To Do"],
        "statuses_by_issue_type": {
            "Story": ["In Progress", "To Do"],
            "Bug": ["Done", "To Do"],
        },
        "components": ["API", "Web"],
        "priorities": ["Highest", "High", "Low"],
        "users": [
            {"account_id": "abc123", "display_name": "Alice", "email": "alice@example.com", "active": True},
            {"account_id": "def456", "display_name": "Bob", "email": "bob@example.com", "active": True},
        ],
        "labels": ["Backend", "Frontend"],
    }

    calls = mock_session.request.call_args_list
    assert calls[0].args[:2] == ("GET", "https://jira.example.com/rest/api/2/project/PAYKAN")
    assert calls[1].args[:2] == ("GET", "https://jira.example.com/rest/api/2/project/PAYKAN/statuses")
    assert calls[2].args[:2] == ("GET", "https://jira.example.com/rest/api/2/project/PAYKAN/components")
    assert calls[3].args[:2] == ("GET", "https://jira.example.com/rest/api/2/priority")
    users_method, users_url = calls[4].args[:2]
    assert users_method == "GET"
    assert users_url.endswith("/user/assignable/search")
    assert calls[4].kwargs["params"]["project"] == "PAYKAN"
    assert calls[5].args[0] == "POST"


def test_project_context_paginates_users_instead_of_one_large_page(client, mock_session):
    def fake_user(i):
        return {"accountId": f"acc{i}", "displayName": f"User {i}", "emailAddress": f"u{i}@example.com", "active": True}

    users_page1 = make_response(json_data=[fake_user(i) for i in range(50)])
    users_page2 = make_response(json_data=[fake_user(i) for i in range(50, 60)])
    mock_session.request.side_effect = [
        make_response(json_data={"name": "Payment Platform", "lead": {"displayName": "Alice"}}),
        make_response(json_data=[]),  # statuses
        make_response(json_data=[]),  # components
        make_response(json_data=[]),  # priorities
        users_page1,
        users_page2,
        make_response(json_data={"issues": [], "total": 0}),  # labels
    ]

    result = client.project_context(project="PAYKAN")

    assert len(result["users"]) == 60
    assert mock_session.request.call_count == 7
    # Each user page request asks for a bounded page, not one large page.
    users_page1_call = mock_session.request.call_args_list[4]
    assert users_page1_call.kwargs["params"]["maxResults"] == 50
