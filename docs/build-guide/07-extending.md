# 07 — Extending: make it your own

The architecture's claim is that adding a control never touches the
pipeline. This chapter proves it by walking one new control into **each
bucket**, file by file, in the order you'd actually work — then covers
adapting the whole system to a different org, and what *not* to change.

## Worked example 1 — bucket 1 (machine): CCM-22, "No IAM role policies with full wildcards"

*Control statement: no IAM role carries an inline policy allowing
`Action: *` on `Resource: *`.* (PR.AC-4 / AC-6)

**Step 1 — catalog entry first** (`mappings/controls.yaml`). Sorting
discipline before code: state is fully readable via the IAM API → bucket 1.

```yaml
- id: CCM-22
  name: No IAM role policies with full wildcards
  bucket: machine
  csf: PR.AC-4
  nist_800_53: [AC-6]
  severity: HIGH
  method: Custom Config rule (periodic Lambda)
  source: config-rules/src/iam_role_wildcards
  status: planned          # flips to implemented when tests pass
```

Run `python scripts/gen_matrix.py` — the matrix now shows 22 controls,
21 implemented. The gap is visible from the first minute, which is the
point of the generated matrix.

**Step 2 — tests before handler**
(`tests/config_rules/test_iam_role_wildcards.py`). Copy the shape of
[`test_iam_user_mfa.py`](../../tests/config_rules/test_iam_user_mfa.py):
under `@mock_aws`, create a role with a wildcard inline policy → expect
NON_COMPLIANT naming the policy; a scoped role → COMPLIANT; a role with no
inline policies → COMPLIANT (managed policies are a *different* control —
say so in the docstring rather than half-covering it).

**Step 3 — handler** (`config-rules/src/iam_role_wildcards/handler.py`).
Copy any existing rule's skeleton: `CONTROL_ID = "CCM-22"`, paginate
`list_roles` → `list_role_policies` → `get_role_policy`, return
`Evaluation`s per role. The shared runner is untouched. ~50 lines.

**Step 4 — deploy map** (`deploy/main.tf`): one line in `local.rules` —
`iam_role_wildcards = "${var.name_prefix}-22-iam-role-wildcards"`. Done;
`for_each` builds the Lambda, permission, and Config rule.

**Step 5 — flip `status: implemented`, regenerate the matrix, commit.**

