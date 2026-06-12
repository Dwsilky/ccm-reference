"""CCM-06 — MFA enabled for console users.

CSF PR.AC-7 / 800-53 IA-2(1). Bucket: machine-evaluable.

Scoped to users with a *login profile* (console password). API-only users get
NOT_APPLICABLE rather than being skipped: an auditor sampling the population
should see that every user was considered and why some are out of scope —
silent exclusion reads as a coverage gap.

MFA on API access is a different control (it needs policy conditions on
aws:MultiFactorAuthPresent, not a device check) and pretending this rule
covers it would overstate assurance.
"""

from botocore.exceptions import ClientError

from shared.evaluator import COMPLIANT, NON_COMPLIANT, NOT_APPLICABLE, Evaluation, run

CONTROL_ID = "CCM-06"


def _has_console_password(iam, username: str) -> bool:
    try:
        iam.get_login_profile(UserName=username)
        return True
    except ClientError as err:
        if err.response["Error"]["Code"] == "NoSuchEntity":
            return False
        raise


def evaluate(params: dict, session) -> list[Evaluation]:
    iam = session.client("iam")

    evaluations = []
    for page in iam.get_paginator("list_users").paginate():
        for user in page["Users"]:
            name = user["UserName"]
            if not _has_console_password(iam, name):
                evaluations.append(
                    Evaluation(
                        "AWS::IAM::User",
                        name,
                        NOT_APPLICABLE,
                        f"{CONTROL_ID}: no console password; MFA-for-API is a separate "
                        "control.",
                    )
                )
                continue

            devices = iam.list_mfa_devices(UserName=name)["MFADevices"]
            if devices:
                evaluations.append(
                    Evaluation(
                        "AWS::IAM::User",
                        name,
                        COMPLIANT,
                        f"{CONTROL_ID}: console user has {len(devices)} MFA device(s).",
                    )
                )
            else:
                evaluations.append(
                    Evaluation(
                        "AWS::IAM::User",
                        name,
                        NON_COMPLIANT,
                        f"{CONTROL_ID}: console user has a password but no MFA device.",
                    )
                )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
