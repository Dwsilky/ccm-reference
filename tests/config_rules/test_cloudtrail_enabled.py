import boto3
from moto import mock_aws

from src.cloudtrail_enabled.handler import evaluate


def _trail(session, name, multi_region, logging=True):
    s3 = session.client("s3")
    bucket = f"{name}-logs"
    s3.create_bucket(Bucket=bucket)
    ct = session.client("cloudtrail")
    ct.create_trail(Name=name, S3BucketName=bucket, IsMultiRegionTrail=multi_region)
    if logging:
        ct.start_logging(Name=name)
    return ct


@mock_aws
def test_no_trails_is_non_compliant():
    [result] = evaluate({}, boto3.Session())
    assert result.compliance == "NON_COMPLIANT"
    assert "no CloudTrail trails" in result.annotation


@mock_aws
def test_single_region_trail_is_not_enough():
    session = boto3.Session()
    _trail(session, "regional", multi_region=False)
    [result] = evaluate({}, session)
    assert result.compliance == "NON_COMPLIANT"
    assert "none are multi-region" in result.annotation


@mock_aws
def test_stopped_multi_region_trail_is_not_enough():
    # DescribeTrails still lists a trail after StopLogging — existence is
    # not logging.
    session = boto3.Session()
    ct = _trail(session, "stopped", multi_region=True)
    ct.stop_logging(Name="stopped")
    [result] = evaluate({}, session)
    assert result.compliance == "NON_COMPLIANT"
    assert "none are logging" in result.annotation


@mock_aws
def test_logging_multi_region_trail_is_compliant():
    session = boto3.Session()
    _trail(session, "org-trail", multi_region=True)
    [result] = evaluate({}, session)
    assert result.compliance == "COMPLIANT"
    assert "org-trail" in result.annotation
