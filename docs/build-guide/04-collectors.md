# 04 — Collectors: the evidence-attestable bucket

**You will build:** four Python collectors for controls whose evidence no
platform rule can reach. This is the differentiator bucket — anyone can
reference managed rules; pulling and asserting on real-world evidence
(ticket APIs, hostile logs, scanner exports) is where the engineering shows.

## The design contract

Every collector is a pure function plus thin CLI plumbing:

```python
def collect(...) -> dict:   # the COLLECTOR_REQUIRED_KEYS contract from ch. 03
    # control_id, status (PASS|FAIL|ERROR), resource_type, resource_id,
    # summary, evidence: dict
```

Three rules, all visible in every collector in
[`collectors/`](../../collectors/):

1. **Inject everything non-deterministic.** `client=`, `now=`, paths — all
   parameters with production defaults. Tests pass fakes and frozen clocks;
   no network, no sleeps, no flaky tests.
2. **ERROR ≠ FAIL.** API unreachable / log unparseable is `ERROR`
   (→ `NOT_AVAILABLE`), never FAIL and never PASS. "The control failed" and
   "we can no longer read the evidence" have *different owners* — conflating
   them either pages the wrong team or quietly rots coverage.
3. **Empty population is PASS with `population: 0` in evidence** — audit
   language for "no exceptions noted" — and is explicitly distinct from
   ERROR. No merges this window means the gate held vacuously, not that we
   couldn't look.

The shared pieces are deliberately tiny:
[`github_api.py`](../../collectors/github_api.py) (a ~60-line client with
token resolution: arg → `GITHUB_TOKEN` → `gh auth token`) and
[`runner.py`](../../collectors/runner.py) (collect → normalize → LocalBus,
so `python -m collectors.<name>` runs one collection end to end).

## The four collectors and their signature judgment calls

### CCM-13 — access review occurred ([`access_review.py`](../../collectors/access_review.py))

*Gap:* Config sees IAM **state**, never whether a human reviewed it.
*Assertion:* an issue labeled `access-review` was **closed this quarter**.

The trap that makes this collector worth reading: GitHub's `since` parameter
filters on `updated_at`, not `closed_at`. An old Q4 review ticket that
someone edits today comes back from the API looking fresh — trusting `since`
would let stale evidence attest the current quarter. So the collector
re-checks `closed_at` locally against the quarter boundary, and excludes
PRs (which surface in the Issues API) because a PR *named* "access review"
is not a review ticket. This is what the spec meant by "reconciling messy
ticket data."

What it deliberately does **not** claim: that the review was thorough.
That's why this is bucket 2 — the collector proves the ritual, the bucket
label keeps the assurance claim honest.

### CCM-14 — backup restore test succeeded ([`backup_restore.py`](../../collectors/backup_restore.py)) — the deep dive

*Gap:* platforms prove backups **ran**; the control that matters is that a
restore was **tested** (Schrödinger's backup), and that evidence lives in
tool logs nobody exposes as an API.

The vendored log
([`samples/backup_logs/restore_test.log`](../../collectors/samples/backup_logs/restore_test.log))
is deliberately hostile, and every hostility is one the parser handles
explicitly rather than pretending the world is clean:

| Hostility | Handling |
|---|---|
| Three line formats across tool versions (syslog, bracket-style `restore-verify`, legacy US-dates) | Three regexes normalizing into one `RestoreEvent` |
| **Syslog lines carry no year** (`Apr  5 03:11:02 …`) | Year inferred from the nearest *preceding* ISO-dated line; if that resolves to the future, roll back one year — a log can't be from the future |
| Binary logrotate garbage mid-file | `errors="replace"` on read; unmatched lines skipped, never fatal |
| Duplicate lines (at-least-once log shipping) | Events deduped as a set of `(timestamp, job, result)` |
| An ad-hoc developer restore (`job=adhoc-dev-refresh`) | **Excluded** — a sandbox refresh is not the controlled test, however convenient it would be to count it |
| A `FAILED` test with no later success | Surfaced in evidence as `unrecovered_failures` even when the verdict is PASS — the verdict answers "did a test succeed," the evidence keeps the auditor honest about what else happened |
| Zero parseable events | **ERROR, not FAIL** — "format drifted" is the pipeline owner's bug, not the backup team's failure |

The tests
([`test_backup_restore.py`](../../tests/collectors/test_backup_restore.py))
prove the exclusion *matters*: at a frozen `now` of Aug 1, the real Q2 tests
have aged out of the 90-day window, only the ad-hoc restore remains — and
the verdict is FAIL. If you write one collector to learn this craft, write
this one.

### CCM-15 — vuln remediation SLAs ([`vuln_sla.py`](../../collectors/vuln_sla.py))

*Gap:* scanners show what's vulnerable **now**; SLA compliance is a property
of the **timeline** — how long each finding stayed open against its
severity's committed window.

Judgment calls: open findings breach **by age** (an open critical past its
window is a breach *today*, not on the day it's eventually fixed); severity
casing is normalized; unknown severities ("Sev3" from a legacy import) are
**skipped-and-counted** — dropping them silently shrinks the population,
mapping them silently invents an SLA; and the scanner-bug case
(`status: fixed` with `fixed_at: null`) uses `last_seen` as the bound and
discloses that inference in evidence (`fix_date_inferred_from_last_seen`).

### CCM-16 — change approvals enforced ([`change_approval.py`](../../collectors/change_approval.py))

*Gap:* a branch-protection **setting** proves the gate was configured, not
that it **held** for every change in the window.

The assertion is three-part, and each part kills a common loophole: the
approval must be (a) state `APPROVED` — `CHANGES_REQUESTED` is not approval,
(b) **submitted before the merge** — post-merge approval is paperwork after
the change shipped, not a gate, and (c) **by a non-author** — self-approval
via a bot or second account is the classic bypass.

## Designing your own collector — six questions

Answer these before writing code; they *are* the design:

1. **What artifact proves the control operated?** (Not "what does the
   control say" — what physical evidence exists?)
2. **What system exposes that artifact, via what API/file/export?**
3. **What does the messy version of that data look like?** (Pagination
   semantics, timestamp formats, fields that lie — like `since` or
   `fixed_at: null`. Budget most of your effort here.)
4. **What exactly is PASS?** Window, population, boundary cases. Write the
   sentence an auditor would accept before writing the code.
5. **What's the stable `resource_id`?** It feeds the deterministic finding
   ID (ch. 03) — rerun must upsert, not duplicate.
6. **What goes in `evidence`?** Enough for an auditor to re-derive the
   verdict: the query, the counts, the matched artifact, the window.

Then: pure `collect()` with injected dependencies, tests with fakes/frozen
clocks for PASS / FAIL / ERROR / boundary, a docstring header stating the
platform gap, and a row in `controls.yaml`.

## Checkpoint

```sh
.venv/Scripts/python -m pytest tests/collectors -q    # -> 24 passed
.venv/Scripts/python -m collectors.backup_restore     # PASS with evidence, on the vendored log
.venv/Scripts/python -m collectors.access_review      # live GitHub call (FAIL until you close a labeled issue)
```

Next: [Chapter 05 — the router](05-router.md), where findings become
tickets, SLAs, and audit artifacts.
