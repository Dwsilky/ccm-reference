import boto3
from moto import mock_aws

from src.s3_public_access_block.handler import evaluate

ALL_ON = {
    "BlockPublicAcls": True,
    "IgnorePublicAcls": True,
    "BlockPublicPolicy": True,
    "RestrictPublicBuckets": True,
}


def _account_id(session):
    return session.client("sts").get_caller_identity()["Account"]


@mock_aws
def test_non_compliant_when_no_block_configured():
    session = boto3.Session()
    [result] = evaluate({}, session)
    assert result.compliance == "NON_COMPLIANT"
    assert result.resource_type == "AWS::::Account"
    assert "no account-level" in result.annotation


@mock_aws
def test_compliant_when_all_four_flags_on():
    session = boto3.Session()
    session.client("s3control").put_public_access_block(
        AccountId=_account_id(session), PublicAccessBlockConfiguration=ALL_ON
    )
    [result] = evaluate({}, session)
    assert result.compliance == "COMPLIANT"


@mock_aws
def test_partial_block_is_non_compliant_and_names_the_gap():
    session = boto3.Session()
    session.client("s3control").put_public_access_block(
        AccountId=_account_id(session),
        PublicAccessBlockConfiguration={**ALL_ON, "BlockPublicPolicy": False},
    )
    [result] = evaluate({}, session)
    assert result.compliance == "NON_COMPLIANT"
    assert "BlockPublicPolicy" in result.annotation
