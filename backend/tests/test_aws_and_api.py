"""Scanner, clean-up and API, tested against a fake AWS (moto). No real account needed."""

import re
import sys
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import aws, main  # noqa: E402

APP = Path(main.__file__).parent


@pytest.fixture
def fake_aws(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setattr(main, "SCAN_DIR", tmp_path)
    monkeypatch.setitem(main.connection, "profile", None)
    with mock_aws():
        yield boto3.Session(region_name="us-east-1")


def test_scan_finds_waste_in_different_regions(fake_aws):
    fake_aws.client("ec2", region_name="us-west-2").create_volume(
        AvailabilityZone="us-west-2a", Size=50, VolumeType="gp3")
    fake_aws.client("ec2", region_name="ap-southeast-1").allocate_address(Domain="vpc")

    s = aws.scan_account(aws.make_session())
    kinds = {(r.kind, r.region) for r in s.resources}
    assert ("volume", "us-west-2") in kinds and ("elastic_ip", "ap-southeast-1") in kinds
    assert s.account.startswith("********")
    ip = next(r for r in s.resources if r.kind == "elastic_ip")
    assert ip.info["attached_to"] is None          # AWS can send "" here; we must read it as "not attached"


def test_scan_fix_and_scan_again_through_the_api(fake_aws):
    fake_aws.client("ec2", region_name="ap-south-1").allocate_address(Domain="vpc")
    client = TestClient(main.app)

    assert client.post("/api/connect", json={}).json()["connected"] is True
    scan_id = client.post("/api/scan").json()["id"]
    finding = next(f for f in client.get(f"/api/report/{scan_id}").json()["findings"]
                   if f["rule"] == "Unused Elastic IP")

    done = client.post("/api/fix", json={"scan_id": scan_id, "resource_id": finding["resource_id"],
                                         "action": finding["fix_action"]})
    assert done.status_code == 200 and "Released" in done.json()["message"]

    scan_id = client.post("/api/scan").json()["id"]
    rules = [f["rule"] for f in client.get(f"/api/report/{scan_id}").json()["findings"]]
    assert "Unused Elastic IP" not in rules


def test_fix_refuses_anything_the_scan_did_not_flag(fake_aws):
    ec2 = fake_aws.client("ec2", region_name="ap-south-1")
    ami = ec2.describe_images()["Images"][0]["ImageId"]
    busy = ec2.run_instances(ImageId=ami, InstanceType="t3.micro", MinCount=1, MaxCount=1)["Instances"][0]
    client = TestClient(main.app)
    scan_id = client.post("/api/scan").json()["id"]
    r = client.post("/api/fix", json={"scan_id": scan_id, "resource_id": busy["InstanceId"], "action": "terminate"})
    assert r.status_code == 400


def test_spare_disk_is_backed_up_before_delete(fake_aws):
    ec2 = fake_aws.client("ec2", region_name="ap-south-1")
    vol = ec2.create_volume(AvailabilityZone="ap-south-1a", Size=5, VolumeType="gp3")["VolumeId"]
    client = TestClient(main.app)
    scan_id = client.post("/api/scan").json()["id"]
    client.post("/api/fix", json={"scan_id": scan_id, "resource_id": vol, "action": "delete_volume"})
    backups = ec2.describe_snapshots(Filters=[{"Name": "volume-id", "Values": [vol]}])["Snapshots"]
    assert len(backups) == 1
    assert ec2.describe_volumes(Filters=[{"Name": "volume-id", "Values": [vol]}])["Volumes"] == []


def test_connect_with_unknown_profile_fails_cleanly(fake_aws):
    r = TestClient(main.app).post("/api/connect", json={"profile": "no-such-profile"}).json()
    assert r["connected"] is False and "no-such-profile" in r["error"]


def test_cost_checker_and_bad_ids():
    client = TestClient(main.app)
    assert client.post("/api/estimate", json={}).json()["monthly_total"] > 0
    assert client.get("/api/report/..%2Fsecret").status_code == 404
    assert client.get("/api/report/nope").status_code == 404


def test_scanner_only_reads():
    """aws.py must only use describe/get/list calls; changes live in fixes.py only."""
    source = (APP / "aws.py").read_text()
    calls = set(re.findall(r"\b(?:ec2|cw|elb|s3)\.(\w+)\(", source))
    calls |= set(re.findall(r'get_paginator\("(\w+)"\)', source))
    assert calls and all(c.startswith(("describe_", "get_", "list_")) for c in calls), calls
