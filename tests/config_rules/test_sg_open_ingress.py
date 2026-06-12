import boto3
from moto import mock_aws

from src.sg_open_ingress.handler import evaluate


def _sg_with_ingress(ec2, name, permissions):
    group_id = ec2.create_security_group(GroupName=name, Description=name)["GroupId"]
    if permissions:
        ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=permissions)
    return group_id


def _world_tcp(from_port, to_port):
    return {
        "IpProtocol": "tcp",
        "FromPort": from_port,
        "ToPort": to_port,
        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
    }


def _result_for(session, group_id, params=None):
    return {e.resource_id: e for e in evaluate(params or {}, session)}[group_id]


@mock_aws
def test_world_open_ssh_is_non_compliant():
    session = boto3.Session()
    sg = _sg_with_ingress(session.client("ec2"), "ssh-open", [_world_tcp(22, 22)])
    result = _result_for(session, sg)
    assert result.compliance == "NON_COMPLIANT"
    assert "22" in result.annotation


@mock_aws
def test_world_open_https_is_fine():
    # 443 to the world is what load balancers do; flagging it teaches owners
    # to ignore the rule.
    session = boto3.Session()
    sg = _sg_with_ingress(session.client("ec2"), "web", [_world_tcp(443, 443)])
    assert _result_for(session, sg).compliance == "COMPLIANT"


@mock_aws
def test_all_traffic_rule_counts_as_every_sensitive_port():
    session = boto3.Session()
    sg = _sg_with_ingress(
        session.client("ec2"),
        "wide-open",
        [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
    )
    result = _result_for(session, sg)
    assert result.compliance == "NON_COMPLIANT"
    assert "3389" in result.annotation


@mock_aws
def test_port_range_spanning_sensitive_ports_is_caught():
    session = boto3.Session()
    sg = _sg_with_ingress(session.client("ec2"), "range", [_world_tcp(3000, 6000)])
    result = _result_for(session, sg)
    assert result.compliance == "NON_COMPLIANT"
    assert "3306" in result.annotation and "5432" in result.annotation


@mock_aws
def test_port_list_is_a_rule_parameter():
    session = boto3.Session()
    sg = _sg_with_ingress(session.client("ec2"), "web2", [_world_tcp(443, 443)])
    strict = _result_for(session, sg, {"SensitivePorts": "443"})
    assert strict.compliance == "NON_COMPLIANT"
