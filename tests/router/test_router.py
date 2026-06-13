import json
from datetime import UTC, datetime, timedelta

from normalizer.adapters import from_collector
from normalizer.bus import LocalBus
from router.router import route
from router.tickets import DryRunTickets

NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def _finding(status="FAIL", control_id="CCM-13", resource_id="Dwsilky/ccm-reference"):
    return from_collector(
        {
            "control_id": control_id,
            "status": status,
            "resource_type": "GitHubRepo",
            "resource_id": resource_id,
            "summary": "No access-review issue closed this quarter.",
        },
        account_id="123456789012",
    )


def _bus(tmp_path, findings):
    bus = LocalBus(tmp_path / "findings.jsonl")
    bus.publish(findings)
    return bus


def test_only_failed_findings_become_tickets(tmp_path):
    bus = _bus(tmp_path, [_finding("FAIL"), _finding("PASS", resource_id="other/repo")])
    tickets = DryRunTickets()
    report = route(bus, tickets, now=NOW, evidence_root=tmp_path / "evidence")

    assert len(report["routed"]) == 1
    assert report["by_status"] == {"FAILED": 1, "PASSED": 1}
    assert len(tickets.created) == 1


def test_owner_and_sla_resolved_from_mappings(tmp_path):
    finding = _finding()  # CCM-13: owner identity, MEDIUM -> 90d SLA
    bus = _bus(tmp_path, [finding])
    report = route(bus, DryRunTickets(), now=NOW, evidence_root=tmp_path / "e")

    [routed] = report["routed"]
    assert routed["owner"] == "identity"
    updated = datetime.fromisoformat(finding["UpdatedAt"].replace("Z", "+00:00"))
    assert routed["due"] == (updated + timedelta(days=90)).date().isoformat()


def test_ticket_body_carries_full_audit_context(tmp_path):
    bus = _bus(tmp_path, [_finding()])
    tickets = DryRunTickets()
    route(bus, tickets, now=NOW, evidence_root=tmp_path / "e")

    body = tickets.created[0]["body"]
    assert "CCM-13" in body
    assert "PR.AC-4" in body and "AC-2(3)" in body  # framework mappings inline
    assert "ccm-finding-id: collector/CCM-13/Dwsilky/ccm-reference" in body
    assert "owner:identity" in tickets.created[0]["labels"]


def test_evidence_artifact_closes_the_loop(tmp_path):
    bus = _bus(tmp_path, [_finding()])
    report = route(bus, DryRunTickets(), now=NOW, evidence_root=tmp_path / "evidence")

    [artifact_path] = report["evidence_artifacts"]
    assert f"{NOW.date()}" in artifact_path and "CCM-13" in artifact_path
    artifact = json.loads((tmp_path / "evidence").joinpath(
        NOW.date().isoformat(), "CCM-13",
        "collector_CCM-13_Dwsilky_ccm-reference.json").read_text(encoding="utf-8"))
    assert artifact["routing"]["owner"] == "identity"
    assert artifact["routing"]["ticket"].startswith("DRY-RUN")
    assert artifact["finding"]["Id"] == "collector/CCM-13/Dwsilky/ccm-reference"


def test_rerun_updates_are_deduped_to_latest(tmp_path):
    # Same check run twice -> same Id appended twice -> one ticket.
    bus = _bus(tmp_path, [_finding()])
    bus.publish([_finding()])
    report = route(bus, DryRunTickets(), now=NOW, evidence_root=tmp_path / "e")
    assert report["findings_seen"] == 1
    assert len(report["routed"]) == 1


def test_already_filed_findings_are_not_refiled(tmp_path):
    class TicketsWithHistory(DryRunTickets):
        def existing_finding_ids(self):
            return {"collector/CCM-13/Dwsilky/ccm-reference"}

    bus = _bus(tmp_path, [_finding()])
    report = route(bus, TicketsWithHistory(), now=NOW, evidence_root=tmp_path / "e")
    assert report["routed"] == []
    assert report["skipped_existing"] == 1


def test_not_available_findings_flagged_for_attention_not_ticketed(tmp_path):
    bus = _bus(tmp_path, [_finding("ERROR")])
    report = route(bus, DryRunTickets(), now=NOW, evidence_root=tmp_path / "e")
    assert report["routed"] == []
    assert report["needs_attention_not_available"] == [
        "collector/CCM-13/Dwsilky/ccm-reference"
    ]


def test_overdue_open_tickets_reported_as_sla_breaches(tmp_path):
    class TicketsWithOpenWork(DryRunTickets):
        def open_tickets(self):
            return [
                {"ref": "issue/1", "title": "old", "due": "2026-05-01"},   # breached
                {"ref": "issue/2", "title": "fresh", "due": "2026-09-01"},
            ]

    bus = _bus(tmp_path, [])
    report = route(bus, TicketsWithOpenWork(), now=NOW, evidence_root=tmp_path / "e")
    assert [b["ref"] for b in report["sla_breaches"]] == ["issue/1"]
