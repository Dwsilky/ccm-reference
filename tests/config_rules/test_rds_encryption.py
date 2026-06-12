import boto3
from moto import mock_aws

from src.rds_encryption.handler import evaluate


def _create_db(rds, name, encrypted):
    rds.create_db_instance(
        DBInstanceIdentifier=name,
        DBInstanceClass="db.t3.micro",
        Engine="postgres",
        AllocatedStorage=20,
        StorageEncrypted=encrypted,
    )


@mock_aws
def test_no_instances_yields_no_evaluations():
    assert evaluate({}, boto3.Session()) == []


@mock_aws
def test_each_instance_judged_independently():
    session = boto3.Session()
    rds = session.client("rds")
    _create_db(rds, "encrypted-db", True)
    _create_db(rds, "plain-db", False)

    results = {e.resource_id: e for e in evaluate({}, session)}
    assert results["encrypted-db"].compliance == "COMPLIANT"
    assert results["plain-db"].compliance == "NON_COMPLIANT"
    # The ticket assignee should learn the remediation path from the finding.
    assert "snapshot" in results["plain-db"].annotation
