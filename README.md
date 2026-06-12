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

## Running locally

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # (.venv/bin/python on POSIX)
.venv/Scripts/python -m pytest                                # evaluate rule logic against moto
.venv/Scripts/python scripts/gen_matrix.py                    # regenerate the coverage matrix
```

No AWS credentials required for any of the above.

## Design questions this repo answers

<!-- Each links to the relevant ADR in docs/decisions.md as the build progresses. -->

- **Why Security Hub as the finding bus?** One schema (ASFF), one place to
  route from — see ADR-001.
- **How do you handle controls that can't be machine-evaluated?** The
  three-bucket model above; buckets 2 and 3 still flow through the same bus.
- **What did the platform fail at, and what was built instead?** See
  `collectors/` — each one documents the gap it fills. *(Session 4)*
- **Where does this break at scale?** Config eval cost, finding volume,
  owner-routing drift, evidence staleness — honest discussion in ADRs.
  *(Session 6)*
- **What would change in production?** Real ticketing/IdP, multi-account
  aggregation, OSCAL mappings. *(Session 6)*

## Status

Work in progress, built in deliberate layers (see commit history):

- [x] Control catalog + coverage matrix generation (21 controls sorted into buckets)
- [x] First custom Config rules with moto-tested evaluation logic (4/12)
- [ ] Remaining Config rules (machine-evaluable bucket complete)
- [ ] ASFF normalizer: Config + Prowler + custom collector → one schema
- [ ] Evidence collectors (attestable bucket)
- [ ] Router + judgment tracker + evidence loop
- [ ] Terraform deploy/teardown for the real-AWS proof
