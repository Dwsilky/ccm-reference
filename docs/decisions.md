# Architecture Decision Records

Short ADRs, newest last. These record *why*, not *what* — the what is in the code.

---

## ADR-001 — Security Hub (ASFF) as the finding bus, with a local seam

**Status:** accepted

**Context.** Findings come from heterogeneous sources: AWS Config rule
evaluations, Prowler scans, and custom Python collectors. Each has its own
native shape. If the router has to understand every source format, every new
control means touching routing, ticketing, and evidence code.

**Decision.** Normalize everything to ASFF (AWS Security Finding Format) at the
source boundary and treat Security Hub as the single bus the router consumes
from. Behind a small `Bus` interface there are two implementations:

- `SecurityHubBus` — `batch_import_findings` to real Security Hub.
- `LocalBus` — appends the identical ASFF JSON to `evidence/findings.jsonl`.

Everything above the seam (router, SLA logic, evidence writing) is identical in
both modes.

**Why ASFF and not a home-grown schema?** A custom schema would be simpler for
this repo, but ASFF is what AWS-native tooling (Config→Security Hub
integration, Prowler's `--output-formats asff`) already speaks. Choosing it
means two of the three source types need *no* custom mapping in production, and
the one custom mapping (collectors) is the part worth demonstrating.

**Why the local seam?** Security Hub bills per finding ingested and Config per
rule evaluation. Development iterates hundreds of times; demos run twice. The
seam keeps iteration free and makes the repo runnable by a reviewer with no AWS
account — without forking the logic into "demo code" and "real code."

**Consequences / where it breaks.** Security Hub is regional and
single-account by default; at org scale you need a delegated-admin aggregator
account, and finding volume becomes a real cost line. ASFF is also
AWS-shaped — a multi-cloud program would normalize to OCSF instead, at the cost
of losing the native integrations. Revisited in the scale discussion (Session 6).

---

## ADR-002 — Local-first development on moto; deploy only to prove it

**Status:** accepted

**Context.** AWS Config and Security Hub have per-evaluation/per-finding
pricing with no meaningful free tier at steady state. This is a learning +
portfolio repo, not a production deployment; an idle demo should cost $0.

**Decision.** All rule evaluation logic is exercised locally against
[moto](https://github.com/getmoto/moto) (in-process AWS mock, no Docker
required) with pytest. Real AWS is reached only through `deploy/` (Terraform),
which exists to prove the same Lambdas run in a real account — and is torn down
(`terraform destroy`) after each demo.

**Why moto over LocalStack?** LocalStack is higher-fidelity but requires
Docker; moto runs in-process inside pytest, which makes the tests trivially
runnable by any reviewer (`pip install -r requirements-dev.txt && pytest`).
Where moto can't represent a state (e.g. root-account access keys), tests stub
the specific API response instead — the handler code never knows the difference.

**Consequences.** moto's fidelity is imperfect; a check can pass on moto and
behave differently on real AWS (this is exactly why `deploy/` exists). The
Lambda *plumbing* (Config event parsing, `put_evaluations`) is only fully
exercised on real AWS.

---

## ADR-003 — The three-bucket sorting criteria

**Status:** accepted

**Context.** The most common CCM failure mode is dishonest sorting: claiming a
control is "automated" when a script merely checks that a document exists, or
leaving a fully computable control on a manual evidence-request cadence.

**Decision.** Every control in `mappings/controls.yaml` carries exactly one
bucket, assigned by two questions:

1. **Can a machine compute pass/fail from system state alone?** → Bucket 1
   (machine-evaluable). The automation *is* the evaluation.
2. **If not — does a retrievable artifact prove the process ran?** → Bucket 2
   (evidence-attestable). The automation pulls and asserts on the artifact;
   it does not judge the process's quality.
3. **Otherwise** → Bucket 3 (human-judgment). The automation is only the
   reminder and the attestation tracking. Anything more would be theater.

**The boundary cases are the point.** "Access reviews occurred" is Bucket 2,
not Bucket 1: a script can prove a review ticket closed this quarter, but
cannot prove the reviewer actually scrutinized the entitlements. Writing a rule
that marks it COMPLIANT would overstate assurance. Conversely "MFA enabled" is
Bucket 1, not Bucket 2 — collecting screenshots of the IAM console for a state
the API exposes is wasted human time.

**Consequences.** Bucket 3 findings ("attestation overdue") flow through the
same bus and router as Bucket 1 findings. Auditors see one evidence store with
honest labels about what each item does and does not prove.
