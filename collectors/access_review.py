"""CCM-13 — quarterly access review occurred. (PR.AC-4 / AC-2(3), attestable)

WHAT THE PLATFORM COULDN'T DO
    AWS Config can read IAM *state* (who has access) but has no concept of
    whether a human reviewed that access. The review process lives in a
    ticketing system; no managed rule reaches it.

WHAT THIS DOES INSTEAD
    Queries GitHub Issues for a ticket labeled `access-review` that was
    *closed this quarter*, and emits PASS/FAIL evidence. It proves the review
    ritual happened — deliberately NOT that the review was thorough; that's
    why this control is bucket 2 (attestable), not bucket 1 (see ADR-003).

SOURCE -> DESTINATION
    GitHub Issues API -> collector contract dict -> normalizer.from_collector
    -> ASFF -> bus.

The messy bit: GitHub's `since` parameter filters on *updated_at*, not
closed_at — an old review ticket that someone edits today comes back in the
response. Trusting `since` would let a stale Q4 review evidence Q2, so every
candidate's closed_at is re-checked locally. PRs also surface in the issues
API and are excluded (a PR named "access review" is not a review ticket).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from collectors.github_api import GitHubClient

CONTROL_ID = "CCM-13"
LABEL = "access-review"
DEFAULT_REPO = "Dwsilky/ccm-reference"


def quarter_start(now: datetime) -> datetime:
    first_month = ((now.month - 1) // 3) * 3 + 1
    return datetime(now.year, first_month, 1, tzinfo=UTC)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect(repo: str = DEFAULT_REPO, client: GitHubClient | None = None,
            now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    start = quarter_start(now)
    base = {
        "control_id": CONTROL_ID,
        "resource_type": "GitHubRepo",
        "resource_id": repo,
    }

    client = client or GitHubClient()
    try:
        candidates = client.get_all(
            f"/repos/{repo}/issues",
            labels=LABEL,
            state="closed",
            since=start.isoformat(),
        )
    except Exception as err:  # noqa: BLE001 - any transport failure is the same verdict
        return {**base, "status": "ERROR",
                "summary": f"Could not reach GitHub Issues API: {err}"}

    reviews = [
        issue
        for issue in candidates
        if "pull_request" not in issue and _ts(issue["closed_at"]) >= start
    ]

    if reviews:
        latest = max(reviews, key=lambda i: i["closed_at"])
        return {
            **base,
            "status": "PASS",
            "summary": (
                f"Access review issue #{latest['number']} closed "
                f"{latest['closed_at']} (quarter began {start.date()})."
            ),
            "evidence": {
                "issue": latest["number"],
                "issue_url": latest["html_url"],
                "closed_at": latest["closed_at"],
                "quarter_start": start.date().isoformat(),
                "matches": len(reviews),
            },
        }

    return {
        **base,
        "status": "FAIL",
        "summary": (
            f"No issue labeled '{LABEL}' closed since the quarter began "
            f"({start.date()}) in {repo}."
        ),
        "evidence": {
            "query": f"repo:{repo} label:{LABEL} state:closed closed:>={start.date()}",
            "matches": 0,
            "quarter_start": start.date().isoformat(),
        },
    }


if __name__ == "__main__":
    from collectors.runner import publish

    result = collect()
    publish(result)
    print(json.dumps(result, indent=2, default=str))
