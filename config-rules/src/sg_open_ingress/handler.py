"""CCM-08 — no 0.0.0.0/0 (or ::/0) ingress on sensitive ports.

CSF PR.AC-5 / 800-53 SC-7. Bucket: machine-evaluable.

Deliberately NOT "no world-open ingress at all": 80/443 open to the internet
is what load balancers are for, and a rule that flags every web tier trains
owners to ignore it. The port list targets admin and data-store planes
(SSH/RDP, SQL, cache, search) and is a rule parameter so an org can tighten
or extend it without code changes.

`IpProtocol: -1` (all traffic) counts as exposing every sensitive port — a
surprising number of "temporary" SG rules are exactly this.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-08"

# SSH, RDP, MySQL, Postgres, MSSQL, MongoDB, Redis, Elasticsearch
DEFAULT_SENSITIVE_PORTS = "22,3389,3306,5432,1433,27017,6379,9200"


def _world_open(perm: dict) -> bool:
    v4 = any(r.get("CidrIp") == "0.0.0.0/0" for r in perm.get("IpRanges", []))
    v6 = any(r.get("CidrIpv6") == "::/0" for r in perm.get("Ipv6Ranges", []))
    return v4 or v6


def evaluate(params: dict, session) -> list[Evaluation]:
    ports = {
        int(p)
        for p in str(params.get("SensitivePorts", DEFAULT_SENSITIVE_PORTS)).split(",")
        if p.strip()
    }
    ec2 = session.client("ec2")

    evaluations = []
    for page in ec2.get_paginator("describe_security_groups").paginate():
        for sg in page["SecurityGroups"]:
            exposed: set[int] = set()
            for perm in sg["IpPermissions"]:
                if not _world_open(perm):
                    continue
                if perm.get("IpProtocol") == "-1":
                    exposed |= ports
                    continue
                from_port, to_port = perm.get("FromPort"), perm.get("ToPort")
                if from_port is None:
                    continue
                exposed |= {p for p in ports if from_port <= p <= to_port}

            if exposed:
                evaluations.append(
                    Evaluation(
                        "AWS::EC2::SecurityGroup",
                        sg["GroupId"],
                        NON_COMPLIANT,
                        f"{CONTROL_ID}: '{sg['GroupName']}' is world-open on sensitive "
                        f"port(s) {sorted(exposed)}.",
                    )
                )
            else:
                evaluations.append(
                    Evaluation(
                        "AWS::EC2::SecurityGroup",
                        sg["GroupId"],
                        COMPLIANT,
                        f"{CONTROL_ID}: no world-open ingress on sensitive ports.",
                    )
                )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
