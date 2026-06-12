"""Generate coverage-matrix.md from mappings/controls.yaml.

The matrix is the README centerpiece; generating it from the same YAML the
pipeline reads means the documented coverage can never drift from reality.
Run: python scripts/gen_matrix.py
"""

from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

BUCKETS = {
    "machine": (
        "Machine-evaluable",
        "Config state we can compute a pass/fail on. Fully automated.",
    ),
    "attestable": (
        "Evidence-attestable",
        "No computable pass/fail, but the artifact proving the process ran "
        "can be pulled on a schedule.",
    ),
    "judgment": (
        "Human-judgment",
        "Not automatable. We automate only the reminder and the tracking of "
        "the attestation.",
    ),
}


def main() -> None:
    catalog = yaml.safe_load((ROOT / "mappings" / "controls.yaml").read_text(encoding="utf-8"))
    controls = catalog["controls"]

    lines = [
        "# Control coverage matrix",
        "",
        f"_Generated from `mappings/controls.yaml` by `scripts/gen_matrix.py` "
        f"on {date.today().isoformat()}. Do not edit by hand._",
        "",
    ]

    total = len(controls)
    implemented = sum(1 for c in controls if c["status"] == "implemented")
    lines += [
        f"**{total} controls** across the three buckets — "
        f"**{implemented} implemented**, {total - implemented} planned.",
        "",
    ]

    for bucket, (title, blurb) in BUCKETS.items():
        rows = [c for c in controls if c["bucket"] == bucket]
        done = sum(1 for c in rows if c["status"] == "implemented")
        lines += [
            f"## {title} ({done}/{len(rows)} implemented)",
            "",
            f"_{blurb}_",
            "",
            "| ID | Control | CSF | 800-53 | Collection method | Source | Status |",
            "|---|---|---|---|---|---|---|",
        ]
        for c in rows:
            nist = ", ".join(c["nist_800_53"])
            status = "✅ implemented" if c["status"] == "implemented" else "⬜ planned"
            lines.append(
                f"| {c['id']} | {c['name']} | {c['csf']} | {nist} "
                f"| {c['method']} | `{c['source']}` | {status} |"
            )
        lines.append("")

    out = ROOT / "coverage-matrix.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(ROOT)} ({total} controls, {implemented} implemented)")


if __name__ == "__main__":
    main()
