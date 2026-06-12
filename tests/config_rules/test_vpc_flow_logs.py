import boto3
from moto import mock_aws

from src.vpc_flow_logs.handler import evaluate


@mock_aws
def test_default_vpc_without_flow_logs_is_flagged():
    # moto provisions a default VPC just like AWS — unused default VPCs are
    # in scope, not exempt.
    results = evaluate({}, boto3.Session())
    assert len(results) >= 1
    assert all(e.compliance == "NON_COMPLIANT" for e in results)


@mock_aws
def test_vpc_with_active_flow_log_is_compliant():
    session = boto3.Session()
    ec2 = session.client("ec2")
    vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]

    session.client("s3").create_bucket(Bucket="flow-archive")
    ec2.create_flow_logs(
        ResourceIds=[vpc_id],
        ResourceType="VPC",
        TrafficType="ALL",
        LogDestinationType="s3",
        LogDestination="arn:aws:s3:::flow-archive",
    )

    results = {e.resource_id: e.compliance for e in evaluate({}, session)}
    assert results[vpc_id] == "COMPLIANT"
    # The default VPC still has no flow log and stays flagged.
    assert "NON_COMPLIANT" in results.values()
