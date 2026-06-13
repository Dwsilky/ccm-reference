# CCM Reference Implementation

A continuous control monitoring (CCM) pipeline demonstrating the pattern that
makes control automation scale: **many sources, one schema, one bus.**

```
Evidence sources ──→ Normalizer (ASFF) ──→ Finding bus ──→ Router ──→ Evidence store
                                                                  └──→ Tickets (SLA-tracked)

config-rules (Lambda)  ─┐
collectors (Python)    ─┼─→ normalizer/ ──→ bus ──→ router/ ──→ evidence/ + GitHub Issues
Prowler output         ─┤                   │
judgment tracker       ─┘     LocalBus (JSONL) | SecurityHubBus (boto3)
```

Adding a control means adding a source that emits ASFF — never rewriting the
pipeline. Everything runs locally with zero AWS spend (moto-mocked AWS, vendored
sample data); Terraform in `deploy/` proves the same code on real AWS, with
teardown documented as a first-class step.

> **Want to build this yourself?** The [**Build Guide**](docs/build-guide/README.md)
> explains every layer in rebuild-it-from-scratch depth — why each piece is
> shaped the way it is, how it's tested, the pitfalls hit along the way, and
> worked examples for [extending it with your own controls](docs/build-guide/07-extending.md).

## The three-bucket model

Every control is sorted into exactly one bucket before any code is written.
Sorting honestly is the core discipline of a CCM program — claiming automation
on a judgment control is how programs lose auditor trust.

| Bucket | What it means | What we automate |
|---|---|---|
| **1. Machine-evaluable** | Config state with a computable pass/fail (encryption, logging, access policy) | The full evaluation, as custom AWS Config rules |
| **2. Evidence-attestable** | A process ran / a review happened — no computable pass/fail, but the artifact exists | Pulling + asserting on the artifact, on a schedule |
| **3. Human-judgment** | Policy adequacy, risk acceptance — inherently human calls | Only the reminder and the attestation tracking |

All three buckets emit findings through the **same** normalizer → bus → router
path. Bucket 3 findings just assert *staleness* ("attestation overdue") instead
of *state*.

## Coverage

See **[coverage-matrix.md](coverage-matrix.md)** — 21 controls × (bucket,
CSF/800-53 mapping, collection method, source, status). Generated from
[`mappings/controls.yaml`](mappings/controls.yaml), the same catalog the
pipeline reads, so the matrix cannot drift from the code.

## Repo map

| Path | What it is |
|---|---|
| `config-rules/` | Custom AWS Config rules — one Lambda per control, evaluation logic written by hand (not managed-rule references) |
| `normalizer/` | Source-native output → ASFF. The single most important artifact: this is what makes "many sources, one bus" real |
| `collectors/` | Python collectors for controls no platform rule can evaluate (the evidence-attestable bucket) |
| `router/` | Finding → owner → ticket → SLA → evidence artifact. The closed loop |
| `mappings/` | Control catalog + CSF/800-53 mappings + owners |
| `evidence/` | Timestamped, audit-retrievable evidence artifacts (sample output committed) |
| `deploy/` | Terraform to run it on real AWS — and tear it down (cost guardrail) |
| `docs/decisions.md` | ADRs: why Security Hub as the bus, why this tiering, where it breaks at scale |
| `docs/build-guide/` | **The build guide** — chapter-by-chapter instructions to recreate, understand, and extend every part of this system |

