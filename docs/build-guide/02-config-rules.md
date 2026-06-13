# 02 — Custom Config rules: the machine-evaluable bucket

**You will build:** 12 custom AWS Config rules — each a Lambda whose
evaluation logic you wrote and can defend — plus the shared plumbing that
keeps each rule file pure logic, and a moto test suite that proves all of it
with zero AWS credentials.

## Why custom rules (the interview answer first)

AWS ships managed rules for most of these checks, and in production you
should usually use them. This repo writes them custom for reasons worth
being able to recite ([config-rules/README.md](../../config-rules/README.md)
has the full version):

1. **The logic is the learning** — a managed-rule reference proves you can
   read a catalog; writing the evaluation proves you know what the control
   asserts (see CCM-09's "exists ≠ logging" below).
2. **Managed rules can't take your org's position** — CCM-05 deliberately
   doesn't assert password rotation (NIST 800-63B dropped it); CCM-08 ships
   an opinionated sensitive-port list instead of flagging every web tier.
3. **Same price** — Config bills per evaluation either way.

## Anatomy of a rule

```
config-rules/
├── shared/evaluator.py        # ALL the Config-API knowledge lives here
└── src/<rule_name>/handler.py # pure logic: evaluate(params, session) -> [Evaluation]
```

The contract, from [`shared/evaluator.py`](../../config-rules/shared/evaluator.py):

```python
@dataclass
class Evaluation:
    resource_type: str   # e.g. "AWS::S3::Bucket", "AWS::::Account"
    resource_id: str
    compliance: str      # COMPLIANT | NON_COMPLIANT | NOT_APPLICABLE
    annotation: str = ""
```

A rule module is three things: a `CONTROL_ID` constant (joins to the
catalog), an `evaluate()` function returning `Evaluation`s, and a one-line
`lambda_handler` delegating to the shared `run()`. The shared runner owns
everything every rule would otherwise duplicate:

- **`invokingEvent` is a JSON *string* inside the event** — the classic
  first-custom-rule stumbling block. Parsed once, in `parse_event()`.
- **Annotations cap at 256 chars** — Config rejects the whole
  `put_evaluations` call for one long annotation. Truncated centrally.
- **`put_evaluations` takes ≤100 evaluations per call** — batched centrally.

This split is also the testing strategy: `evaluate()` is testable with moto
alone, and the wire plumbing is tested *once* against a recording fake
([`tests/config_rules/test_evaluator.py`](../../tests/config_rules/test_evaluator.py)),
not re-tested through 12 rules.

## Periodic vs change-triggered (a real tradeoff table)

All 12 rules are **periodic** (ScheduledNotification): they query live state
via API instead of trusting the configuration-item snapshot Config delivers.

| | Periodic (chosen) | Change-triggered |
|---|---|---|
| Detection latency | the schedule (24 h here) | seconds after change |
| Testability | moto only — no Config service needed | must fabricate configuration items |
| Recorder dependency | none | dead if the recorder is off |
| Cost shape | re-lists whole populations each run | pay per change |
| Where it loses | huge populations (see scale notes) | the recorder meta-control (below) |

The recorder dependency is not academic: **CCM-11 (Config recorder enabled)
can only exist as a periodic rule.** A change-triggered rule watching the
recorder never fires once the recorder is off — permanent silence reads as
permanent green. That one sentence is the whole case for understanding
trigger types.

## Two rules in depth

### `s3_public_access_block` — the simplest complete rule

[Source](../../config-rules/src/s3_public_access_block/handler.py). Pattern
to copy for any account-level check:

1. Resolve the account ID via STS (it's the `resource_id` for
   `AWS::::Account` evaluations).
2. Call the API; **branch on the error code, not on exception type** —
   `NoSuchPublicAccessBlockConfiguration` *is* a verdict (NON_COMPLIANT,
   "nothing configured"), while any other ClientError should raise and fail
   loudly.
3. Check all four flags and **name the gap in the annotation**
   (`"flags disabled: BlockPublicPolicy"`) — the annotation becomes the
   ticket text; "non-compliant" with no *why* just creates a research task
   for the assignee.

Judgment embedded: it checks the *account-level* block, not per-bucket
settings, because per-bucket blocks don't constrain the next bucket someone
creates. The control with teeth is the account default — a theme that
repeats in CCM-04 (EBS encryption-by-default) below.

### `cloudtrail_enabled` — where verdict scope gets interesting

[Source](../../config-rules/src/cloudtrail_enabled/handler.py). Two
decisions to internalize:

**Account-level verdict, not per-trail.** The control is "API activity is
recorded everywhere," which one multi-region trail satisfies regardless of
how many abandoned single-region trails coexist. Grading trails individually
would mark an account with one good trail and three stale ones as 75%
failing — noise that trains owners to ignore findings.

**Exists ≠ logging.** A trail that someone ran `StopLogging` against still
appears in `DescribeTrails`. The rule therefore requires `IsLogging` from
`GetTrailStatus` — and the NON_COMPLIANT annotation distinguishes *no
trails* / *none multi-region* / *none logging*, because those are three
different remediations.

## The other ten, one decision each

| Rule | The decision worth knowing |
|---|---|
| CCM-02 s3_bucket_encryption | Post-2023, AWS encrypts all new buckets — so the rule has an opt-in `RequireKms` parameter; without it the check is nearly free to pass and says so in its docstring |
| CCM-03 rds_encryption | Annotation carries the remediation path (snapshot → encrypted copy → restore) because RDS encryption can't be flipped in place; scopes to instances and *says* Aurora clusters are out of scope rather than silently missing them |
| CCM-04 ebs_encryption | Emits per-volume verdicts **and** an account-level encryption-by-default evaluation from one rule: existing volumes are the backlog, the default is what stops it regrowing |
| CCM-05 iam_password_policy | Asserts length + reuse, **not rotation** (800-63B); rotation is an opt-in parameter for orgs whose framework still demands it. A managed rule can't express that posture |
| CCM-06 iam_user_mfa | API-only users get `NOT_APPLICABLE`, not skipped — a sampled population must show every member was *considered*; silent exclusion reads as a coverage gap |
| CCM-07 root_access_keys | Uses `GetAccountSummary` (one synchronous call) over the credential report (generate/poll cycle, extra failure mode, same bit of information) |
| CCM-08 sg_open_ingress | Flags a parameterized sensitive-port list, **not** all world-open ingress — 443-to-the-world is what load balancers do; `IpProtocol: -1` counts as every port |
| CCM-10 cloudtrail_log_validation | Per-trail (integrity is a per-output property), and `NOT_APPLICABLE` with zero trails — trail absence is CCM-09's finding; double-failing one root cause opens two tickets for one fix |
| CCM-11 config_recorder_enabled | The meta-control; must be periodic (see above); annotation notes that failing it blinds every change-triggered rule, so it outranks any single resource finding |
| CCM-12 vpc_flow_logs | Requires status `ACTIVE` (a flow log with broken delivery still exists in the API) and evaluates default VPCs like any other — unused default VPCs are where unmonitored traffic hides |

## Testing on moto

Pattern (see any file in
[`tests/config_rules/`](../../tests/config_rules/)): decorate with
`@mock_aws`, create the state with real boto3 calls, call `evaluate()`,
assert on the returned `Evaluation`s. Three cases minimum per rule:
compliant, non-compliant (asserting the annotation names the gap), and the
rule's boundary (NOT_APPLICABLE, parameter override, partial config).

Supporting pieces:

- [`tests/conftest.py`](../../tests/conftest.py) — an autouse fixture sets
  fake AWS credentials so boto3 can never touch a real account from tests,
  and provides `config_event()` for the wire-format tests.
- [`tests/support.py`](../../tests/support.py) — `FakeSession`: when moto
  *can't* represent a state (it cannot attach access keys to the root
  account), fake the one API call instead. The handler only ever calls
  `session.client(name)`, so a dict-backed fake session is the entire
  mechanism. This is [ADR-002](../decisions.md)'s escape hatch, used
  sparingly and visibly.

## Pitfalls actually hit

- **moto enforces S3 bucket-name rules** — `create_bucket(Bucket="a")`
  fails with `InvalidBucketName` (3-char minimum). Two tests failed on
  exactly this; use realistic names.
- **moto's Config service won't start a recorder without a delivery
  channel**, matching real AWS — the CCM-11 test had to create a bucket and
  delivery channel first. Fidelity cuts both ways: annoying in tests,
  reassuring in what the tests prove.
- **Don't test `put_evaluations` through moto at all** — moto's coverage of
  Config's evaluation APIs is partial. The recording-fake approach
  sidesteps the question and tests *our* batching/truncation, which is
  what's actually ours to break.

## Checkpoint

```sh
.venv/Scripts/python -m pytest tests/config_rules -q
# -> 43 passed
```

Every rule has compliant/non-compliant/boundary coverage and no test needed
AWS credentials. Next: [Chapter 03 — the normalizer](03-normalizer.md),
where these `Evaluation`s become one schema among three sources.
