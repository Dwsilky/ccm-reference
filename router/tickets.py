"""Ticket backends: where routed findings become work items.

DryRunTickets is the default everywhere — `route()` against a real repo is
an outward-facing action and must be opted into (`--live`). Both backends
expose the same three methods, so the router never knows which it has.
"""

from __future__ import annotations

import re

from collectors.github_api import GitHubClient

FINDING_MARKER = "ccm-finding-id:"
_MARKER_RE = re.compile(rf"{FINDING_MARKER}\s*(\S+)")


class DryRunTickets:
    """Records what would have been filed; creates nothing."""

    def __init__(self):
        self.created: list[dict] = []

    def existing_finding_ids(self) -> set[str]:
        return set()

    def create(self, payload: dict) -> str:
        self.created.append(payload)
        return f"DRY-RUN-{len(self.created)}"

    def open_tickets(self) -> list[dict]:
        return []


class GitHubTickets:
    """Findings become GitHub Issues labeled `ccm-finding`.

    The finding Id is embedded in the body as an HTML comment
    (`ccm-finding-id: ...`) — that marker, not the title, is the dedupe key,
    because humans edit titles and the router must not re-file a finding
    every time someone renames its issue.
    """

    def __init__(self, repo: str, client: GitHubClient | None = None):
        self.repo = repo
        self.client = client or GitHubClient()

    def _open_issues(self) -> list[dict]:
        return self.client.get_all(
            f"/repos/{self.repo}/issues", state="open", labels="ccm-finding"
        )

    def existing_finding_ids(self) -> set[str]:
        ids = set()
        for issue in self._open_issues():
            if match := _MARKER_RE.search(issue.get("body") or ""):
                ids.add(match.group(1))
        return ids

    def create(self, payload: dict) -> str:
        issue = self.client.post(
            f"/repos/{self.repo}/issues",
            {
                "title": payload["title"],
                "body": payload["body"],
                "labels": payload["labels"],
            },
        )
        return issue["html_url"]

    def open_tickets(self) -> list[dict]:
        tickets = []
        for issue in self._open_issues():
            due = next(
                (
                    label["name"].removeprefix("due:")
                    for label in issue.get("labels", [])
                    if label["name"].startswith("due:")
                ),
                None,
            )
            tickets.append(
                {"ref": issue["html_url"], "title": issue["title"], "due": due}
            )
        return tickets
