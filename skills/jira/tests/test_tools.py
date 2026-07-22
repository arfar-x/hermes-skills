from unittest.mock import MagicMock, patch

from lib.auth import JiraConfig
from lib.models import Comment, Issue, IssueLink, Sprint, User, Worklog
from tools import (
    blockers,
    issue_summary,
    list_fields,
    my_work,
    search,
    sprint,
    transition,
    triage,
    worklog,
    worklog_delete,
    worklog_edit,
    worklog_report,
)


def _issue(
    key="PAY-1",
    status="To Do",
    links=None,
    priority="High",
    updated="2026-07-20",
    original_estimate_seconds=None,
):
    return Issue(
        key=key,
        summary="Fix bug",
        status=status,
        priority=priority,
        issue_type="Bug",
        assignee="Alice",
        reporter="Bob",
        updated=updated,
        created="2026-07-01",
        due_date=None,
        links=links or [],
        original_estimate_seconds=original_estimate_seconds,
    )


def _fake_config(auto_confirm=False):
    return JiraConfig(
        base_url="https://jira.example.com",
        username="alice",
        password="secret",
        auto_confirm_writes=auto_confirm,
    )


def test_my_work_returns_list_with_blocked_flag():
    mock_client = MagicMock()
    mock_client.search.return_value = [_issue(status="Blocked")]
    with patch("tools.my_work.get_client", return_value=mock_client):
        result = my_work.my_work()
    assert result[0]["key"] == "PAY-1"
    assert result[0]["blocked"] is True
    mock_client.search.assert_called_once()


def test_my_work_wraps_errors_as_json():
    mock_client = MagicMock()
    from lib.jira_client import JiraApiError

    mock_client.search.side_effect = JiraApiError("boom", status_code=500)
    with patch("tools.my_work.get_client", return_value=mock_client):
        result = my_work.my_work()
    assert "error" in result


def test_blockers_reports_reasons():
    link = IssueLink("is blocked by", "inward", "PAY-2", "dep", "In Progress")
    mock_client = MagicMock()
    mock_client.get_issue.return_value = _issue(links=[link])
    mock_client.get_comments.return_value = []
    with patch("tools.blockers.get_client", return_value=mock_client):
        result = blockers.blockers("PAY-1")
    assert result["blocked"] is True
    assert "PAY-2" in result["reasons"][0]


def test_blockers_rejects_empty_issue_key():
    result = blockers.blockers("")
    assert result["error"]["type"] == "invalid_input"


def test_issue_summary_combines_all_sources():
    mock_client = MagicMock()
    mock_client.get_issue.return_value = _issue()
    mock_client.get_comments.return_value = [Comment("1", "Alice", "hi", "2026-07-01", None)]
    mock_client.get_worklogs.return_value = [Worklog("1", "Alice", "2h", 7200, "work", "2026-07-01")]
    mock_client.get_changelog.return_value = []
    with patch("tools.issue_summary.get_client", return_value=mock_client):
        result = issue_summary.issue_summary("PAY-1")
    assert result["issue"]["key"] == "PAY-1"
    assert len(result["comments"]) == 1
    assert len(result["worklogs"]) == 1


def test_search_requires_jql():
    result = search.search("")
    assert result["error"]["type"] == "invalid_input"


def test_search_returns_count_and_issues():
    mock_client = MagicMock()
    mock_client.search.return_value = [_issue()]
    with patch("tools.search.get_client", return_value=mock_client):
        result = search.search("project = PAY")
    assert result["count"] == 1
    assert result["issues"][0]["key"] == "PAY-1"


def test_search_requests_default_fields_plus_extra():
    mock_client = MagicMock()
    mock_client.search.return_value = []
    with patch("tools.search.get_client", return_value=mock_client):
        search.search("project = PAY", fields=["customfield_10056"])
    _, kwargs = mock_client.search.call_args
    assert "customfield_10056" in kwargs["fields"]
    assert "summary" in kwargs["fields"]  # a default field is still requested


def test_list_fields_returns_client_result():
    mock_client = MagicMock()
    mock_client.list_fields.return_value = [{"id": "summary", "name": "Summary", "custom": False}]
    with patch("tools.list_fields.get_client", return_value=mock_client):
        result = list_fields.list_fields()
    assert result == [{"id": "summary", "name": "Summary", "custom": False}]


