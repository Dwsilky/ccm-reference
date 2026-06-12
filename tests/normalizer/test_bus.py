import boto3
import pytest
from moto import mock_aws

from normalizer.adapters import from_collector
from normalizer.asff import InvalidFinding
from normalizer.bus import LocalBus, SecurityHubBus


def _finding(resource_id="Dwsilky/ccm-reference"):
    return from_collector(
        {
            "control_id": "CCM-13",
            "status": "FAIL",
            "resource_type": "GitHubRepo",
            "resource_id": resource_id,
            "summary": "no review ticket",
        },
        account_id="123456789012",
    )


def test_local_bus_round_trips_findings(tmp_path):
    bus = LocalBus(tmp_path / "findings.jsonl")
    assert bus.publish([_finding("a"), _finding("b")]) == 2
    assert bus.publish([_finding("c")]) == 1  # appends, not overwrites

    read_back = bus.read_all()
    assert [f["Resources"][0]["Id"] for f in read_back] == ["a", "b", "c"]


def test_local_bus_rejects_invalid_findings_before_writing(tmp_path):
    bus = LocalBus(tmp_path / "findings.jsonl")
    broken = _finding()
    del broken["AwsAccountId"]
    with pytest.raises(InvalidFinding):
        bus.publish([broken])
    assert bus.read_all() == []


@mock_aws
def test_security_hub_bus_imports_via_batch_api():
    session = boto3.Session()
    session.client("securityhub").enable_security_hub()
    assert SecurityHubBus(session).publish([_finding()]) == 1


def test_security_hub_partial_failure_raises_not_silently_drops():
    # BatchImportFindings returns 200 with FailedCount on partial failure.
    class RejectingClient:
        def batch_import_findings(self, Findings):
            return {
                "SuccessCount": 0,
                "FailedCount": len(Findings),
                "FailedFindings": [
                    {"Id": f["Id"], "ErrorMessage": "InvalidInput"} for f in Findings
                ],
            }

    class FakeSession:
        def client(self, name):
            return RejectingClient()

    with pytest.raises(RuntimeError, match="rejected 1 finding"):
        SecurityHubBus(FakeSession()).publish([_finding()])
