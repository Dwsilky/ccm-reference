"""Run the complete CCM loop locally: zero AWS credentials, zero spend.

    seed moto AWS state -> run Config-rule logic -> normalize
    Prowler sample      ----------------------------^
    file collectors     ----------------------------^
    judgment tracker    ----------------------------^
                                -> LocalBus -> router -> tickets + evidence/

Default is a dry run (tickets are recorded, not filed). `--live` files real
GitHub Issues on the repo — outward-facing, so it is opt-in.

Usage: python scripts/demo.py [--live] [--repo owner/name]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "config-rules"))

# Fake credentials BEFORE boto3 sessions exist: moto intercepts the calls,
# these only satisfy the SDK chain (same trick as tests/conftest.py).
os.environ.setdefault("AWS_ACCESS_KEY_ID", "demo")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "demo")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import json  # noqa: E402

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from collectors import backup_restore, vuln_sla  # noqa: E402
from normalizer.adapters import from_collector, from_config_evaluation, from_prowler  # noqa: E402
from normalizer.bus import LocalBus  # noqa: E402
from router import judgment_tracker  # noqa: E402
from router.router import route  # noqa: E402
from router.tickets import DryRunTickets, GitHubTickets  # noqa: E402
from src.iam_password_policy.handler import evaluate as eval_password_policy  # noqa: E402
from src.root_access_keys.handler import evaluate as eval_root_keys  # noqa: E402
from src.s3_bucket_encryption.handler import evaluate as eval_s3_encryption  # noqa: E402
from src.s3_public_access_block.handler import evaluate as eval_pab  # noqa: E402

PROWLER_SAMPLE = ROOT / "normalizer" / "samples" / "prowler" / "findings.ocsf.json"
REGION = "us-east-1"


def gather_config_findings() -> list[dict]:
    """Seed a deliberately imperfect account in moto and run real rule logic."""
    with mock_aws():
        session = boto3.Session()
        account = session.client("sts").get_caller_identity()["Account"]

        s3 = session.client("s3")
        s3.create_bucket(Bucket="demo-data-lake")
        s3.delete_bucket_encryption(Bucket="demo-data-lake")  # CCM-02 will fail
        # No account public-access block (CCM-01 fails), no password policy
        # (CCM-05 fails), no root keys (CCM-07 passes) — a believable mix.

        findings = []
        for control_id, evaluate in (
            ("CCM-01", eval_pab),
            ("CCM-02", eval_s3_encryption),
            ("CCM-05", eval_password_policy),
            ("CCM-07", eval_root_keys),
        ):
            for evaluation in evaluate({}, session):
                findings.append(
                    from_config_evaluation(evaluation, control_id, account, REGION)
                )
        return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="file real GitHub Issues instead of a dry run")
    parser.add_argument("--repo", default="Dwsilky/ccm-reference")
    args = parser.parse_args()

    bus_path = ROOT / "evidence" / "findings.jsonl"
    if bus_path.exists():
        bus_path.unlink()  # each demo is a fresh, reproducible run
    bus = LocalBus(bus_path)

    config_findings = gather_config_findings()
    bus.publish(config_findings)
    print(f"[1/4] config-rules : {len(config_findings)} findings (real rule logic on moto)")

    prowler = [
        from_prowler(check)
        for check in json.loads(PROWLER_SAMPLE.read_text(encoding="utf-8"))
    ]
    bus.publish(prowler)
    print(f"[2/4] prowler      : {len(prowler)} findings (vendored scanner sample)")

    collected = [
        from_collector(backup_restore.collect(), account_id="000000000000"),
        from_collector(vuln_sla.collect(), account_id="000000000000"),
    ]
    bus.publish(collected)
    print(f"[3/4] collectors   : {len(collected)} findings (backup log + vuln export)")

    tracked = [
        from_collector(result, account_id="000000000000", source="tracker")
        for result in judgment_tracker.collect_all()
    ]
    bus.publish(tracked)
    print(f"[4/4] tracker      : {len(tracked)} findings (judgment attestations)")

    tickets = GitHubTickets(args.repo) if args.live else DryRunTickets()
    report = route(bus, tickets, now=datetime.now(UTC))

    print("\n--- routing report ---")
    print(f"findings on bus     : {report['findings_seen']}  {report['by_status']}")
    print(f"tickets {'filed' if args.live else '(dry-run)'}   : {len(report['routed'])}")
    for item in report["routed"]:
        print(f"  {item['id']}\n    -> owner {item['owner']}, due {item['due']}, {item['ticket']}")
    print(f"needs attention     : {report['needs_attention_not_available'] or 'none'}")
    print(f"evidence artifacts  : {len(report['evidence_artifacts'])} under evidence/")
    print(f"sla breaches        : {len(report['sla_breaches'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
