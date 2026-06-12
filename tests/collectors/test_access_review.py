from datetime import UTC, datetime

from collectors.access_review import collect, quarter_start
from tests.collectors.fake_github import BrokenGitHub, FakeGitHub

NOW = datetime(2026, 6, 12, tzinfo=UTC)  # Q2: quarter began 2026-04-01
REPO = "Dwsilky/ccm-reference"
ISSUES_PATH = f"/repos/{REPO}/issues"


def _issue(number, closed_at, **extra):
    return {
        "number": number,
        "closed_at": closed_at,
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        **extra,
    }


def test_quarter_start():
    assert quarter_start(NOW) == datetime(2026, 4, 1, tzinfo=UTC)
    assert quarter_start(datetime(2026, 1, 15, tzinfo=UTC)) == datetime(
        2026, 1, 1, tzinfo=UTC
    )


def test_review_closed_this_quarter_passes_with_evidence():
    client = FakeGitHub({ISSUES_PATH: [_issue(12, "2026-05-30T17:01:00Z")]})
    result = collect(REPO, client=client, now=NOW)
    assert result["status"] == "PASS"
    assert result["evidence"]["issue"] == 12
    assert result["evidence"]["quarter_start"] == "2026-04-01"


def test_stale_review_returned_by_since_is_not_counted():
    # GitHub's `since` filters on updated_at: editing an old Q4 ticket today
    # resurfaces it. closed_at is what the control asserts on.
    client = FakeGitHub({ISSUES_PATH: [_issue(3, "2025-12-19T09:00:00Z")]})
    result = collect(REPO, client=client, now=NOW)
    assert result["status"] == "FAIL"
    assert result["evidence"]["matches"] == 0


def test_pull_requests_are_not_review_tickets():
    pr_shaped = _issue(40, "2026-05-02T10:00:00Z", pull_request={"url": "..."})
    client = FakeGitHub({ISSUES_PATH: [pr_shaped]})
    assert collect(REPO, client=client, now=NOW)["status"] == "FAIL"


def test_api_failure_is_error_not_fail():
    result = collect(REPO, client=BrokenGitHub(), now=NOW)
    assert result["status"] == "ERROR"
    assert "GitHub" in result["summary"]
