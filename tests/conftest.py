import json

import pytest


@pytest.fixture(autouse=True)
def aws_sandbox(monkeypatch):
    """Fake credentials so boto3 never touches a real account from tests.

    moto intercepts the API calls; these env vars just satisfy the SDK's
    credential chain and pin a region.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    # Belt and braces: fail loudly if a profile would have been picked up.
    monkeypatch.delenv("AWS_PROFILE", raising=False)


def config_event(params: dict | None = None) -> dict:
    """A minimal periodic (ScheduledNotification) Config invocation event."""
    return {
        "invokingEvent": json.dumps(
            {
                "messageType": "ScheduledNotification",
                "notificationCreationTime": "2026-06-12T00:00:00.000Z",
            }
        ),
        "ruleParameters": json.dumps(params or {}),
        "resultToken": "test-token",
        "accountId": "123456789012",
    }
