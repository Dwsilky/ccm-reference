"""Minimal GitHub REST client shared by the GitHub-backed collectors.

Deliberately tiny: the collectors are the artifact here, not an SDK. Token
resolution order: explicit arg -> GITHUB_TOKEN env -> `gh auth token` (so a
machine with the gh CLI logged in needs zero extra setup). Unauthenticated
still works for public repos at a low rate limit.
"""

from __future__ import annotations

import os
import subprocess

import requests

API = "https://api.github.com"
PAGE_SIZE = 100

_GH_CANDIDATES = ("gh", r"C:\Program Files\GitHub CLI\gh.exe")


def _gh_cli_token() -> str | None:
    for exe in _GH_CANDIDATES:
        try:
            out = subprocess.run(
                [exe, "auth", "token"], capture_output=True, text=True, timeout=10
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except OSError:
            continue
    return None


class GitHubClient:
    def __init__(self, token: str | None = None, session=None):
        self.http = session or requests.Session()
        token = token or os.environ.get("GITHUB_TOKEN") or _gh_cli_token()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def post(self, path: str, payload: dict) -> dict:
        resp = self.http.post(
            f"{API}{path}", headers=self.headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def get_all(self, path: str, **params) -> list[dict]:
        """Fetch every page; a short page terminates the loop."""
        items: list[dict] = []
        page = 1
        while True:
            resp = self.http.get(
                f"{API}{path}",
                headers=self.headers,
                params={**params, "per_page": PAGE_SIZE, "page": page},
                timeout=30,
            )
            resp.raise_for_status()
            batch = resp.json()
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                return items
            page += 1
