"""The thesis test: three different sources, one schema, one bus.

If this test holds, adding control #22 means adding a source — never
touching the bus or the router. This is the property the whole repo exists
to demonstrate.
"""

import json
from pathlib import Path

import boto3
from moto import mock_aws

from normalizer.adapters import from_collector, from_config_evaluation, from_prowler
from normalizer.asff import validate
from normalizer.bus import LocalBus
from src.s3_public_access_block.handler import evaluate as evaluate_pab

SAMPLES = Path(__file__).resolve().parents[2] / "normalizer" / "samples" / "prowler"


@mock_aws
def test_three_sources_land_identically_on_one_bus(tmp_path):
    # Source 1: a real Config-rule evaluation against moto state.
    session = boto3.Session()
    [evaluation] = evaluate_pab({}, session)
    account_id = session.client("sts").get_caller_identity()["Account"]
    config_finding = from_config_evaluation(evaluation, "CCM-01", account_id, "us-east-1")

    # Source 2: vendored Prowler scanner output.
    prowler_raw = json.loads((SAMPLES / "findings.ocsf.json").read_text(encoding="utf-8"))
    prowler_findings = [from_prowler(check) for check in prowler_raw]

    # Source 3: a custom collector result.
    collector_finding = from_collector(
        {
            "control_id": "CCM-13",
            "status": "PASS",
            "resource_type": "GitHubRepo",
            "resource_id": "Dwsilky/ccm-reference",
            "summary": "Access review issue #12 closed 2026-05-30.",
        },
        account_id=account_id,
    )

    bus = LocalBus(tmp_path / "findings.jsonl")
    bus.publish([config_finding, *prowler_findings, collector_finding])

    landed = bus.read_all()
    assert len(landed) == 5

    # One schema: every finding validates and exposes the same spine,
    # regardless of which source produced it.
    for finding in landed:
        validate(finding)

    sources = {f["ProductFields"]["ccm:source"] for f in landed}
    assert sources == {"config-rule", "prowler", "collector"}

    # The router will never need to know which source a finding came from:
    # severity, compliance, resource, and control linkage are uniform.
    for finding in landed:
        assert finding["Severity"]["Label"]
        assert finding["Compliance"]["Status"]
        assert finding["Resources"][0]["Id"]