## Running locally

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # (.venv/bin/python on POSIX)
.venv/Scripts/python -m pytest                                # evaluate rule logic against moto
.venv/Scripts/python scripts/gen_matrix.py                    # regenerate the coverage matrix
.venv/Scripts/python scripts/demo.py                          # the full loop: moto -> ASFF -> bus -> router
```

No AWS credentials required for any of the above. The demo seeds a
deliberately imperfect account in moto, runs real rule logic plus the
scanner sample, collectors, and judgment tracker, then routes every FAILED
finding to a dry-run ticket and writes timestamped artifacts under
`evidence/` (see `evidence/sample/` for a committed example). Add `--live`
to file real GitHub Issues.

## Design questions this repo answers

**Why Security Hub as the finding bus?**
One schema, one place to route from. ASFF is what AWS-native tooling already
speaks: the Config→Security Hub integration and Prowler's ASFF output mean
two of three source types need no custom mapping in production — the one
custom mapping (collectors) is the part worth demonstrating. A small `Bus`
seam (`normalizer/bus.py`) keeps development on a local JSONL file and demos
free. Full reasoning: [ADR-001](docs/decisions.md).

**How do you handle controls that can't be machine-evaluated?**
Sort honestly first (the three-bucket model above), then automate what each
bucket truthfully supports. Bucket 2 collectors pull and assert on artifacts
without claiming to judge process quality; bucket 3 gets only a tracked
reminder (`router/judgment_tracker.py` + `mappings/judgment-register.yaml`) —
its "attestation overdue" findings flow through the same bus, ticketing, and
SLA machinery as machine findings. Claiming more than that is assurance
theater. [ADR-003](docs/decisions.md).

**What did the platform fail at, and what was built instead?**
Four controls whose evidence no Config rule or scanner can reach: access
reviews (the review lives in a ticket system), restore tests (the proof lives
in hostile backup logs — three formats, yearless timestamps, binary garbage),
vuln SLAs (a timeline property, not a point-in-time scan), and change
approvals (a setting isn't proof the gate held). Each collector in
[`collectors/`](collectors/README.md) documents its specific gap.

**Where does this break at scale?**
- *Config evaluation cost*: periodic rules re-list whole resource
  populations; at thousands of resources, change-triggered rules and
  aggregated queries win ([config-rules/README.md](config-rules/README.md)).
- *Finding volume*: Security Hub bills per finding; deterministic upsert Ids
  are the guardrail here ([ADR-004](docs/decisions.md)), but org-wide you
  need a delegated-admin aggregator and a retention policy.
- *Owner-routing drift*: `owners.yaml` rots as fast as the org chart;
  production needs owner resolution against a live service catalog or IdP,
  plus a report of unroutable findings ([ADR-005](docs/decisions.md)).
- *Evidence staleness*: artifacts are point-in-time; nothing here re-verifies
  that the evidence for an open ticket still reflects reality. A real program
  re-collects on a cadence and flags evidence older than its control's cycle.
- *Single account, single region*: the entire repo assumes one of each.

**What would change in production?**
Enable the native Config→Security Hub integration and delete
`from_collector`'s config twin (documented in ADR-004 §3); swap
`router/tickets.py`'s GitHub backend for Jira/ServiceNow (that interface is
the seam); resolve owners from an IdP; aggregate findings cross-account via
Security Hub delegated admin; schedule collectors with EventBridge instead of
running them by hand; store evidence in S3 with object lock instead of a git
directory; and express the catalog in OSCAL so the mappings are
machine-consumable by GRC tooling.

## Proving it on real AWS

The local pipeline is the development story; [`deploy/`](deploy/README.md)
is the proof story — Terraform for the 12 rules + Lambdas, Security Hub, and
an evidence bucket, with cost guardrails documented per knob and
`terraform destroy` written into the runbook as a first-class step.

## Status

Complete — built in deliberate layers (see commit history):

- [x] Control catalog + coverage matrix generation (21 controls sorted into buckets)
- [x] First custom Config rules with moto-tested evaluation logic (4/12)
- [x] Remaining Config rules — machine-evaluable bucket complete (12/12, 43 tests)
- [x] ASFF normalizer: Config + Prowler + custom collector → one schema, one bus (LocalBus/Security Hub)
- [x] Evidence collectors — attestable bucket complete (4/4, incl. the hostile backup-log parser)
- [x] Router + judgment tracker + evidence loop — all 21 controls flowing, `make demo` end-to-end
- [x] Terraform deploy/teardown for the real-AWS proof (`deploy/`)

Deferred by choice, not omission: OSCAL catalog export, Steampipe-as-checks,
and a coverage-trend metric — candidates for a v2.
