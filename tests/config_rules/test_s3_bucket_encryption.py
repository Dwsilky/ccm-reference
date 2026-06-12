import boto3
from moto import mock_aws

from src.s3_bucket_encryption.handler import evaluate


def _put_encryption(s3, bucket, algorithm, key=None):
    rule = {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": algorithm}}
    if key:
        rule["ApplyServerSideEncryptionByDefault"]["KMSMasterKeyID"] = key
    s3.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={"Rules": [rule]},
    )


@mock_aws
def test_no_buckets_yields_no_evaluations():
    assert evaluate({}, boto3.Session()) == []


@mock_aws
def test_unencrypted_bucket_non_compliant():
    session = boto3.Session()
    s3 = session.client("s3")
    s3.create_bucket(Bucket="plain")
    s3.delete_bucket_encryption(Bucket="plain")  # strip any moto/AWS default
    [result] = evaluate({}, session)
    assert result.resource_id == "plain"
    assert result.compliance == "NON_COMPLIANT"


@mock_aws
def test_sse_s3_passes_default_but_fails_require_kms():
    session = boto3.Session()
    s3 = session.client("s3")
    s3.create_bucket(Bucket="sse-s3")
    _put_encryption(s3, "sse-s3", "AES256")

    [lenient] = evaluate({}, session)
    assert lenient.compliance == "COMPLIANT"

    [strict] = evaluate({"RequireKms": "true"}, session)
    assert strict.compliance == "NON_COMPLIANT"
    assert "RequireKms" in strict.annotation


@mock_aws
def test_kms_bucket_passes_strict_mode():
    session = boto3.Session()
    s3 = session.client("s3")
    s3.create_bucket(Bucket="kms-bucket")
    _put_encryption(s3, "kms-bucket", "aws:kms", key="alias/data")
    [result] = evaluate({"RequireKms": "true"}, session)
    assert result.compliance == "COMPLIANT"


@mock_aws
def test_evaluates_every_bucket_independently():
    session = boto3.Session()
    s3 = session.client("s3")
    for name in ("bucket-a", "bucket-b"):
        s3.create_bucket(Bucket=name)
    _put_encryption(s3, "bucket-a", "AES256")
    s3.delete_bucket_encryption(Bucket="bucket-b")

    results = {e.resource_id: e.compliance for e in evaluate({}, session)}
    assert results == {"bucket-a": "COMPLIANT", "bucket-b": "NON_COMPLIANT"}
