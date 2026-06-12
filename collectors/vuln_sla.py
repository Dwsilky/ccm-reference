"""CCM-15 — vulnerability remediation SLAs met. (RS.MI-3 / RA-5, SI-2, attestable)

WHAT THE PLATFORM COULDN'T DO
    Scanners report what's vulnerable *now*; SLA compliance is a property of
    the *timeline* — how long each finding stayed open relative to its
    severity tier. No scanner dashboard answers "did we meet our committed
    remediation windows this period" in evidence form.

WHAT THIS DOES INSTEAD
    Reads a scanner export and computes time-to-remediate per finding:
    fixed findings against (fixed_at - detected_at), still-open findings
    against their current age — an open critical past its window is a breach
    *today*, not on the day someone fixes it.

    Real exports are messy and the parser says so instead of guessing:
      * severity casing varies ("Critical", "HIGH", "medium") — normalized;
      * findings marked status=fixed with a null fixed_at (scanner bug) —
        last_seen is used as the fix bound, noted in evidence;
      * severities outside the SLA table ("Sev3" from a legacy import) are
        *skipped and counted* — silently dropping them would quietly shrink
        the population, silently mapping them would invent an SLA.

SOURCE -> DESTINATION
    scanner export JSON -> collector contract dict ->
    normalizer.from_collector -> ASFF -> bus.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

CONTROL_ID = "CCM-15"
DEFAULT_EXPORT = Path(__file__).parent / "samples" / "scanner" / "vulns.json"

# Committed remediation windows, in days. An org's policy artifact — kept as
# the collector's parameter, not buried in code elsewhere.
SLA_DAYS = {"critical": 15, "high": 30, "medium": 90, "low": 180}


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=UTC)


def collect(export_path: str | Path = DEFAULT_EXPORT,
            sla_days: dict[str, int] = SLA_DAYS, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    export_path = Path(export_path)
    base = {
        "control_id": CONTROL_ID,
        "resource_type": "VulnScannerExport",
        "resource_id": export_path.name,
    }

    try:
        data = json.loads(export_path.read_text(encoding="utf-8"))
        findings = data["findings"]
    except (OSError, ValueError, KeyError) as err:
        return {**base, "status": "ERROR",
                "summary": f"Cannot read scanner export: {err}"}

    breaches: list[str] = []
    skipped: list[str] = []
    inferred_fix_bound = 0
    evaluated = 0

    for finding in findings:
        severity = str(finding.get("severity", "")).lower()
        if severity not in sla_days:
            skipped.append(finding.get("id", "?"))
            continue

        detected = _date(finding["detected_at"])
        fixed_raw = finding.get("fixed_at")
        if not fixed_raw and str(finding.get("status", "")).lower() == "fixed":
            fixed_raw = finding.get("last_seen")  # scanner bug: fixed with null fixed_at
            if fixed_raw:
                inferred_fix_bound += 1

        end = _date(fixed_raw) if fixed_raw else now
        open_days = (end - detected).days
        evaluated += 1
        if open_days > sla_days[severity]:
            state = "fixed" if fixed_raw else "still open"
            breaches.append(
                f"{finding['id']} ({severity} {open_days}d, SLA {sla_days[severity]}d, {state})"
            )

    if evaluated == 0:
        return {**base, "status": "ERROR",
                "summary": f"Export contained no findings with a known severity "
                f"(skipped: {len(skipped)})."}

    evidence = {
        "evaluated": evaluated,
        "breaches": len(breaches),
        "breach_detail": "; ".join(breaches) or "none",
        "skipped_unknown_severity": ",".join(skipped) or "none",
        "fix_date_inferred_from_last_seen": inferred_fix_bound,
        "sla_days": json.dumps(sla_days),
    }

    if breaches:
        return {
            **base,
            "status": "FAIL",
            "summary": f"{len(breaches)} of {evaluated} findings breached their "
            f"remediation SLA: {'; '.join(breaches)}.",
            "evidence": evidence,
        }
    return {
        **base,
        "status": "PASS",
        "summary": f"All {evaluated} findings with known severity met their "
        f"remediation SLAs ({len(skipped)} skipped as unknown severity).",
        "evidence": evidence,
    }


if __name__ == "__main__":
    from collectors.runner import publish

    result = collect()
    publish(result)
    print(json.dumps(result, indent=2, default=str))
