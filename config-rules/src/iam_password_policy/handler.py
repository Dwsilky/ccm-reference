"""CCM-05 — IAM account password policy meets standard.

CSF PR.AC-1 / 800-53 IA-5. Bucket: machine-evaluable.

Defaults follow current NIST 63B-leaning practice: length over complexity
churn — 14+ chars and reuse prevention, but NO forced rotation check.
MaxPasswordAge is deliberately not asserted; mandatory rotation drives
predictable-suffix behavior and 800-63B dropped it. Organizations that still
require it (e.g. for PCI) can assert it via the MaxPasswordAge parameter.
"""

from botocore.exceptions import ClientError

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-05"

# requirement -> (policy field, default threshold, comparator)
DEFAULTS = {
    "MinimumPasswordLength": 14,
    "PasswordReusePrevention": 24,
}
REQUIRED_TRUE = (
    "RequireSymbols",
    "RequireNumbers",
    "RequireUppercaseCharacters",
    "RequireLowercaseCharacters",
)


def evaluate(params: dict, session) -> list[Evaluation]:
    iam = session.client("iam")
    account_id = session.client("sts").get_caller_identity()["Account"]

    try:
        policy = iam.get_account_password_policy()["PasswordPolicy"]
    except ClientError as err:
        if err.response["Error"]["Code"] == "NoSuchEntity":
            return [
                Evaluation(
                    "AWS::::Account",
                    account_id,
                    NON_COMPLIANT,
                    f"{CONTROL_ID}: no account password policy is set (AWS defaults apply).",
                )
            ]
        raise

    failures = []

    for field, default in DEFAULTS.items():
        threshold = int(params.get(field, default))
        actual = policy.get(field) or 0
        if actual < threshold:
            failures.append(f"{field}={actual} (need >={threshold})")

    for field in REQUIRED_TRUE:
        if not policy.get(field):
            failures.append(f"{field}=false")

    # Opt-in rotation assertion for orgs whose framework still mandates it.
    if "MaxPasswordAge" in params:
        limit = int(params["MaxPasswordAge"])
        actual_age = policy.get("MaxPasswordAge")
        if not actual_age or actual_age > limit:
            failures.append(f"MaxPasswordAge={actual_age} (need <={limit})")

    if failures:
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                NON_COMPLIANT,
                f"{CONTROL_ID}: password policy gaps: {'; '.join(failures)}.",
            )
        ]
    return [
        Evaluation(
            "AWS::::Account",
            account_id,
            COMPLIANT,
            f"{CONTROL_ID}: password policy meets standard.",
        )
    ]


def lambda_handler(event, context):
    return run(event, context, evaluate)
