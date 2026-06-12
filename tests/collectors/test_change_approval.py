from datetime import UTC, datetime

from collectors.change_approval import collect
from tests.collectors.fake_github import BrokenGitHub, FakeGitHub

NOW = datetime(2026, 6, 12, tzinfo=UTC)
REPO = "Dwsilky/ccm-reference"
PULLS = f"/repos/{REPO}/pulls"


def _pr(number, merged_at, author="derek"):
    return {"number": number, "merged_at": merged_at, "user": {"login": author}}


def _review(state, user, submitted_at):
    return {"state": state, "user": {"login": user}, "submitted_at": submitted_at}


def test_pre_merge_approval_by_non_author_passes():
    client = FakeGitHub(
        {
            PULLS: [_pr(7, "2026-06-01T12:00:00Z")],
            f"{PULLS}/7/reviews": [_review("APPROVED", "reviewer", "2026-06-01T11:00:00Z")],
        }
    )
    result = collect(REPO, client=client, now=NOW)
    assert result["status"] == "PASS"
    assert result["evidence"]["population"] == 1


def test_self_approval_does_not_count():
    client = FakeGitHub(
        {
            PULLS: [_pr(8, "2026-06-01T12:00:00Z", author="derek")],
            f"{PULLS}/8/reviews": [_review("APPROVED", "derek", "2026-06-01T11:00:00Z")],
        }
    )
    result = collect(REPO, client=client, now=NOW)
    assert result["status"] == "FAIL"
    assert result["evidence"]["unapproved"] == [8]


def test_post_merge_approval_is_paperwork_not_a_gate():
    client = FakeGitHub(
        {
            PULLS: [_pr(9, "2026-06-01T12:00:00Z")],
            f"{PULLS}/9/reviews": [_review("APPROVED", "reviewer", "2026-06-01T15:00:00Z")],
        }
    )
    assert collect(REPO, client=client, now=NOW)["status"] == "FAIL"


def test_changes_requested_is_not_approval():
    client = FakeGitHub(
        {
            PULLS: [_pr(10, "2026-06-01T12:00:00Z")],
            f"{PULLS}/10/reviews": [
                _review("CHANGES_REQUESTED", "reviewer", "2026-06-01T11:00:00Z")
            ],
        }
    )
    assert collect(REPO, client=client, now=NOW)["status"] == "FAIL"


def test_merges_outside_window_are_out_of_population():
    client = FakeGitHub({PULLS: [_pr(2, "2026-01-10T12:00:00Z")]})
    result = collect(REPO, client=client, now=NOW)
    assert result["status"] == "PASS"
    assert result["evidence"]["population"] == 0
    assert "no exceptions noted" in result["summary"]


def test_api_failure_is_error():
    assert collect(REPO, client=BrokenGitHub(), now=NOW)["status"] == "ERROR"
