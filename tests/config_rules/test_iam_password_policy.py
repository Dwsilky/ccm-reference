import boto3
from moto import mock_aws

from src.iam_password_policy.handler import evaluate

STRONG = dict(
    MinimumPasswordLength=14,
    RequireSymbols=True,
    RequireNumbers=True,
    RequireUppercaseCharacters=True,
    RequireLowercaseCharacters=True,
    PasswordReusePrevention=24,
)


@mock_aws
def test_missing_policy_is_non_compliant():
    [result] = evaluate({}, boto3.Session())
    assert result.compliance == "NON_COMPLIANT"
    assert "no account password policy" in result.annotation


@mock_aws
def test_strong_policy_is_compliant():
    session = boto3.Session()
    session.client("iam").update_account_password_policy(**STRONG)
    [result] = evaluate({}, session)
    assert result.compliance == "COMPLIANT"


@mock_aws
def test_weak_policy_names_each_gap():
    session = boto3.Session()
    session.client("iam").update_account_password_policy(
        MinimumPasswordLength=8,
        RequireSymbols=False,
        RequireNumbers=True,
        RequireUppercaseCharacters=True,
        RequireLowercaseCharacters=True,
    )
    [result] = evaluate({}, session)
    assert result.compliance == "NON_COMPLIANT"
    assert "MinimumPasswordLength=8" in result.annotation
    assert "RequireSymbols=false" in result.annotation
    assert "PasswordReusePrevention=0" in result.annotation


@mock_aws
def test_rotation_only_asserted_when_opted_in():
    session = boto3.Session()
    session.client("iam").update_account_password_policy(**STRONG)

    # No MaxPasswordAge set on the policy: fine by default...
    [default] = evaluate({}, session)
    assert default.compliance == "COMPLIANT"

    # ...but a gap once the org opts into a rotation requirement.
    [strict] = evaluate({"MaxPasswordAge": "90"}, session)
    assert strict.compliance == "NON_COMPLIANT"
    assert "MaxPasswordAge" in strict.annotation


@mock_aws
def test_thresholds_overridable_by_rule_parameters():
    session = boto3.Session()
    session.client("iam").update_account_password_policy(
        **{**STRONG, "MinimumPasswordLength": 12, "PasswordReusePrevention": 5}
    )
    [relaxed] = evaluate(
        {"MinimumPasswordLength": "12", "PasswordReusePrevention": "5"}, session
    )
    assert relaxed.compliance == "COMPLIANT"
