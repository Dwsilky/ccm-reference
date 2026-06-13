"""Stage each Config-rule Lambda for deployment.

Lambda functions don't share a filesystem, so every rule's zip must vendor
the shared/ package next to its handler (the single-source-in-repo,
duplicated-in-artifact tradeoff from shared/evaluator.py's docstring).
This script builds deploy/build/<rule>/ staging dirs; Terraform's
archive_file data source zips them.

Run before `terraform apply`: python scripts/package_lambdas.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "config-rules" / "src"
SHARED = ROOT / "config-rules" / "shared"
BUILD = ROOT / "deploy" / "build"


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)

    rules = sorted(
        d.name for d in SRC.iterdir() if d.is_dir() and (d / "handler.py").exists()
    )
    for rule in rules:
        stage = BUILD / rule
        stage.mkdir(parents=True)
        shutil.copy2(SRC / rule / "handler.py", stage / "handler.py")
        shutil.copytree(SHARED, stage / "shared",
                        ignore=shutil.ignore_patterns("__pycache__"))

    print(f"staged {len(rules)} rules under {BUILD.relative_to(ROOT)}:")
    for rule in rules:
        print(f"  {rule}")


if __name__ == "__main__":
    main()
