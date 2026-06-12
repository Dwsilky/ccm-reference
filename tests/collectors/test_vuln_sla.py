import json
from datetime import UTC, datetime

from collectors.vuln_sla import collect

NOW = datetime(2026, 6, 12, tzinfo=UTC)


def test_vendored_export_yields_one_breach():
    result = collect(now=NOW)
    assert result["status"] == "FAIL"
    # V-1002: high, detected 04-02, fixed 05-20 = 48 days against a 30-day SLA.
    assert "V-1002" in result["evidence"]["breach_detail"]
    assert result["evidence"]["breaches"] == 1
    assert result["evidence"]["evaluated"] == 6


def test_unknown_severity_is_skipped_and_counted_not_guessed():
    result = collect(now=NOW)
    assert result["evidence"]["skipped_unknown_severity"] == "V-1007"


def test_fixed_with_null_fixed_at_uses_last_seen_and_says_so():
    result = collect(now=NOW)
    # V-1006: status=fixed, fixed_at null -> bounded by last_seen (27d, in SLA).
    assert result["evidence"]["fix_date_inferred_from_last_seen"] == 1
    assert "V-1006" not in result["evidence"]["breach_detail"]


def test_open_finding_breaches_by_age_not_only_when_fixed(tmp_path):
    export = tmp_path / "vulns.json"
    export.write_text(
        json.dumps(
            {
                "findings": [
                    {"id": "V-9", "severity": "critical", "detected_at": "2026-05-01",
                     "fixed_at": None, "status": "open"}
                ]
            }
        ),
        encoding="utf-8",
    )
    result = collect(export, now=NOW)  # 42 days open vs 15-day SLA
    assert result["status"] == "FAIL"
    assert "still open" in result["evidence"]["breach_detail"]


def test_all_within_sla_passes(tmp_path):
    export = tmp_path / "vulns.json"
    export.write_text(
        json.dumps(
            {
                "findings": [
                    {"id": "V-1", "severity": "critical", "detected_at": "2026-06-01",
                     "fixed_at": "2026-06-10"}
                ]
            }
        ),
        encoding="utf-8",
    )
    assert collect(export, now=NOW)["status"] == "PASS"


def test_missing_export_is_error():
    assert collect("nope.json", now=NOW)["status"] == "ERROR"


def test_export_with_only_unknown_severities_is_error(tmp_path):
    export = tmp_path / "vulns.json"
    export.write_text(
        json.dumps({"findings": [{"id": "V-1", "severity": "P4",
                                  "detected_at": "2026-06-01"}]}),
        encoding="utf-8",
    )
    assert collect(export, now=NOW)["status"] == "ERROR"
