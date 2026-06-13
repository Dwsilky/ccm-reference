# 06 — Deploy: proving it on real AWS (then tearing it down)

**You will build:** the Terraform in [`deploy/`](../../deploy/) — 12 Lambdas
+ Config rules, Security Hub, an evidence bucket — plus the packaging script
that makes per-Lambda zips possible. This chapter is short on purpose: the
local pipeline is the development story; this is only the proof story.

## The cost model that drives everything

Why local-first at all ([ADR-002](../decisions.md))? Because the two AWS
services at the heart of this bill *per use* with no meaningful steady-state
free tier:

- **AWS Config**: per configuration item recorded (the recorder) **and**
  per rule evaluation. Development iterates evaluations hundreds of times.
- **Security Hub**: per finding ingested. CCM re-ingests on a schedule
  forever.

So: logic developed and proven on moto for $0, deployed only to demonstrate
the wire plumbing moto can't — Config invoking the Lambda with its real
event format, `put_evaluations` accepting our batches, the native
Config→Security Hub forwarding. Deploy, evaluate once, screenshot,
**destroy**. The runbook treats `terraform destroy` as step 4, not an
afterthought, because *infra you aren't demoing is infra you tear down* —
the habit matters more than the dollar amount.

## The vendoring problem (why `package_lambdas.py` exists)

Chapter 02 put all Config-API knowledge in `config-rules/shared/` so each
rule file is pure logic. But Lambdas don't share a filesystem — each
function's zip must contain *everything it imports*. The resolution:
single-source-in-repo, duplicated-in-artifact.
[`scripts/package_lambdas.py`](../../scripts/package_lambdas.py) stages
`deploy/build/<rule>/` as `handler.py` + a vendored copy of `shared/`, and
Terraform's `archive_file` zips each staging dir. `source_code_hash` ties
deployment to content: editing one rule redeploys exactly that Lambda.

## The Terraform, file by file

| File | Job | The decision inside |
|---|---|---|
| [`main.tf`](../../deploy/main.tf) | providers + the `local.rules` map | The rule map is the *entire* deploy-side change when adding a control; everything else is `for_each`. Default tags on every resource so a cost report — or an emergency cleanup — can find it all |
| [`iam.tf`](../../deploy/iam.tf) | one shared Lambda role | `SecurityAudit` (AWS-maintained read-only audit policy) + logs + `config:PutEvaluations`. Broader than any one rule needs — but AWS maintains it as services change, which beats hand-curating 12 minimal policies that rot |
| [`lambda.tf`](../../deploy/lambda.tf) | 12 functions + invoke permissions | `python3.12`, 256 MB (rules list whole populations), `config.amazonaws.com` principal scoped to this account |
| [`config.tf`](../../deploy/config.tf) | recorder (optional) + 12 rules | Periodic, `TwentyFour_Hours`. Recorder's recording group pinned to a single resource type — our rules query live APIs, so the recorder exists only because Config requires one; per-CI pricing makes `all_supported` the expensive default |
| [`s3.tf`](../../deploy/s3.tf) | evidence bucket | Versioned, encrypted, public-access-blocked — it must pass its own controls (CCM-01/02 eat their own dog food). `force_destroy = true` because a demo teardown that fails on a non-empty bucket isn't a teardown |
| [`securityhub.tf`](../../deploy/securityhub.tf) | the real bus | `enable_default_standards = false` — default standards generate thousands of per-finding-billed findings this repo doesn't route |
| [`variables.tf`](../../deploy/variables.tf) | escape hatches | `manage_recorder=false` / `manage_security_hub=false` for accounts that already have them — a second recorder is an *error*, not a duplicate |

Full runbook with verify commands: [`deploy/README.md`](../../deploy/README.md).

## Honest status

**This HCL has not yet been applied.** It's written conventionally
(provider ~> 5.0, standard resources, no exotica) and the Lambdas it ships
are byte-for-byte the moto-tested code — but first contact with a real AWS
account historically surfaces something (an IAM propagation delay, a
delivery-channel policy nit). Expect to fix one or two small things on first
`apply`; that is *the point* of having a deploy story, and pretending
otherwise would undercut everything else this repo says about evidence.

Known assumptions, stated rather than hidden: `manage_recorder=true`
presumes a Config-virgin account; there's no remote state or CI deploy
because this is a prove-it module, not an operate-it module.

## Checkpoint

```sh
python scripts/package_lambdas.py     # -> staged 12 rules under deploy/build
cd deploy && terraform init && terraform plan    # read the plan — it's someone's bill
# apply / verify / DESTROY per deploy/README.md
```

Next: [Chapter 07 — extending](07-extending.md): the worked examples for
making this system your own.
