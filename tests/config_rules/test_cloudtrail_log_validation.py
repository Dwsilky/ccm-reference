import boto3
from moto import mock_aws

from src.cloudtrail_log_validation.handler import evaluate


def _trail(session, name, validation):
    s3 = session.client("s3")
    bucket = f"{name}-logs"
    s3.create_bucket(Bucket=bucket)
    session.client("cloudtrail").create_trail(
        Name=name, S3BucketName=bucket, EnableLogFileValidation=validation
    )


@mock_aws
def test_no_trails_is_not_applicable_not_failing():
    # Absence of CloudTrail is CCM-09's finding; one root cause, one ticket.
    [result] = evaluate({}, boto3.Session())
    assert result.compliance == "NOT_APPLICABLE"


@mock_aws
def test_each_trail_judged_independently():
    session = boto3.Session()
    _trail(session, "validated", validation=True)
    _trail(session, "unvalidated", validation=False)

    results = {e.resource_id: e.compliance for e in evaluate({}, session)}
    assert results == {"validated": "COMPLIANT", "unvalidated": "NON_COMPLIANT"}
