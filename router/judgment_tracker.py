"""CCM-17..21 — human-judgment controls: automate the reminder, only. (ADR-003)

Policy adequacy, risk acceptance, vendor assessments, tabletops, data
classification — a machine cannot judge any of these, and a script that
pretends to is assurance theater. What a machine CAN do honestly:

  * know the attestation cadence for each control,
  * know when a human last attested (with what artifact),
  * emit an overdue finding into the same bus every other control uses,
    so the reminder gets an owner, an SLA, and an audit trail like any
    machine finding.

A control with no attestation on record is FAIL, not "pending" — an
attestation that has never happened is exactly as overdue as one that
expired, and "pending since forever" is how these controls quietly die.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

REGISTER_PATH = Path(__file__).resolve().parents[1] / "mappings" / "judgment-register.yaml"


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def collect_all(register_path: str | Path = REGISTER_PATH,
                now: datetime | None = None) -> list[dict]:
    """One collector-contract dict per registered judgment control."""
    now = now or datetime.now(UTC)
    today = now.date()
    register = yaml.safe_load(Path(register_path).read_text(encoding="utf-8"))["register"]

    results = []
    for entry in register:
        control_id = entry["control"]
        cadence = int(entry["cadence_days"])
        last = _as_date(entry.get("last_attested"))
        base = {
            "control_id": control_id,
            "resource_type": "AttestationRegister",
            "resource_id": f"judgment-register:{control_id}",
        }
        evidence = {
            "owner": entry.get("owner", ""),
            "cadence_days": cadence,
            "last_attested": last.isoformat() if last else "never",
            "artifact": entry.get("artifact", ""),
        }

        if last is None:
            results.append({
                **base, "status": "FAIL",
                "summary": f"{control_id}: no attestation on record "
                f"(cadence {cadence}d). Never attested is overdue, not pending.",
                "evidence": evidence,
            })
            continue

        age = (today - last).days
        if age > cadence:
            results.append({
                **base, "status": "FAIL",
                "summary": f"{control_id}: attestation overdue by {age - cadence}d "
                f"(last {last}, cadence {cadence}d). Artifact then: "
                f"{entry.get('artifact', 'n/a')}.",
                "evidence": {**evidence, "days_overdue": age - cadence},
            })
        else:
            results.append({
                **base, "status": "PASS",
                "summary": f"{control_id}: attestation current (last {last}, "
                f"due again in {cadence - age}d).",
                "evidence": {**evidence, "days_until_due": cadence - age},
            })
    return results


if __name__ == "__main__":
    from collectors.runner import publish

    for result in collect_all():
        publish(result, source="tracker")
        print(json.dumps(result, indent=2, default=str))
