# 03 — Normalizer & bus: many sources, one schema

**You will build:** the ASFF builder/validator, three source adapters, and
the bus abstraction. This is the chapter the repo exists for — everything
before it produces findings, everything after it consumes them, and this
layer is why neither side knows about the other.

## Why one schema (the N×M argument)

Without a common format, every consumer must understand every producer:
3 sources × 3 consumers (tickets, evidence, SLA tracking) = 9 integrations,
and control #22 makes it 12. With a schema boundary at the source, it's
3 adapters + 3 consumers and **adding a source is one adapter** — the
pipeline literally never changes. That's the difference between a CCM
*program* and a folder of scripts.

**Why ASFF specifically** (and not a home-grown schema or OCSF): ASFF is
what the AWS-native world already speaks. The Config→Security Hub
integration and Prowler's `--output-formats asff` both emit it natively —
meaning in production, two of our three source types need *no custom code at
all*, and the one mapping we must write (custom collectors) is exactly the
part worth demonstrating. A home-grown schema would be simpler and prove
nothing; OCSF would be the right call for multi-cloud at the cost of every
native integration ([ADR-001](../decisions.md)).

## The builder: `normalizer/asff.py`

[Source](../../normalizer/asff.py). Three decisions define it
([ADR-004](../decisions.md) is the full record):

**1. A deliberate subset, omit-don't-stub.** ASFF has ~100 fields. We emit
the `BatchImportFindings` required set plus `Compliance`, `ProductFields`,
`RecordState`, `Workflow` — and *omit* blocks we have no data for (Network,
Process, Malware…) rather than stubbing them empty. An auditor reading a
finding must never wonder whether an empty field means "checked, nothing
there" or "never collected."

**2. Deterministic IDs are the cost control.**

```python
"Id": f"{source}/{control_id or 'unmapped'}/{resource_id}"
# e.g. "config-rule/CCM-02/demo-data-lake"
```

Security Hub *upserts* on `Id`: re-running a check updates the existing
finding's `UpdatedAt` instead of creating a duplicate. Since Security Hub
bills per finding ingested and CCM re-runs everything on a schedule, UUID
IDs would turn the bill into a function of your cron frequency. The
tradeoff, stated honestly: two *different* problems on the same
resource+control collapse into one finding — acceptable here because every
check is single-assertion by design.

**3. PASSED is always INFORMATIONAL.** Severity describes the risk of the
*finding*, not the importance of the *control*. The catalog's severity
(`CRITICAL` for root keys) applies only when the control FAILS; a passing
critical control is not a critical event. Without this rule your dashboard
is a wall of red that means nothing.

The validator (`validate()`) enforces required fields, severity labels,
compliance statuses, resource shape, and UTC timestamps — *at the boundary*.
`BatchImportFindings` reports per-finding failures in a 200 response with
terse reasons; failing fast locally with a readable message beats debugging
`FailedCount` in production. `build_finding()` calls `validate()` before
returning, so an invalid finding cannot exist.

## The three adapters: `normalizer/adapters.py`

[Source](../../normalizer/adapters.py). Each absorbs one source's quirks and
enriches from the catalog (`ccm:bucket`, `ccm:csf`, `ccm:nist_800_53` land
in `ProductFields`, so every finding is framework-traceable without a
lookup).

### `from_config_evaluation(evaluation, control_id, account_id, region)`

Input is chapter 02's `Evaluation` dataclass. Mapping:
`COMPLIANT→PASSED`, `NON_COMPLIANT→FAILED`, `NOT_APPLICABLE→NOT_AVAILABLE`.
Worth saying in any interview: **in production this adapter is redundant** —
the Config→Security Hub native integration does this for free. It exists
because the local pipeline has no Config service, and writing it documents
exactly what the integration buys you (ADR-004 §3).

### `from_prowler(check)`

