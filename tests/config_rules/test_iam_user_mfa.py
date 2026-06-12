import boto3
from moto import mock_aws

from src.iam_user_mfa.handler import evaluate


def _enable_mfa(iam, username):
    serial = iam.create_virtual_mfa_device(VirtualMFADeviceName=username)[
        "VirtualMFADevice"
    ]["SerialNumber"]
    iam.enable_mfa_device(
        UserName=username,
        SerialNumber=serial,
        AuthenticationCode1="123456",
        AuthenticationCode2="654321",
    )


@mock_aws
def test_console_user_without_mfa_is_non_compliant():
    session = boto3.Session()
    iam = session.client("iam")
    iam.create_user(UserName="alice")
    iam.create_login_profile(UserName="alice", Password="Sup3r-secret-pw!")

    [result] = evaluate({}, session)
    assert result.resource_id == "alice"
    assert result.compliance == "NON_COMPLIANT"


@mock_aws
def test_console_user_with_mfa_is_compliant():
    session = boto3.Session()
    iam = session.client("iam")
    iam.create_user(UserName="bob")
    iam.create_login_profile(UserName="bob", Password="Sup3r-secret-pw!")
    _enable_mfa(iam, "bob")

    [result] = evaluate({}, session)
    assert result.compliance == "COMPLIANT"


@mock_aws
def test_api_only_user_is_not_applicable_not_skipped():
    # Auditors sampling the population must see the user was considered.
    session = boto3.Session()
    session.client("iam").create_user(UserName="service-account")

    [result] = evaluate({}, session)
    assert result.compliance == "NOT_APPLICABLE"
    assert "no console password" in result.annotation
