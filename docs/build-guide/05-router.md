# 05 — Router & judgment tracker: closing the loop

**You will build:** the routing engine (finding → owner → ticket → SLA →
evidence artifact), the judgment tracker that brings bucket 3 onto the bus,
and the end-to-end demo. After this chapter, all 21 controls flow and the
system is whole.

## Why this layer exists

Detection without follow-through is a dashboard, and dashboards get ignored.
A finding only counts as *monitoring* when it reliably produces: an
accountable owner, a deadline derived from severity, a work item the owner
sees, and a retrievable artifact proving all of the above happened. The
router is small (~150 lines) precisely because chapters 02–04 did the hard
part — by the time findings reach it, they're one schema, so it's written
once and every current and future control uses it.

## The routing pipeline, step by step

[`router/router.py`](../../router/router.py), in execution order:

**1. Dedupe to latest per `Id`.** The bus is append-only; re-running a check
appends an update, not a new fact. `_dedupe_latest()` keeps the newest
`UpdatedAt` per finding ID — this is the local mirror of Security Hub's
upsert behavior, and it works because IDs are deterministic (ch. 03).

**2. Partition by `Compliance.Status`.**
- `FAILED` → routed (the work).
- `PASSED` → counted, not routed (it's evidence, not work).
- `NOT_AVAILABLE` → the **attention list**: a collector that couldn't reach
  its evidence is the *pipeline owner's* operational problem, not the
  control owner's failure — but it cannot be silent, because an unreachable
  evidence source left alone quietly becomes a coverage gap.

**3. Resolve owner and SLA.** Owner from
[`mappings/owners.yaml`](../../mappings/owners.yaml) by control ID (default
for unmapped findings — yes, the unmapped Prowler check gets routed too,
to `grc-engineering`); due date = finding `UpdatedAt` + `sla_days[severity]`
(CRITICAL 7d → LOW 180d).

**4. File the ticket — through an interface.**
[`router/tickets.py`](../../router/tickets.py) defines two backends with
identical methods. `DryRunTickets` records payloads;
`GitHubTickets` files real issues. **Dry-run is the default everywhere** —
a pipeline that *can* spam a ticket tracker on every dev iteration
eventually will, and wrong/duplicate tickets are how a CCM program trains
its owners to ignore it ([ADR-005](../decisions.md)).

The dedupe-against-existing-work mechanism is worth copying: the finding ID
is embedded in the issue body as `<!-- ccm-finding-id: ... -->`, and *that
marker* — not the title — is the dedupe key, because humans rename issues
and the router must not re-file a finding because someone tidied a title.

The ticket body is the full audit context: control + CSF/800-53 mappings,
bucket, severity, resource, detecting source, owner, due date, and every
`ProductFields` entry in a collapsible table. The assignee should never
have to go research what this finding means.

**5. Write the evidence artifact.**
`evidence/<date>/<control>/<finding-id>.json` containing `{finding, routing}` —
see the [committed sample](../../evidence/sample/config-rule_CCM-02_demo-data-lake.json).
Written *even on dry runs*: the audit answer to "show me the chain for this
finding" is a file, not a database query.

**6. SLA check.** Open tickets carry `due:YYYY-MM-DD` labels; anything past
due lands in the report's `sla_breaches`. (ADR-005 notes the honest
limitation: labels are editable; production computes due dates from
immutable finding data and treats the label as a view.)

## The judgment tracker: bucket 3 without theater

[`router/judgment_tracker.py`](../../router/judgment_tracker.py) +
[`mappings/judgment-register.yaml`](../../mappings/judgment-register.yaml).

The register holds, per control: owner, `cadence_days`, `last_attested`,
and the artifact reference. The tracker emits the standard collector
contract (`source="tracker"`): PASS with `days_until_due` when current,
FAIL with `days_overdue` when stale. Two design points carry the weight:

- **The attestation workflow is a PR.** A human updates `last_attested`
  by merging a PR against the register — which makes the PR itself (author,
  approver, timestamp, linked artifact) the attestation evidence, in a
  system that's already access-controlled. No new tooling, and CCM-16 even
  monitors the approval gate on it.
- **Never-attested is FAIL, not "pending."** An attestation that has never
  happened is exactly as overdue as one that expired — "pending since
  forever" is how judgment controls quietly die.

This completes the three-bucket thesis: an overdue tabletop exercise
(CCM-20) becomes a ticket with an owner and a due date through *the same
six steps above* as an unencrypted bucket. The automation never judged
anything — it just refused to let the judgment be forgotten.

## The demo: the whole system in one command

[`scripts/demo.py`](../../scripts/demo.py) — run it, then read it; it's the
system's table of contents:

| Stage | What it proves |
|---|---|
| 1. Seeds a deliberately imperfect account in **moto**, runs four real rules' `evaluate()` | Chapter 02 logic is live, zero credentials |
| 2. Normalizes the vendored **Prowler** sample | Scanner findings are bus citizens, incl. the unmapped one |
| 3. Runs the file-based **collectors** (backup log, vuln export) | Bucket 2 flows |
| 4. Runs the **judgment tracker** | Bucket 3 flows |
| → routes everything | 14 findings → 8 dry-run tickets + 8 evidence artifacts + the attention/SLA report |

`--live` swaps in `GitHubTickets` and files real issues. Each run resets
`evidence/findings.jsonl` so output is reproducible.

## Pitfalls actually hit

- **UTC vs local dates.** The router stamps artifact directories with UTC;
  an evening demo run (local June 12) wrote `evidence/2026-06-13/`, and a
  copy command targeting the local date failed. Decide UTC-everywhere early
  — timestamps that disagree about "today" eventually corrupt evidence
  retrieval.
- **A failed command silently skipping a step.** That failed copy
  short-circuited an `&&` chain whose later steps (catalog status flips)
  never ran — caught only because the matrix generator printed
  `16 implemented` where 21 was expected. Generation steps should print
  counts, and you should *read* them.
- **Don't compute SLA dates from "now" in tests** — compute from the
  finding's own `UpdatedAt`, or the test fails the day the clock crosses a
  boundary mid-run (ours did).

## Checkpoint

```sh
.venv/Scripts/python -m pytest -q          # -> 102 passed
.venv/Scripts/python scripts/demo.py
# -> findings on bus : 14  {'FAILED': 8, 'PASSED': 6}
# -> tickets (dry-run): 8 ... evidence artifacts: 8 ... sla breaches: 0
```

Next: [Chapter 06 — deploy](06-deploy.md): proving the same code on real
AWS, briefly and cheaply.
