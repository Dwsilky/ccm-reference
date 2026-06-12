import json
from pathlib import Path

import pytest

from normalizer.adapters import from_collector, from_config_evaluation, from_prowler
from shared.evaluator import Evaluation

SAMPLES = Path(__file__).resolve().parents[2] / "normalizer" / "samples" / "prowler"


def _prowler_sample():
    return json.loads((SAMPLES / "findings.ocsf.json").read_text(encoding="utf-8"))


# --- Config evaluations -----------------------------------------------------


def test_config_evaluation_enriched_from_catalog():
    evaluation = Evaluation(
        "AWS::::Account", "123456789012", "NON_COMPLIANT", "CCM-07: root has keys."
    )
    finding = from_config_evaluation(evaluation, "CCM-07", "123456789012", "us-east-1")

    assert finding["Compliance"]["Status"] == "FAILED"
    assert finding["Severity"]["Label"] == "CRITICAL"  # from controls.yaml
    fields = finding["ProductFields"]
    assert fields["ccm:control_id"] == "CCM-07"
    assert fields["ccm:csf"] == "PR.AC-4"
    assert fields["ccm:nist_800_53"] == "AC-6"
    assert fields["ccm:bucket"] == "machine"


def test_not_applicable_maps_to_not_available_not_passed():
    evaluation = Evaluation("AWS::IAM::User", "svc", "NOT_APPLICABLE", "api-only")
    finding = from_config_evaluation(evaluation, "CCM-06", "123456789012", "us-east-1")
    assert finding["Compliance"]["Status"] == "NOT_AVAILABLE"


# --- Prowler ----------------------------------------------------------------


def test_mapped_prowler_fail_attributes_to_catalog_control():
    [fail, _, _] = _prowler_sample()
    finding = from_prowler(fail)
    assert finding["ProductFields"]["ccm:control_id"] == "CCM-09"
    assert finding["Compliance"]["Status"] == "FAILED"
    assert finding["Severity"]["Label"] == "HIGH"
    assert finding["AwsAccountId"] == "123456789012"


def test_prowler_pass_normalizes_as_informational_passed():
    [_, ok, _] = _prowler_sample()
    finding = from_prowler(ok)
    assert finding["Compliance"]["Status"] == "PASSED"
    assert finding["Severity"]["Label"] == "INFORMATIONAL"
    assert finding["ProductFields"]["ccm:control_id"] == "CCM-01"


def test_unmapped_prowler_check_still_normalizes_without_attribution():
    # Dropping scanner findings our catalog hasn't claimed would hide exposure.
    [_, _, unmapped] = _prowler_sample()
    finding = from_prowler(unmapped)
    assert "ccm:control_id" not in finding["ProductFields"]
    assert finding["Id"].startswith("prowler/unmapped/")
    assert finding["Compliance"]["Status"] == "FAILED"


# --- Collectors -------------------------------------------------------------


def _collector_result(**overrides):
    result = {
        "control_id": "CCM-13",
        "status": "FAIL",
        "resource_type": "GitHubRepo",
        "resource_id": "Dwsilky/ccm-reference",
        "summary": "No access-review issue closed this quarter.",
        "evidence": {"query": "label:access-review closed:>2026-04-01", "matches": 0},
    }
    result.update(overrides)
    return result


def test_collector_result_normalizes_with_evidence_fields():
    finding = from_collector(_collector_result(), account_id="123456789012")
    assert finding["Compliance"]["Status"] == "FAILED"
    assert finding["ProductFields"]["evidence:matches"] == "0"
    assert finding["ProductFields"]["ccm:bucket"] == "attestable"


def test_collector_error_is_not_available_never_failed_or_passed():
    # "We couldn't check" must not read as a pass or a fail.
    finding = from_collector(
        _collector_result(status="ERROR", summary="GitHub API unreachable"),
        account_id="123456789012",
    )
    assert finding["Compliance"]["Status"] == "NOT_AVAILABLE"
    assert finding["Severity"]["Label"] == "INFORMATIONAL"


def test_collector_contract_enforced():
    with pytest.raises(ValueError, match="resource_id"):
        from_collector(
            {"control_id": "CCM-13", "status": "PASS"}, account_id="123456789012"
        )