Input is one Prowler v4 OCSF JSON object (vendored sample with documented
provenance: [`normalizer/samples/prowler/`](../../normalizer/samples/prowler/README.md)).
The interesting policy is **attribution is best-effort**: the catalog's
`prowler_checks` field reverse-maps scanner check IDs to controls, and
*unmapped* checks still normalize — they just carry no `ccm:control_id` and
get IDs like `prowler/unmapped/arn:...`. Dropping scanner findings your
catalog hasn't claimed would hide real exposure; silently inventing a
mapping would corrupt coverage reporting. The vendored sample deliberately
includes one unmapped check (`ec2_instance_imdsv2_enabled`) so the path
stays tested.

### `from_collector(result, account_id, region, source)`

Input is the contract dict every collector emits:

```python
COLLECTOR_REQUIRED_KEYS = ("control_id", "status", "resource_type", "resource_id", "summary")
# plus optional: evidence: dict  -> ProductFields as "evidence:<key>"
```

This tuple is the system's **extension API** — chapter 04's collectors and
chapter 05's judgment tracker (via `source="tracker"`) are just things that
emit it. The status mapping carries the most important compliance semantics
in the repo:

```
PASS  -> PASSED
FAIL  -> FAILED
ERROR -> NOT_AVAILABLE      # never PASSED, never FAILED
```

"We couldn't check" reported as a pass is how evidence programs rot;
reported as a failure, it pages the wrong owner. `NOT_AVAILABLE` routes to
an attention list instead (chapter 05).

## The bus: `normalizer/bus.py`

[Source](../../normalizer/bus.py). A `Protocol` with one method
(`publish(findings) -> int`) and two implementations:

- **`LocalBus`** appends validated ASFF to `evidence/findings.jsonl`.
  JSONL, not a JSON array: appends don't rewrite the file, a partial write
  corrupts one line instead of the store, and the router can stream it.
- **`SecurityHubBus`** batches `batch_import_findings` (100 per call) and
  **raises on partial failure** — the API returns HTTP 200 with a
  `FailedCount`; checking only the status code silently drops findings.

Everything above this seam is identical in both modes. That's the entire
local-development story: not separate "demo code," the same pipeline with a
file where Security Hub would be.

## The thesis test

[`tests/normalizer/test_one_schema.py`](../../tests/normalizer/test_one_schema.py)
is the property the repo exists to demonstrate, as an executable assertion:

1. runs a **real** Config rule's `evaluate()` against moto state,
2. normalizes the **vendored Prowler sample**,
3. normalizes a **collector result**,
4. publishes all of them to one `LocalBus`,
5. asserts every finding validates, the three `ccm:source` values are
   present, and severity/compliance/resource are uniform — i.e. the router
   will never need to know where a finding came from.

If you rebuild this system and that test passes, you've built the right
thing. Everything else is volume.

## Pitfalls actually hit

- **Prowler's OCSF format will drift.** That's why the sample is vendored
  with a provenance README naming exactly which fields the adapter consumes
  — when Prowler moves a field, the fixture and the adapter tests say which
  one, instead of a live scan failing mysteriously.
- **moto supports `batch_import_findings`** (after `enable_security_hub()`),
  so the real-bus path is testable — but the *partial failure* path isn't
  reproducible in moto, hence the rejecting-fake test in
  [`test_bus.py`](../../tests/normalizer/test_bus.py). Match the test double
  to what each test actually exercises.
- **Timestamps**: ASFF wants UTC ISO-8601; the builder emits trailing-`Z`
  format and the validator enforces it, because half-`Z`/half-offset
  timestamps will eventually bite any consumer that string-sorts them
  (the router's dedupe-latest does exactly that).

## Checkpoint

```sh
.venv/Scripts/python -m pytest tests/normalizer -q     # -> 23 passed
.venv/Scripts/python -m collectors.vuln_sla            # publishes one real finding
type evidence\findings.jsonl                           # cat on POSIX — valid ASFF, one line
```

Next: [Chapter 04 — collectors](04-collectors.md): the sources that earn
this architecture its keep.
