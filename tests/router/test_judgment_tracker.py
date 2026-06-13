from datetime import UTC, datetime

from router.judgment_tracker import collect_all

NOW = datetime(2026, 6, 12, tzinfo=UTC)


def test_register_covers_all_five_judgment_controls():
    results = collect_all(now=NOW)
    assert [r["control_id"] for r in results] == [
        "CCM-17", "CCM-18", "CCM-19", "CCM-20", "CCM-21",
    ]


def test_overdue_attestations_fail_with_days_overdue():
    results = {r["control_id"]: r for r in collect_all(now=NOW)}
    # CCM-18: quarterly, last attested 2026-02-20 -> 112d old vs 90d cadence.
    assert results["CCM-18"]["status"] == "FAIL"
    assert results["CCM-18"]["evidence"]["days_overdue"] == 22
    # CCM-20: annual tabletop, last 2025-05-10 -> overdue.
    assert results["CCM-20"]["status"] == "FAIL"


def test_current_attestations_pass_with_artifact_reference():
    results = {r["control_id"]: r for r in collect_all(now=NOW)}
    for control in ("CCM-17", "CCM-19", "CCM-21"):
        assert results[control]["status"] == "PASS"
        assert results[control]["evidence"]["artifact"]


def test_never_attested_is_fail_not_pending(tmp_path):
    register = tmp_path / "register.yaml"
    register.write_text(
        "register:\n  - control: CCM-17\n    owner: ciso-office\n    cadence_days: 365\n",
        encoding="utf-8",
    )
    [result] = collect_all(register, now=NOW)
    assert result["status"] == "FAIL"
    assert "no attestation on record" in result["summary"]
    assert result["evidence"]["last_attested"] == "never"
