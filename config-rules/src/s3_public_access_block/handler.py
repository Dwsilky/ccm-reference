"""CCM-01 — S3 account-level public access block enabled.

CSF PR.DS-5 / 800-53 SC-7. Bucket: machine-evaluable.

Checks the *account-level* block, not per-bucket settings: per-bucket blocks
can be silently undone by whoever creates the next bucket, so the account
block is the control with teeth. All four flags must be on — a partial block
(e.g. ACLs blocked but policies not) still permits public exposure paths.
"""

from botocore.exceptions import ClientError

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-01"

REQUIRED_FLAGS = (
    "BlockPublicAcls",
    "IgnorePublicAcls",
    "BlockPublicPolicy",
    "RestrictPublicBuckets",
)


def evaluate(params: dict, session) -> list[Evaluation]:
    account_id = session.client("sts").get_caller_identity()["Account"]
    s3control = session.client("s3control")

    try:
        cfg = s3control.get_public_access_block(AccountId=account_id)[
            "PublicAccessBlockConfiguration"
        ]
    except ClientError as err:
        if err.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
            return [
                Evaluation(
                    "AWS::::Account",
                    account_id,
                    NON_COMPLIANT,
                    f"{CONTROL_ID}: no account-level S3 public access block is configured.",
                )
            ]
        raise

    off = [flag for flag in REQUIRED_FLAGS if not cfg.get(flag)]
    if off:
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                NON_COMPLIANT,
                f"{CONTROL_ID}: public access block flags disabled: {', '.join(off)}.",
            )
        ]
    return [
        Evaluation(
            "AWS::::Account",
            account_id,
            COMPLIANT,
            f"{CONTROL_ID}: all four account-level public access block flags enabled.",
        )
    ]


def lambda_handler(event, context):
    return run(event, context, evaluate)
