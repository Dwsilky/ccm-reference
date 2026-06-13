"""Source-native output -> ASFF. One adapter per source type.

This module is the scaling pattern of the whole repo: adding a control means
emitting one of these three shapes, never touching the bus or router. Each
adapter enriches ProductFields with catalog metadata (CSF / 800-53 / bucket)
so a finding is audit-traceable back to the framework without a lookup.
"""

from __future__ import annotations

from normalizer.asff import build_finding, compliance_from_config
from normalizer.catalog import Control, by_prowler_check, load_catalog

# Prowler OCSF severity strings -> ASFF labels. Prowler "Informational" maps
# to INFORMATIONAL even on FAIL — if the scanner says it's informational, we
# don't inflate it.
_PROWLER_SEVERITY = {
    "Informational": "INFORMATIONAL",
    "Low": "LOW",
    "Medium": "MEDIUM",
    "High": "HIGH",
    "Critical": "CRITICAL",
}


def _catalog_fields(control: Control) -> dict[str, str]:
    return {
        "ccm:bucket": control.bucket,
        "ccm:csf": control.csf,
        "ccm:nist_800_53": ",".join(control.nist_800_53),
    }


def from_config_evaluation(evaluation, control_id: str, account_id: str, region: str) -> dict:
    """Adapt a config-rules Evaluation (shared/evaluator.py dataclass).

    In production this path is redundant — the Config->Security Hub native
    integration forwards rule results already. It exists here because the
    local pipeline has no Config service, and because writing it makes the
    'what the integration does for you' tradeoff concrete (ADR-004).
    """
    control = load_catalog()[control_id]
    return build_finding(
        source="config-rule",
        control_id=control_id,
        generator_id=f"ccm/config-rule/{control.source.rsplit('/', 1)[-1]}",
        account_id=account_id,
        region=region,
        resource_type=evaluation.resource_type,
        resource_id=evaluation.resource_id,
        compliance_status=compliance_from_config(evaluation.compliance),
        title=f"{control_id}: {control.name}",
        description=evaluation.annotation or control.name,
        failed_severity=control.severity,
        product_fields=_catalog_fields(control),
    )


def from_prowler(check: dict) -> dict:
    """Adapt one Prowler v4 OCSF finding (one JSON object from the output array).

    Attribution to a CCM control is best-effort via prowler_checks in the
    catalog. Unmapped checks still normalize — dropping scanner findings
    because our catalog hasn't claimed them yet would hide real exposure —
    they just carry ccm:control_id absent for the coverage report to count
    honestly.
    """
    event_code = check["metadata"]["event_code"]
    resource = check["resources"][0]
    status_code = check["status_code"]  # PASS | FAIL | MANUAL

    control = by_prowler_check().get(event_code)
    severity = _PROWLER_SEVERITY.get(check.get("severity", "Medium"), "MEDIUM")

    fields = {"prowler:event_code": event_code, "prowler:uid": check["finding_info"]["uid"]}
    if control:
        fields.update(_catalog_fields(control))

    return build_finding(
        source="prowler",
        control_id=control.id if control else None,
        generator_id=f"ccm/prowler/{event_code}",
        account_id=check["cloud"]["account"]["uid"],
        region=check["cloud"]["region"],
        resource_type=resource["type"],
        resource_id=resource["uid"],
        compliance_status="PASSED" if status_code == "PASS" else "FAILED",
        title=check["finding_info"]["title"],
        description=check.get("status_detail") or check.get("message", ""),
        failed_severity=severity,
        product_fields=fields,
        created_at=check["finding_info"].get("created_time_dt"),
    )


# Contract for Session-4 collectors: the minimal dict a collector must emit.
COLLECTOR_REQUIRED_KEYS = ("control_id", "status", "resource_type", "resource_id", "summary")


def from_collector(
    result: dict, account_id: str, region: str = "global", source: str = "collector"
) -> dict:
    """Adapt a custom collector result.

    Collectors assert on evidence ("a review ticket closed this quarter"),
    so their statuses are PASS / FAIL / ERROR — ERROR meaning the evidence
    source itself was unreachable, which maps to NOT_AVAILABLE rather than
    FAILED: 'we couldn't check' must never be reported as 'it failed', and
    silently passing would be worse.

    The judgment tracker reuses this contract with source="tracker" so its
    findings are distinguishable on the bus while flowing the same path.
    """
    missing = [k for k in COLLECTOR_REQUIRED_KEYS if k not in result]
    if missing:
        raise ValueError(f"collector result missing keys: {missing}")

    control = load_catalog()[result["control_id"]]
    status_map = {"PASS": "PASSED", "FAIL": "FAILED", "ERROR": "NOT_AVAILABLE"}

    fields = _catalog_fields(control)
    for key, value in result.get("evidence", {}).items():
        fields[f"evidence:{key}"] = str(value)

    return build_finding(
        source=source,
        control_id=control.id,
        generator_id=f"ccm/{source}/{control.source.rsplit('/', 1)[-1]}",
        account_id=account_id,
        region=region,
        resource_type=result["resource_type"],
        resource_id=result["resource_id"],
        compliance_status=status_map[result["status"]],
        title=f"{control.id}: {control.name}",
        description=result["summary"],
        failed_severity=control.severity,
        product_fields=fields,
    )