def test_triage_delegates_to_client_and_returns_result():
    mock_client = MagicMock()
    mock_client.triage.return_value = {"project": "PAYKAN", "issue_count": 0, "stories": []}
    with patch("tools.triage.get_client", return_value=mock_client):
        result = triage.triage(project="PAYKAN")
    assert result["project"] == "PAYKAN"
    mock_client.triage.assert_called_once_with(
        project="PAYKAN", parent_issue_types=None, max_results=200
    )


def test_triage_wraps_errors_as_json():
    mock_client = MagicMock()
    from lib.jira_client import JiraValidationError

    mock_client.triage.side_effect = JiraValidationError("no project")
    with patch("tools.triage.get_client", return_value=mock_client):
        result = triage.triage()
    assert "error" in result


def test_worklog_requires_confirmation_by_default():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work")
    assert result["confirmed"] is False
    assert result["requires_confirmation"] is True
    mock_client.add_worklog.assert_not_called()


def test_worklog_executes_when_confirmed():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    mock_client.add_worklog.return_value = Worklog("1", "Alice", "2h", 7200, "did work", "2026-07-21")
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work", confirm=True)
    assert result["confirmed"] is True
    mock_client.add_worklog.assert_called_once_with("PAY-1", 7200, "did work", started=None)


def test_worklog_with_date_passes_formatted_started_timestamp():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    mock_client.add_worklog.return_value = Worklog("1", "Alice", "2h", 7200, "did work", "2026-07-20")
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work", date="2026-07-20T09:00:00+00:00", confirm=True)
    assert result["confirmed"] is True
    mock_client.add_worklog.assert_called_once_with(
        "PAY-1", 7200, "did work", started="2026-07-20T09:00:00.000+0000"
    )


def test_worklog_pending_action_includes_date_and_started():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work", date="2026-07-20")
    assert result["requires_confirmation"] is True
    assert result["pending_action"]["date"] == "2026-07-20"
    assert result["pending_action"]["started"].startswith("2026-07-20T")


def test_worklog_rejects_unparseable_date():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work", date="last tuesday")
    assert result["error"]["type"] == "invalid_input"


def test_worklog_auto_confirm_config_skips_gate():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    mock_client.add_worklog.return_value = Worklog("1", "Alice", "2h", 7200, "did work", "2026-07-21")
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "2h", "did work")
    assert result["confirmed"] is True


def test_worklog_rejects_bad_duration():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog.get_client", return_value=mock_client):
        result = worklog.worklog("PAY-1", "not-a-duration", "did work")
    assert result["error"]["type"] == "invalid_input"


def test_worklog_edit_requires_confirmation_by_default():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.worklog_edit.get_client", return_value=mock_client):
        result = worklog_edit.worklog_edit("PAY-1", "28459", duration="1h")
    assert result["confirmed"] is False
    assert result["requires_confirmation"] is True
    mock_client.update_worklog.assert_not_called()


def test_worklog_edit_executes_when_confirmed():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    mock_client.update_worklog.return_value = Worklog("28459", "Alice", "1h", 3600, "did work", "2026-07-20")
    with patch("tools.worklog_edit.get_client", return_value=mock_client):
        result = worklog_edit.worklog_edit("PAY-1", "28459", duration="1h", confirm=True)
    assert result["confirmed"] is True
    mock_client.update_worklog.assert_called_once_with(
        "PAY-1", "28459", duration_seconds=3600, description=None, started=None
    )


def test_worklog_edit_rejects_when_no_fields_given():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog_edit.get_client", return_value=mock_client):
        result = worklog_edit.worklog_edit("PAY-1", "28459")
    assert result["error"]["type"] == "invalid_input"
    mock_client.update_worklog.assert_not_called()


def test_worklog_edit_rejects_bad_duration():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog_edit.get_client", return_value=mock_client):
        result = worklog_edit.worklog_edit("PAY-1", "28459", duration="not-a-duration")
    assert result["error"]["type"] == "invalid_input"


def test_worklog_edit_rejects_unparseable_date():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog_edit.get_client", return_value=mock_client):
        result = worklog_edit.worklog_edit("PAY-1", "28459", date="last tuesday")
    assert result["error"]["type"] == "invalid_input"


def test_worklog_edit_with_date_passes_formatted_started_timestamp():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    mock_client.update_worklog.return_value = Worklog("28459", "Alice", "1h", 3600, "did work", "2026-07-20")
    with patch("tools.worklog_edit.get_client", return_value=mock_client):
        worklog_edit.worklog_edit("PAY-1", "28459", date="2026-07-20T09:00:00+00:00")
    mock_client.update_worklog.assert_called_once_with(
        "PAY-1", "28459", duration_seconds=None, description=None, started="2026-07-20T09:00:00.000+0000"
    )


