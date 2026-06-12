import pytest

from normalizer.asff import InvalidFinding, build_finding, validate


def _finding(**overrides):
    kwargs = dict(
        source="collector",
        control_id="CCM-13",
        account_id="123456789012",
        region="us-east-1",
        resource_type="GitHubRepo",
        resource_id="Dwsilky/ccm-reference",
        compliance_status="FAILED",
        title="t",
        description="d",
        failed_severity="HIGH",
    )
    kwargs.update(overrides)
    return build_finding(**kwargs)


def test_builder_output_passes_its_own_validator():
    validate(_finding())  # build_finding validates internally; belt and braces


def test_passing_findings_are_informational_regardless_of_control_severity():
    finding = _finding(compliance_status="PASSED", failed_severity="CRITICAL")
    assert finding["Severity"]["Label"] == "INFORMATIONAL"


def test_failed_findings_carry_the_control_severity():
    assert _finding()["Severity"]["Label"] == "HIGH"


def test_id_is_deterministic_for_upsert_semantics():
    # Security Hub upserts on Id — rerunning a check must not duplicate.
    assert _finding()["Id"] == _finding()["Id"]
    assert _finding()["Id"] == "collector/CCM-13/Dwsilky/ccm-reference"


def test_long_descriptions_truncated_to_asff_limit():
    assert len(_finding(description="x" * 5000)["Description"]) == 1024


@pytest.mark.parametrize(
    "mutation",
    [
        lambda f: f.pop("AwsAccountId"),
        lambda f: f["Severity"].update(Label="SEVERE"),
        lambda f: f["Compliance"].update(Status="OK"),
        lambda f: f.update(CreatedAt="2026-06-12 10:00:00"),
        lambda f: f["Resources"][0].pop("Id"),
    ],
)
def test_validator_rejects_malformed_findings(mutation):
    finding = _finding()
    mutation(finding)
    with pytest.raises(InvalidFinding):
        validate(finding)
