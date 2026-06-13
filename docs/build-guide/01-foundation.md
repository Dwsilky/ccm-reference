# 01 — Foundation: catalog-as-code

**You will build:** the repo scaffold, the control catalog
(`mappings/controls.yaml`), and the script that generates the coverage
matrix from it. No AWS, no findings yet — but every later layer joins to
what you define here.

## Why this layer exists

A CCM program lives or dies on one question: *what controls do you cover,
and how?* If the answer lives in a README table someone edits by hand, it
drifts from the code within a month — and a coverage claim that doesn't
match reality is itself an audit finding. So the catalog is data
(`controls.yaml`), the matrix is generated from it, and the pipeline reads
the same file at runtime. One source of truth; the docs *cannot* disagree
with the code.

## Design decisions

**Directory names are audit-domain, not Python-domain.** The tree reads
`config-rules/`, `collectors/`, `router/`, `evidence/` — a GRC reviewer
should navigate by control concept, not by packaging convention. The cost:
hyphens aren't importable, so [`conftest.py`](../../conftest.py) (5 lines)
puts `config-rules/` and the repo root on `sys.path` for tests. A small,
visible shim beats renaming the domain to please the import system.

**`requirements.txt`, not an installable package.** This is a reference
implementation, not a library — nothing pip-installs it. Pretending
otherwise adds `pyproject` build config that answers questions nobody asks.
[`pyproject.toml`](../../pyproject.toml) exists only to configure pytest and
ruff (note `known-first-party` so import sorting understands our layout).

**Every Lambda is standalone by design.** Each Config rule ships as its own
zip in deployment, so there is deliberately no shared installed package —
shared code is vendored at package time (you'll meet this again in
[chapter 06](06-deploy.md)).

## The catalog schema, field by field

[`mappings/controls.yaml`](../../mappings/controls.yaml) — one entry per
control:

```yaml
- id: CCM-07                      # joins code <-> catalog <-> tickets <-> evidence
  name: Root account has no access keys
  bucket: machine                 # machine | attestable | judgment (ADR-003)
  csf: PR.AC-4                    # NIST CSF function.category-id
  nist_800_53: [AC-6]             # list; some controls map to several
  severity: CRITICAL              # ASFF label applied when the control FAILS
  prowler_checks: [iam_no_root_access_key]   # optional scanner attribution
  method: Custom Config rule (periodic Lambda)
  source: config-rules/src/root_access_keys  # where the implementation lives
  status: implemented             # implemented | planned
```

Field rationale, in the order they earn their keep:

- **`id`** — the join key for the entire system. It appears in rule code
  (`CONTROL_ID`), ASFF `ProductFields`, ticket bodies, evidence paths.
  Pick a scheme and never reuse an ID.
- **`bucket`** — the sorted three-bucket assignment. Forcing this into the
  catalog (one value, no hedging) is what makes the sorting honest.
- **`severity`** — *failure* severity. Passing findings are always
  INFORMATIONAL regardless ([ADR-004](../decisions.md)); a passing critical
  control is not a critical event.
- **`prowler_checks`** — reverse-maps scanner check IDs onto your catalog so
  scanner findings count toward coverage. Optional and best-effort by
  design: unmapped scanner findings still flow (see
  [chapter 03](03-normalizer.md)).
- **`status`** — drives the generated matrix's implemented/planned split,
  which is your program's coverage metric in embryo.

The typed loader is [`normalizer/catalog.py`](../../normalizer/catalog.py)
— a frozen dataclass + `lru_cache`, ~50 lines. Everything that needs control
metadata (adapters, router, matrix generator) goes through it.

## The generated matrix

[`scripts/gen_matrix.py`](../../scripts/gen_matrix.py) reads the catalog and
writes [`coverage-matrix.md`](../../coverage-matrix.md): summary counts, then
one table per bucket with each bucket's definition inline. The output file
opens with *"Generated… do not edit by hand"* — and because the same YAML
feeds the runtime, the matrix is correct by construction.

This is a 60-line script, and it's the highest-leverage 60 lines in the
repo: it's what lets a reviewer assess coverage in 30 seconds.

## Choosing your own controls (if you're adapting this)

Heuristics that shaped the 21 here:

1. **Spread across all three buckets** — a catalog that's 100% bucket 1 says
   "I automated the easy stuff"; the bucket 2/3 handling is the senior
   signal.
2. **Bucket 1: only pick controls whose state you can actually read.** "S3
   encryption" is one API call; "data is classified correctly" is not a
   config read, however tempting the name sounds.
3. **Pair related controls that need different verdict scopes** — CCM-09
   (account-level: *any* good trail) vs CCM-10 (per-trail: *every* trail) —
   because explaining that distinction proves you understand evaluation
   scope.
4. **Include one meta-control** (CCM-11: is the monitoring system itself on?).
5. **Depth over breadth.** 20–30 done with judgment beats 200 managed-rule
   references. Nobody is impressed by volume; everybody probes depth.

## Pitfalls actually hit

- **Mutating YAML with naive string replacement.** Status flips during the
  build used a script splitting on `"\n  - id: "` — fine, but one run was
  silently skipped because an earlier command in the same shell chain failed
  (`&&` short-circuit) and the only symptom was a wrong count later. Check
  the *output* of generation steps (`21 controls, 16 implemented`) against
  what you expect, every time.
- **`grep -c "status: implemented"` lies** — it also matches the schema
  comment in the file header. Count with the parser
  (`python -c "...load_catalog()..."`), not with grep.

## Checkpoint

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # .venv/bin on POSIX
.venv/Scripts/python scripts/gen_matrix.py
# -> wrote coverage-matrix.md (21 controls, 21 implemented)
.venv/Scripts/python -c "from normalizer.catalog import load_catalog; c=load_catalog(); print(len(c), c['CCM-07'].severity)"
# -> 21 CRITICAL
```

Next: [Chapter 02 — Config rules](02-config-rules.md), where the catalog's
bucket-1 rows become running code.
