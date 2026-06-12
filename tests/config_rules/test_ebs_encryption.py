import boto3
from moto import mock_aws

from src.ebs_encryption.handler import evaluate


def _by_type(evaluations):
    return {
        "account": [e for e in evaluations if e.resource_type == "AWS::::Account"],
        "volumes": {
            e.resource_id: e for e in evaluations if e.resource_type == "AWS::EC2::Volume"
        },
    }


@mock_aws
def test_account_default_off_is_flagged_even_with_no_volumes():
    [account] = _by_type(evaluate({}, boto3.Session()))["account"]
    assert account.compliance == "NON_COMPLIANT"
    assert "encryption-by-default" in account.annotation


@mock_aws
def test_account_default_on_is_compliant():
    session = boto3.Session()
    session.client("ec2").enable_ebs_encryption_by_default()
    [account] = _by_type(evaluate({}, session))["account"]
    assert account.compliance == "COMPLIANT"


@mock_aws
def test_existing_volumes_judged_individually():
    session = boto3.Session()
    ec2 = session.client("ec2")
    plain = ec2.create_volume(AvailabilityZone="us-east-1a", Size=8)["VolumeId"]
    cipher = ec2.create_volume(AvailabilityZone="us-east-1a", Size=8, Encrypted=True)[
        "VolumeId"
    ]

    volumes = _by_type(evaluate({}, session))["volumes"]
    assert volumes[plain].compliance == "NON_COMPLIANT"
    assert volumes[cipher].compliance == "COMPLIANT"
