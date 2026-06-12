"""In-memory stand-in for collectors.github_api.GitHubClient."""


class FakeGitHub:
    def __init__(self, routes: dict[str, list[dict]]):
        self.routes = routes
        self.calls: list[str] = []

    def get_all(self, path: str, **params) -> list[dict]:
        self.calls.append(path)
        return self.routes[path]


class BrokenGitHub:
    def get_all(self, path: str, **params):
        raise ConnectionError("simulated network failure")
