from datetime import UTC, datetime

from collectors.backup_restore import DEFAULT_LOG, collect, parse_events

NOW = datetime(2026, 6, 12, tzinfo=UTC)
LOG_TEXT = DEFAULT_LOG.read_text(encoding="utf-8", errors="replace")


def test_parses_all_three_formats_despite_garbage_and_dupes():
    events = parse_events(LOG_TEXT, reference=NOW)
    jobs = {e.job for e in events}
    assert jobs == {
        "q2-restore-test-db",       # syslog format (yearless)
        "q2-restore-test-files",    # restore-verify format (duplicated line -> one event)
        "q2-restore-test-tape",     # syslog, unrecovered failure
        "adhoc-dev-refresh",        # legacy US-date format
    }
    files_events = [e for e in events if e.job == "q2-restore-test-files"]
    assert len(files_events) == 1  # at-least-once log shipping deduped


def test_yearless_syslog_timestamps_get_year_from_iso_context():
    events = parse_events(LOG_TEXT, reference=NOW)
    db_success = next(e for e in events if e.job == "q2-restore-test-db" and e.success)
    assert db_success.at == datetime(2026, 4, 5, 3, 58, 40, tzinfo=UTC)


def test_passes_on_q2_success_and_surfaces_unrecovered_failure():
    result = collect(now=NOW)
    assert result["status"] == "PASS"
    assert result["evidence"]["last_success_job"] == "q2-restore-test-files"
    # The tape test failed on Jun 2 with no recovery — verdict stays PASS
    # (a test did succeed) but the auditor sees the failure.
    assert result["evidence"]["unrecovered_failures"] == "q2-restore-test-tape"


def test_adhoc_developer_restore_cannot_carry_the_control():
    # By Aug 1 the real Q2 tests have aged out of the 90-day window and only
    # the 05/22 ad-hoc sandbox refresh remains — which must not count.
    result = collect(now=datetime(2026, 8, 1, tzinfo=UTC))
    assert result["status"] == "FAIL"
    assert "ad-hoc developer restores excluded: 1" in result["summary"]


def test_missing_log_is_error():
    assert collect("does/not/exist.log", now=NOW)["status"] == "ERROR"


def test_unparseable_log_is_error_not_fail(tmp_path):
    # "We can't read the evidence" needs a different owner than "the test
    # didn't happen".
    junk = tmp_path / "rotated.log"
    junk.write_text("totally new format v3.0\nnothing matches\n", encoding="utf-8")
    result = collect(junk, now=NOW)
    assert result["status"] == "ERROR"
    assert "format drift" in result["summary"]
