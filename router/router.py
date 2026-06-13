"""The closed loop: finding -> owner -> ticket -> SLA -> evidence artifact.

Reads ASFF findings off the bus and, for each FAILED one: resolves an owner
from mappings/owners.yaml, computes an SLA due date from severity, files a
ticket (dry-run by default), and writes a timestamped evidence artifact so
the chain detected -> tracked -> audit-ready is retrievable per finding.

PASSED findings are counted but not routed (they're evidence, not work).
NOT_AVAILABLE findings — collectors that couldn't reach their evidence —
are surfaced in the report's attention list: an unreachable evidence source
ages into a coverage gap if nobody notices.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from router.tickets import FINDING_MARKER

ROOT = Path(__file__).resolve().parents[1]
OWNERS_PATH = ROOT / "mappings" / "owners.yaml"
EVIDENCE_ROOT = ROOT / "evidence"


def load_routing(path: str | Path = OWNERS_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _safe_name(finding_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", finding_id)


def _dedupe_latest(findings: list[dict]) -> list[dict]:
    """Keep the newest UpdatedAt per Id — the bus is append-only, reruns
    of the same check are updates, not new facts."""
    latest: dict[str, dict] = {}
    for finding in findings:
        existing = latest.get(finding["Id"])
        if existing is None or finding["UpdatedAt"] > existing["UpdatedAt"]:
            latest[finding["Id"]] = finding
    return list(latest.values())


def _ticket_payload(finding: dict, owner: str, due: str) -> dict:
    fields = finding["ProductFields"]
    control_id = fields.get("ccm:control_id", "UNMAPPED")
    resource = finding["Resources"][0]
    evidence_rows = "\n".join(
        f"| `{key}` | {value} |" for key, value in sorted(fields.items())
    )
    mappings = f"{fields.get('ccm:csf', 'n/a')} / {fields.get('ccm:nist_800_53', 'n/a')}"
    body = f"""## {finding['Title']}

{finding['Description']}

| | |
|---|---|
| **Control** | {control_id} ({mappings}) |
| **Bucket** | {fields.get('ccm:bucket', 'n/a')} |
| **Severity** | {finding['Severity']['Label']} |
| **Resource** | `{resource['Id']}` ({resource['Type']}, {resource.get('Region', 'n/a')}) |
| **Detected by** | {fields.get('ccm:source', 'n/a')} ({finding['GeneratorId']}) |
| **Owner** | {owner} |
| **SLA due** | {due} |

<details><summary>Full finding context</summary>

| field | value |
|---|---|
{evidence_rows}

</details>

<!-- {FINDING_MARKER} {finding['Id']} -->
"""
    return {
        "title": f"{finding['Title']} — {resource['Id']}",
        "body": body,
        "labels": [
            "ccm-finding",
            f"severity:{finding['Severity']['Label'].lower()}",
            f"owner:{owner}",
            f"due:{due}",
        ],
    }


def route(bus, tickets, *, now: datetime | None = None,
          evidence_root: str | Path = EVIDENCE_ROOT,
          routing: dict | None = None) -> dict:
    now = now or datetime.now(UTC)
    routing = routing or load_routing()
    evidence_root = Path(evidence_root)

    findings = _dedupe_latest(bus.read_all())
    by_status: dict[str, int] = {}
    for finding in findings:
        status = finding["Compliance"]["Status"]
        by_status[status] = by_status.get(status, 0) + 1

    already_filed = tickets.existing_finding_ids()
    routed, skipped_existing, artifacts = [], 0, []
    attention = [
        f["Id"] for f in findings if f["Compliance"]["Status"] == "NOT_AVAILABLE"
    ]

    for finding in findings:
        if finding["Compliance"]["Status"] != "FAILED":
            continue
        if finding["Id"] in already_filed:
            skipped_existing += 1
            continue

        control_id = finding["ProductFields"].get("ccm:control_id")
        owner = routing["owners"].get(control_id, routing["default_owner"])
        sla = routing["sla_days"].get(finding["Severity"]["Label"], 90)
        due = (_ts(finding["UpdatedAt"]) + timedelta(days=sla)).date().isoformat()

        ref = tickets.create(_ticket_payload(finding, owner, due))

        artifact_dir = evidence_root / now.date().isoformat() / (control_id or "unmapped")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / f"{_safe_name(finding['Id'])}.json"
        artifact.write_text(
            json.dumps(
                {
                    "finding": finding,
                    "routing": {
                        "owner": owner,
                        "sla_days": sla,
                        "due": due,
                        "ticket": ref,
                        "routed_at": now.isoformat(),
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
        artifacts.append(str(artifact))
        routed.append({"id": finding["Id"], "owner": owner, "due": due, "ticket": ref})

    today = now.date().isoformat()
    sla_breaches = [
        t for t in tickets.open_tickets() if t.get("due") and t["due"] < today
    ]

    return {
        "findings_seen": len(findings),
        "by_status": by_status,
        "routed": routed,
        "skipped_existing": skipped_existing,
        "needs_attention_not_available": attention,
        "evidence_artifacts": artifacts,
        "sla_breaches": sla_breaches,
    }
