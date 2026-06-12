"""CCM-16 — change approvals enforced on merges. (PR.IP-3 / CM-3, attestable)

WHAT THE PLATFORM COULDN'T DO
    Change management lives in the SCM, not the cloud account. No Config rule
    or scanner sees whether a merge carried a real approval — and a branch
    protection *setting* only proves the gate was configured, not that it
    held for every change in the audit window.

WHAT THIS DOES INSTEAD
    Pulls every PR merged in the window and asserts each one had an APPROVED
    review that was (a) submitted *before* the merge and (b) not by the PR's
    own author. Post-merge approvals are explicitly not a gate — they're
    paperwork after the change already shipped.

SOURCE -> DESTINATION
    GitHub Pulls + Reviews API -> collector contract dict ->
    normalizer.from_collector -> ASFF -> bus.

Judgment call: an empty population (no merges in the window) is PASS with
population=0 in evidence — audit language for "no exceptions noted" — and is
kept distinct from ERROR, which means the population couldn't be examined
at all.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from collectors.github_api import GitHubClient

CONTROL_ID = "CCM-16"
DEFAULT_REPO = "Dwsilky/ccm-reference"
WINDOW_DAYS = 30


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _gate_held(pr: dict, reviews: list[dict]) -> bool:
    merged_at = _ts(pr["merged_at"])
    author = pr["user"]["login"]
    return any(
        review["state"] == "APPROVED"
        and review["user"]["login"] != author
        and _ts(review["submitted_at"]) <= merged_at
        for review in reviews
    )


def collect(repo: str = DEFAULT_REPO, client: GitHubClient | None = None,
            window_days: int = WINDOW_DAYS, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    base = {
        "control_id": CONTROL_ID,
        "resource_type": "GitHubRepo",
        "resource_id": repo,
    }

    client = client or GitHubClient()
    try:
        closed = client.get_all(
            f"/repos/{repo}/pulls", state="closed", sort="updated", direction="desc"
        )
        merged = [
            pr for pr in closed if pr.get("merged_at") and _ts(pr["merged_at"]) >= cutoff
        ]
        unapproved = [
            pr["number"]
            for pr in merged
            if not _gate_held(pr, client.get_all(f"/repos/{repo}/pulls/{pr['number']}/reviews"))
        ]
    except Exception as err:  # noqa: BLE001
        return {**base, "status": "ERROR",
                "summary": f"Could not reach GitHub Pulls API: {err}"}

    evidence = {
        "window_days": window_days,
        "population": len(merged),
        "unapproved": unapproved,
    }
    if not merged:
        return {
            **base,
            "status": "PASS",
            "summary": f"No PRs merged into {repo} in the last {window_days} days; "
            "no exceptions noted (population=0).",
            "evidence": evidence,
        }
    if unapproved:
        return {
            **base,
            "status": "FAIL",
            "summary": (
                f"{len(unapproved)} of {len(merged)} PRs merged in the last "
                f"{window_days} days lacked a pre-merge approval by a non-author: "
                f"{unapproved}."
            ),
            "evidence": evidence,
        }
    return {
        **base,
        "status": "PASS",
        "summary": f"All {len(merged)} PRs merged in the last {window_days} days "
        "carried a pre-merge approval by a non-author.",
        "evidence": evidence,
    }


if __name__ == "__main__":
    from collectors.runner import publish

    result = collect()
    publish(result)
    print(json.dumps(result, indent=2, default=str))