Total files touched: catalog, one test file, one handler, one Terraform
line. **Zero changes** to normalizer, bus, router, or demo — CCM-22
findings route with owners and SLAs the moment `owners.yaml` gains a line
(or fall back to `default_owner` if it doesn't).

## Worked example 2 — bucket 2 (attestable): CCM-23, "TLS certificates renewed before expiry"

*Control statement: no certificate in inventory is within 30 days of expiry
without a renewal in flight.* A machine can read expiry dates, but the
*inventory* lives in a cert tracker export — evidence-attestable.

Work through the [six questions from chapter 04](04-collectors.md#designing-your-own-collector--six-questions):

1. *Artifact?* The cert inventory export (CSV/JSON from your tracker or
   `acm list-certificates` if AWS-only).
2. *Source?* Vendor a sample export under `collectors/samples/certs/` —
   same pattern as the vuln export.
3. *Messy how?* Expired-but-renewed pairs (same CN, two rows), date formats,
   certs marked "decommissioned" that must be excluded like CCM-14's
   ad-hoc restores.
4. *PASS is:* every active cert has >30 days remaining, or a successor cert
   for the same CN already exists.
5. *resource_id:* the export filename (the population), not individual
   certs — one finding per collection run, detail in evidence. (Or per-cert
   if you want per-cert tickets; decide *before* the ID ships.)
6. *Evidence:* counts, soonest expiry, the CNs inside the window.

Then: `collectors/cert_renewal.py` with pure
`collect(export_path, now=None) -> dict` returning the
`COLLECTOR_REQUIRED_KEYS` contract, tests with a frozen `now` (PASS / FAIL /
ERROR-on-unreadable / the renewed-pair boundary), catalog entry with
`bucket: attestable`, an `owners.yaml` line. The normalizer accepts it via
`from_collector` unchanged; `python -m collectors.cert_renewal` publishes to
the bus via [`runner.py`](../../collectors/runner.py) unchanged.

## Worked example 3 — bucket 3 (judgment): CCM-24, "BC/DR plan reviewed annually"

Whether the plan is *adequate* is a human call. The entire implementation
is one register entry — and resisting the urge to write more code than
that **is** the implementation:

```yaml
# mappings/judgment-register.yaml
- control: CCM-24
  owner: infrastructure
  cadence_days: 365
  last_attested: null      # never attested -> FAILs immediately, by design
  artifact: ""
```

Plus the catalog entry (`bucket: judgment`,
`source: router/judgment_tracker.py`) and an `owners.yaml` line. The
tracker emits FAIL ("no attestation on record") on its next run; the router
files the reminder ticket; the owner attests by merging a PR that sets
`last_attested` and the artifact reference. If you find yourself writing a
*script* for CCM-24, re-read [ADR-003](../decisions.md) — you're about to
automate theater.

## Adapting the whole system to your org

**Different framework (ISO 27001 / SOC 2 instead of CSF):** the framework
fields live only in the catalog and flow through `ProductFields`
mechanically. Add `iso_27001: [A.8.24]` to entries, mirror the
`nist_800_53` handling in [`catalog.py`](../../normalizer/catalog.py) and
[`adapters.py`](../../normalizer/adapters.py) `_catalog_fields()`, extend
`gen_matrix.py`'s columns. No control logic changes — mappings are data
here, which is the entire reason they're in YAML.

**Jira/ServiceNow instead of GitHub Issues:** implement the three-method
backend interface from [`tickets.py`](../../router/tickets.py)
(`existing_finding_ids`, `create`, `open_tickets`) against your tracker's
API. Keep the dedupe marker in the ticket body. The router doesn't change —
that interface existing is [ADR-005](../decisions.md)'s deliberate seam.

**Real scheduling:** locally, collectors run by hand or cron. In AWS,
EventBridge Scheduler → Lambda per collector, publishing through
`SecurityHubBus`. The collectors don't change; only the thing invoking
`collect()` does.

**Multi-account:** designate a Security Hub delegated-admin account as the
aggregator; member accounts' findings flow to it natively; run the router
there. The single-account assumption lives almost entirely in `demo.py` and
the deploy module, not the pipeline.

**The deferred stretch goals** (deliberately out of v1 scope): OSCAL —
generate component definitions from `controls.yaml` (the catalog already has
everything an OSCAL `implemented-requirement` needs); Steampipe — prototype
new bucket-1 checks as SQL before committing to Lambda, and write up the
tradeoff; coverage trend — a script logging
`implemented/total` per bucket over git history, mirroring real CCM program
reporting.

## What NOT to change (load-bearing decisions)

| Don't touch | Because |
|---|---|
| **Deterministic finding IDs** (`source/control/resource`) | The upsert/dedupe/cost-control chain (ch. 03) *and* the router's re-file protection both hang off ID stability. Switching to UUIDs breaks both silently — duplicate tickets and a growing Security Hub bill |
| **ERROR → NOT_AVAILABLE, never PASS/FAIL** | The honesty rule the whole evidence story rests on. The day "couldn't check" gets reported as "passed" to make a dashboard green, the program is decorative |
| **The generated matrix** | Hand-editing `coverage-matrix.md` reintroduces the drift the generator exists to kill. Want different columns? Change `gen_matrix.py` |
| **One bucket per control, assigned in the catalog** | Sorting is the program's honesty mechanism. "Sort of bucket 1" controls become overstated assurance |
| **Dry-run as the default ticket backend** | The first time a dev loop files 200 real tickets, owners stop reading any of them — and that trust doesn't come back |

---

That's the system. If you've read all eight chapters you know not just what
every file does, but why each one is shaped the way it is — which is the
part that survives a rewrite in a different language, a different cloud, or
a different decade.
