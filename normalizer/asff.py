"""Build and validate ASFF findings — the one schema every source lands in.

This is a deliberate *subset* of ASFF (see ADR-004): the fields Security Hub
requires for BatchImportFindings, plus Compliance and ProductFields. Optional
blocks we don't populate (Network, Process, Malware, ...) are omitted rather
than stubbed with empty values — an auditor reading a finding should never
wonder whether an empty field means "checked, nothing there" or "never
collected."
"""

from __future__ import annotations

from datetime import UTC, datetime

SEVERITY_LABELS = ("INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL")
COMPLIANCE_STATUSES = ("PASSED", "WARNING", "FAILED", "NOT_AVAILABLE")

# Status of the underlying check -> ASFF Compliance.Status
_FROM_CONFIG = {
    "COMPLIANT": "PASSED",
    "NON_COMPLIANT": "FAILED",
    "NOT_APPLICABLE": "NOT_AVAILABLE",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_finding(
    *,
    source: str,  # which pipeline produced this: config-rule | prowler | collector | tracker
    account_id: str,
    region: str,
    resource_type: str,
    resource_id: str,
    compliance_status: str,  # PASSED | WARNING | FAILED | NOT_AVAILABLE
    title: str,
    description: str,
    failed_severity: str = "MEDIUM",
    control_id: str | None = None,
    generator_id: str | None = None,
    product_fields: dict[str, str] | None = None,
    created_at: str | None = None,
) -> dict:
    """Assemble one ASFF finding.

    Id is deterministic (source/control/resource), NOT a uuid: Security Hub
    upserts on Id, so re-running a check updates the existing finding's
    UpdatedAt instead of growing an endless pile of duplicates. Finding
    volume is the Security Hub cost knob — idempotent Ids are the guardrail.
    """
    now = _now()
    severity = failed_severity if compliance_status == "FAILED" else "INFORMATIONAL"

    fields = {"ccm:source": source}
    if control_id:
        # Late import avoided: catalog enrichment is the adapters' job; the
        # builder only records the linkage it was given.
        fields["ccm:control_id"] = control_id
    if product_fields:
        fields.update(product_fields)

    finding = {
        "SchemaVersion": "2018-10-08",
        "Id": f"{source}/{control_id or 'unmapped'}/{resource_id}",
        "ProductArn": f"arn:aws:securityhub:{region}:{account_id}:product/{account_id}/default",
        "GeneratorId": generator_id or f"ccm/{source}",
        "AwsAccountId": account_id,
        "Types": ["Software and Configuration Checks/Continuous Control Monitoring"],
        "CreatedAt": created_at or now,
        "UpdatedAt": now,
        "Severity": {"Label": severity},
        "Title": title,
        "Description": description[:1024],
        "Resources": [{"Type": resource_type, "Id": resource_id, "Region": region}],
        "Compliance": {"Status": compliance_status},
        "ProductFields": fields,
        "RecordState": "ACTIVE",
        "Workflow": {"Status": "NEW"},
    }
    validate(finding)
    return finding


def compliance_from_config(config_compliance: str) -> str:
    return _FROM_CONFIG[config_compliance]


class InvalidFinding(ValueError):
    pass


_REQUIRED = (
    "SchemaVersion",
    "Id",
    "ProductArn",
    "GeneratorId",
    "AwsAccountId",
    "Types",
    "CreatedAt",
    "UpdatedAt",
    "Severity",
    "Title",
    "Description",
    "Resources",
)


def validate(finding: dict) -> None:
    """Reject malformed findings at the boundary, not inside Security Hub.

    BatchImportFindings reports per-finding failures in its response body
    with terse reasons; failing fast locally with a readable message is
    cheaper than debugging FailedFindings counts.
    """
    missing = [k for k in _REQUIRED if not finding.get(k)]
    if missing:
        raise InvalidFinding(f"missing required ASFF fields: {missing}")

    label = finding["Severity"].get("Label")
    if label not in SEVERITY_LABELS:
        raise InvalidFinding(f"Severity.Label {label!r} not in {SEVERITY_LABELS}")

    status = finding.get("Compliance", {}).get("Status")
    if status not in COMPLIANCE_STATUSES:
        raise InvalidFinding(f"Compliance.Status {status!r} not in {COMPLIANCE_STATUSES}")

    for res in finding["Resources"]:
        if not res.get("Type") or not res.get("Id"):
            raise InvalidFinding(f"resource missing Type/Id: {res}")

    for ts_field in ("CreatedAt", "UpdatedAt"):
        if not finding[ts_field].endswith("Z"):
            raise InvalidFinding(f"{ts_field} must be UTC ISO-8601 ending in Z")
