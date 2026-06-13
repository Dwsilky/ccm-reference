# Build Guide — how to recreate this system from an empty directory

This guide explains every part of the CCM reference implementation in enough
depth to rebuild it yourself, adapt it to your own organization, or teach it
to someone else. It is the document I wish existed when I started: not just
*what* the code does, but *why each piece is shaped the way it is* and *what
went wrong while building it*.

## Who this is for

Three readers, deliberately:

1. **GRC people who don't write much code** — every chapter starts with the
   control-assurance problem before any Python appears, and there's a
   [glossary](00-overview.md#glossary) for the AWS/engineering terms.
2. **Engineers who don't do GRC** — the same chapters explain why the
   compliance constraints exist (why "couldn't check" must never equal
   "passed", why a generated coverage matrix matters to an auditor).
3. **Me, in a year** — rebuilding this from memory, or extending it, without
   re-deriving the decisions.

## The chapters

Every chapter follows the same skeleton: **why this layer exists → design
decisions (and what was rejected) → how it's built, file by file → how it's
tested → pitfalls actually hit → checkpoint** (what must work before you move
on).

| # | Chapter | What you build | Rebuild time |
|---|---|---|---|
| 00 | [Overview](00-overview.md) | Nothing yet — the mental model, architecture, and one finding traced end-to-end | 30 min read |
| 01 | [Foundation](01-foundation.md) | Repo scaffold + the control catalog + generated coverage matrix | 2–3 h |
| 02 | [Config rules](02-config-rules.md) | 12 custom AWS Config rules with moto-tested evaluation logic | 1–2 h per rule at first, ~30 min once the pattern clicks |
| 03 | [Normalizer & bus](03-normalizer.md) | **The centerpiece**: source → ASFF adapters + the finding bus | 4–6 h |
| 04 | [Collectors](04-collectors.md) | 4 evidence collectors for controls no platform can evaluate | 2–4 h each |
| 05 | [Router & judgment tracker](05-router.md) | Finding → owner → ticket → SLA → evidence artifact; the end-to-end demo | 4–6 h |
| 06 | [Deploy](06-deploy.md) | Terraform to prove it on real AWS — and tear it down | 2–3 h |
| 07 | [Extending](07-extending.md) | Worked examples: add one new control to *each* bucket; adapt the whole thing to your org | reference |

**If you only read one chapter, read [03](03-normalizer.md).** The normalizer
is the idea the rest of the repo exists to demonstrate: many sources, one
schema, one bus. Everything else is an instance of "add a source."

**If you want to extend rather than rebuild, start at [07](07-extending.md).**

## Prerequisites

- Python 3.12+ and git. That's it for chapters 00–05 — the entire pipeline
  runs locally against [moto](https://github.com/getmoto/moto) with **zero
  AWS credentials and zero spend**.
- Chapter 06 additionally needs Terraform ≥ 1.5 and a *sandbox* AWS account.
- A GitHub account if you want the GitHub-backed collectors (CCM-13, CCM-16)
  and live ticket filing to run against a real repo.

## How to use this guide to rebuild

Build in chapter order. The order isn't arbitrary — each layer is fully
testable before the next exists (the [overview](00-overview.md#why-this-build-order)
explains why), so you always have a green test suite and a working slice.
Commit small and commit often; a CCM repo whose own change history is one
giant commit undermines its own change-management story (see CCM-16).
