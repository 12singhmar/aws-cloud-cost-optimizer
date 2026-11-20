"""The boto3 scanner and the API, tested against a fake AWS (moto) so no account is needed."""

import re
import sys
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import aws, main  # noqa: E402

REGION = "ap-south-1"


@pytest.fixture
def fake_aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield boto3.Session(region_name=REGION)


def test_scan_reads_a_fake_account(fake_aws):
    ec2 = fake_aws.client("ec2")
    ami = ec2.describe_images()["Images"][0]["ImageId"]
    ec2.run_instances(ImageId=ami, InstanceType="t3.micro", MinCount=1, MaxCount=1)
    vol = ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=1, VolumeType="gp3")["VolumeId"]
    ec2.allocate_address(Domain="vpc")

    s = aws.scan_account(fake_aws)
    assert s.source == "aws" and s.account.startswith("********")
    assert [i.type for i in s.instances] == ["t3.micro"]
    assert any(v.id == vol and v.state == "available" for v in s.volumes)
    assert s.elastic_ips[0].attached_to is None      # moto returns "" here; we must treat it as None


def test_api_scan_then_report(fake_aws, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SCAN_DIR", tmp_path)
    fake_aws.client("ec2").allocate_address(Domain="vpc")
    client = TestClient(main.app)

    assert client.post("/api/connect", json={"region": REGION}).json()["connected"] is True
    scan_id = client.post("/api/scan").json()["id"]
    report = client.get(f"/api/report/{scan_id}").json()
    # (moto also pre-loads its own fake snapshots, so check only our IP)
    assert any(f["rule"] == "Unused Elastic IP" for f in report["findings"])
    assert client.get("/api/scans").json()[0]["id"] == scan_id


def test_connect_with_unknown_profile_fails_cleanly():
    client = TestClient(main.app)
    result = client.post("/api/connect", json={"profile": "no-such-profile"}).json()
    assert result["connected"] is False and "no-such-profile" in result["error"]
    client.post("/api/connect", json={})        # reset


def test_optimize_and_usage_endpoints():
    client = TestClient(main.app)
    r = client.post("/api/optimize", json={"instance_type": "m5.xlarge", "peak_cpu": 25, "avg_cpu": 8})
    assert r.status_code == 200 and r.json()["optimized_monthly"] < r.json()["baseline_monthly"]
    assert client.post("/api/optimize", json={"instance_type": "x9.huge"}).status_code == 400
    servers = client.get("/api/usage/public-nab-ec2").json()["servers"]
    assert len(servers) == 8 and all(s["workload"]["region"] == "us-east-1" for s in servers)


def test_public_data_report_and_bad_ids():
    client = TestClient(main.app)
    report = client.get("/api/report/public-nab-ec2").json()
    assert len(report["findings"]) == 3          # 3 of the 8 real EC2 instances are idle
    assert "Numenta" in report["scan"]["description"]
    assert client.get("/api/report/nope").status_code == 404
    assert client.get("/api/report/..%2Fsecret").status_code == 404


def test_scanner_only_reads():
    """The scanner must never change anything in AWS: only describe/get/list calls."""
    source = (Path(main.__file__).parent / "aws.py").read_text()
    calls = set(re.findall(r"\b(?:ec2|cw|s3)\.(\w+)\(", source))
    calls |= set(re.findall(r'get_paginator\("(\w+)"\)', source))
    assert calls, "no AWS calls found"
    assert all(c.startswith(("describe_", "get_", "list_")) for c in calls), calls
