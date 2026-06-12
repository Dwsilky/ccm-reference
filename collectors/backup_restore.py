"""CCM-14 — backup restore test succeeded this quarter. (PR.IP-4 / CP-9, attestable)

WHAT THE PLATFORM COULDN'T DO
    AWS Backup / managed rules can prove backups *ran*. The control that
    matters is that a restore was *tested* — and that evidence lives in the
    backup tool's job logs, which no platform exposes as queryable state.
    (Schrödinger's backup: every backup both works and doesn't until someone
    restores it.)

WHAT THIS DOES INSTEAD
    Parses the acme-backup suite log and asserts a successful restore test
    within the window. The log is genuinely hostile, and the parser deals
    with it rather than pretending the world is clean:

      * three line formats across tool versions (syslog-style, bracket-style
        "restore-verify", legacy US-date "restore_test");
      * syslog lines carry NO YEAR — inferred from the nearest preceding
        ISO-dated line, falling back to the reference year (and rolled back
        one year if that would put the event in the future);
      * binary logrotate garbage that must not kill the parse;
      * duplicate lines (log shipper at-least-once delivery) — deduped;
      * ad-hoc developer restores (job=adhoc-*) — excluded: a sandbox
        refresh is not the controlled test, however convenient it would be
        to count it.

    A FAILED test followed by a SUCCESS for the same job is a recovered
    failure (fine). A FAILED test with no later success is surfaced in
    evidence as unrecovered even when the overall verdict is PASS — the
    verdict answers "did a test succeed", the evidence keeps the auditor
    honest about what else happened.

SOURCE -> DESTINATION
    backup job log file -> collector contract dict ->
    normalizer.from_collector -> ASFF -> bus.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

CONTROL_ID = "CCM-14"
DEFAULT_LOG = Path(__file__).parent / "samples" / "backup_logs" / "restore_test.log"
WINDOW_DAYS = 90
EXCLUDED_JOB_PREFIXES = ("adhoc-",)

SYSLOG = re.compile(
    r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2} \d{2}:\d{2}:\d{2}) \S+ acme-restore\[\d+\]: "
    r"RESTORE TEST job=(?P<job>\S+) .*?result=(?P<result>SUCCESS|FAILED)"
)
VERIFY = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[restore-verify\] "
    r'job "(?P<job>[^"]+)" (?P<result>completed OK|FAILED)'
)
LEGACY = re.compile(
    r"^(?P<ts>\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) restore_test "
    r"job=(?P<job>\S+) result=(?P<result>SUCCESS|FAILED)"
)
# Any line opening with an ISO date updates the year context for syslog lines.
ISO_CONTEXT = re.compile(r"^(?P<year>\d{4})-\d{2}-\d{2}[T ]")


@dataclass(frozen=True)
class RestoreEvent:
    at: datetime
    job: str
    success: bool


def parse_events(text: str, reference: datetime) -> list[RestoreEvent]:
    events: set[RestoreEvent] = set()
    year_context = reference.year

    for line in text.splitlines():
        ctx = ISO_CONTEXT.match(line)
        if ctx:
            year_context = int(ctx.group("year"))

        if m := SYSLOG.match(line):
            at = datetime.strptime(m.group("ts"), "%b %d %H:%M:%S").replace(
                year=year_context, tzinfo=UTC
            )
            if at > reference:  # yearless stamp resolved into the future: prior year
                at = at.replace(year=at.year - 1)
        elif m := VERIFY.match(line):
            at = datetime.strptime(m.group("ts"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        elif m := LEGACY.match(line):
            at = datetime.strptime(m.group("ts"), "%m/%d/%Y %H:%M:%S").replace(tzinfo=UTC)
        else:
            continue

        events.add(
            RestoreEvent(
                at=at,
                job=m.group("job"),
                success=m.group("result") in ("SUCCESS", "completed OK"),
            )
        )
    return sorted(events, key=lambda e: e.at)


def collect(log_path: str | Path = DEFAULT_LOG, window_days: int = WINDOW_DAYS,
            now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    log_path = Path(log_path)
    base = {
        "control_id": CONTROL_ID,
        "resource_type": "BackupJobLog",
        "resource_id": f"{log_path.name}:restore-test",
    }

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return {**base, "status": "ERROR", "summary": f"Cannot read backup log: {err}"}

    all_events = parse_events(text, reference=now)
    excluded = [e for e in all_events if e.job.startswith(EXCLUDED_JOB_PREFIXES)]
    events = [e for e in all_events if e not in excluded]

    if not events:
        # Zero parseable events is a parser/format problem, not a clean FAIL:
        # "the control failed" and "we can no longer read the evidence" need
        # different owners.
        summary = "No restore-test events parsed from the log — format drift?"
        if excluded:
            summary += f" (only {len(excluded)} excluded ad-hoc events found)"
        return {**base, "status": "ERROR", "summary": summary}

    cutoff = now - timedelta(days=window_days)
    last_success_by_job: dict[str, datetime] = {}
    for event in events:
        if event.success:
            last_success_by_job[event.job] = event.at
    unrecovered = sorted(
        {
            e.job
            for e in events
            if not e.success
            and (e.job not in last_success_by_job or last_success_by_job[e.job] < e.at)
        }
    )
    successes_in_window = [e for e in events if e.success and e.at >= cutoff]

    evidence = {
        "window_days": window_days,
        "events_parsed": len(events),
        "excluded_adhoc": len(excluded),
        "unrecovered_failures": ",".join(unrecovered) or "none",
        "log": str(log_path),
    }

    if successes_in_window:
        latest = max(successes_in_window, key=lambda e: e.at)
        evidence.update(last_success_job=latest.job, last_success_at=latest.at.isoformat())
        return {
            **base,
            "status": "PASS",
            "summary": f"Restore test '{latest.job}' succeeded {latest.at.date()} "
            f"(window {window_days}d; unrecovered failures: "
            f"{', '.join(unrecovered) or 'none'}).",
            "evidence": evidence,
        }

    last_any = max((e.at for e in events if e.success), default=None)
    return {
        **base,
        "status": "FAIL",
        "summary": f"No successful restore test in the last {window_days} days "
        f"(last success: {last_any.date() if last_any else 'never'}; "
        f"ad-hoc developer restores excluded: {len(excluded)}).",
        "evidence": evidence,
    }


if __name__ == "__main__":
    from collectors.runner import publish

    result = collect()
    publish(result)
    print(json.dumps(result, indent=2, default=str))
