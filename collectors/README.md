# Custom evidence collectors (bucket 2 — evidence-attestable)

These four controls have no computable pass/fail in any platform — the
evidence lives in systems no managed rule reaches. Each collector pulls the
artifact, asserts on it, and emits the contract dict that
`normalizer.from_collector` turns into ASFF (see `COLLECTOR_REQUIRED_KEYS`).

Run one from the repo root: `python -m collectors.access_review` — the
finding lands on the LocalBus (`evidence/findings.jsonl`).

| Control | What the platform couldn't do | What the collector does instead | Source → destination |
|---|---|---|---|
| CCM-13 access review | Config sees IAM *state*, never whether a human reviewed it | Asserts an `access-review`-labeled issue closed this quarter; re-checks `closed_at` locally because GitHub's `since` filters on `updated_at` | GitHub Issues API → ASFF → bus |
| CCM-14 backup restore test | Platforms prove backups *ran*; restore *tests* only exist in tool logs | Parses a hostile log (3 formats, yearless syslog stamps, binary garbage, dupes), excludes ad-hoc dev restores, asserts a success in window | backup job log → ASFF → bus |
| CCM-15 vuln SLAs | Scanners show what's vulnerable *now*; SLA compliance is a timeline property | Computes time-to-remediate per severity tier; open findings breach by *age*; unknown severities skipped-and-counted, never guessed | scanner export JSON → ASFF → bus |
| CCM-16 change approvals | A branch-protection *setting* ≠ the gate *held* for every change | Asserts every merged PR in window had a pre-merge, non-author approval; post-merge approval is paperwork | GitHub Pulls/Reviews API → ASFF → bus |

Shared verdict semantics (enforced by the adapter, see ADR-004):

- **PASS / FAIL** — the evidence was examined and the assertion held / didn't.
- **ERROR** — the evidence couldn't be examined (API down, log unparseable).
  Maps to `NOT_AVAILABLE`, never to PASSED or FAILED: "we couldn't check"
  reported as either verdict is how evidence programs rot.
- Empty population (e.g. no merges in window) is PASS with `population: 0`
  in evidence — "no exceptions noted" — and is distinct from ERROR.
