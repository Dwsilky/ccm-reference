import boto3
from moto import mock_aws

from src.root_access_keys.handler import evaluate
from tests.support import FakeSession, FakeSTS


@mock_aws
def test_compliant_when_no_root_keys():
    [result] = evaluate({}, boto3.Session())
    assert result.compliance == "COMPLIANT"
    assert result.resource_type == "AWS::::Account"


def test_non_compliant_when_root_keys_exist():
    # moto can't create root-account access keys, so fake the one API call
    # the handler makes (see ADR-002).
    class IAMWithRootKeys:
        def get_account_summary(self):
            return {"SummaryMap": {"AccountAccessKeysPresent": 1}}

    [result] = evaluate({}, FakeSession(sts=FakeSTS(), iam=IAMWithRootKeys()))
    assert result.compliance == "NON_COMPLIANT"
    assert "1 active access key" in result.annotation