def test_worklog_delete_requires_confirmation_by_default():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.worklog_delete.get_client", return_value=mock_client):
        result = worklog_delete.worklog_delete("PAY-1", "28459")
    assert result["confirmed"] is False
    assert result["requires_confirmation"] is True
    mock_client.delete_worklog.assert_not_called()


def test_worklog_delete_executes_when_confirmed():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.worklog_delete.get_client", return_value=mock_client):
        result = worklog_delete.worklog_delete("PAY-1", "28459", confirm=True)
    assert result["confirmed"] is True
    assert result["deleted"] is True
    mock_client.delete_worklog.assert_called_once_with("PAY-1", "28459")


def test_worklog_delete_auto_confirm_config_skips_gate():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=True)
    with patch("tools.worklog_delete.get_client", return_value=mock_client):
        result = worklog_delete.worklog_delete("PAY-1", "28459")
    assert result["confirmed"] is True


def test_transition_requires_confirmation_by_default():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    with patch("tools.transition.get_client", return_value=mock_client):
        result = transition.transition("PAY-1", "Review")
    assert result["requires_confirmation"] is True
    mock_client.transition_issue.assert_not_called()


def test_transition_executes_when_confirmed():
    mock_client = MagicMock()
    mock_client.config = _fake_config(auto_confirm=False)
    mock_client.transition_issue.return_value = {
        "issue_key": "PAY-1",
        "transitioned_to": "Review",
        "transition_name": "Move to Review",
        "success": True,
    }
    with patch("tools.transition.get_client", return_value=mock_client):
        result = transition.transition("PAY-1", "Review", confirm=True)
    assert result["confirmed"] is True
    assert result["transitioned_to"] == "Review"


def test_worklog_report_aggregates_within_window_only():
    mock_client = MagicMock()
    mock_client.get_current_user.return_value = User(account_id="alice", display_name="Alice")
    mock_client.search.return_value = [_issue(original_estimate_seconds=3600)]
    mock_client.get_worklogs.return_value = [
        Worklog("1", "Alice", "2h", 7200, "in range", "2026-07-20T09:00:00.000+0000"),
        Worklog("2", "Alice", "1h", 3600, "too old", "2026-06-01T09:00:00.000+0000"),
        Worklog("3", "Bob", "3h", 10800, "not mine", "2026-07-20T09:00:00.000+0000"),
    ]
    with patch("tools.worklog_report.get_client", return_value=mock_client):
        result = worklog_report.worklog_report(since="2026-07-01")

    assert result["issue_count"] == 1
    assert result["total_logged_seconds"] == 7200
    assert result["total_original_estimate_seconds"] == 3600
    assert result["total_delta_seconds"] == 3600
    assert len(result["issues"][0]["worklogs"]) == 1
    assert result["issues"][0]["worklogs"][0]["comment"] == "in range"


def test_worklog_report_omits_issues_with_no_matching_worklogs():
    mock_client = MagicMock()
    mock_client.get_current_user.return_value = User(account_id="alice", display_name="Alice")
    mock_client.search.return_value = [_issue()]
    mock_client.get_worklogs.return_value = [
        Worklog("1", "Bob", "1h", 3600, "not mine", "2026-07-20T09:00:00.000+0000"),
    ]
    with patch("tools.worklog_report.get_client", return_value=mock_client):
        result = worklog_report.worklog_report(since="2026-07-01")

    assert result["issue_count"] == 0
    assert result["issues"] == []


def test_worklog_report_rejects_until_before_since():
    result = worklog_report.worklog_report(since="2026-07-15", until="2026-07-01")
    assert result["error"]["type"] == "invalid_input"


def test_worklog_report_rejects_unparseable_date():
    result = worklog_report.worklog_report(since="not-a-date")
    assert result["error"]["type"] == "invalid_input"


def test_sprint_returns_board_and_active_sprint():
    mock_client = MagicMock()
    from lib.models import Board

    mock_client.current_board.return_value = Board(3, "PAY Board", "scrum")
    mock_client.current_sprint.return_value = Sprint(55, "Sprint 12", "active", "2026-07-01", "2026-07-15", "Ship it", 3)
    with patch("tools.sprint.get_client", return_value=mock_client):
        result = sprint.sprint()
    assert result["board"]["name"] == "PAY Board"
    assert result["sprint"]["goal"] == "Ship it"
