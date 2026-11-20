"""API smoke tests (on the demo snapshot) and the AWS collector against a fake AWS (moto)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_snapshot_list():
    assert client.get("/api/health").json()["status"] == "ok"
    ids = [s["id"] for s in client.get("/api/snapshots").json()]
    assert "demo" in ids


def test_demo_analysis_and_lab_score():
    a = client.get("/api/analysis/demo").json()
    assert a["snapshot"]["source"] == "demo"
    assert a["summary"]["findings"] > 0 and a["summary"]["blocked"] >= 1
    lab = client.get("/api/lab/demo").json()
    assert lab["available"] and lab["precision"] == 1.0 and lab["recall"] == 1.0


def test_bill_fleet_prices_rules():
    assert client.get("/api/billcheck/demo").json()["available"]
    fleet = client.get("/api/fleet").json()
    assert fleet["available"] and fleet["vms_total"] > 2_000_000
    assert client.get("/api/prices/ap-south-1").json()["region"] == "ap-south-1"
    assert len(client.get("/api/rules").json()) == 8


def test_bad_ids_are_rejected_safely():
    assert client.get("/api/analysis/does-not-exist").status_code == 404
    assert client.get("/api/analysis/..%2F..%2Fsecrets").status_code == 404
    assert client.get("/api/lab/nope").json() == {"available": False}


def test_api_is_read_only():
    methods = {m for r in app.routes for m in getattr(r, "methods", set())}
    assert methods <= {"GET", "HEAD"}


# --- collector against moto (fake AWS) ---------------------------------------------

moto = pytest.importorskip("moto")


@moto.mock_aws
def test_collector_reads_a_fake_account(monkeypatch):
    import boto3
    from collect_snapshot import collect

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    region = "ap-south-1"
    sess = boto3.Session(region_name=region)
    ec2, s3 = sess.client("ec2"), sess.client("s3")

    ami = ec2.describe_images()["Images"][0]["ImageId"]
    ec2.run_instances(ImageId=ami, InstanceType="t3.micro", MinCount=1, MaxCount=1)
    vol = ec2.create_volume(AvailabilityZone=f"{region}a", Size=1, VolumeType="gp3")["VolumeId"]
    ec2.allocate_address(Domain="vpc")
    s3.create_bucket(Bucket="lab-bucket", CreateBucketConfiguration={"LocationConstraint": region})
    s3.create_multipart_upload(Bucket="lab-bucket", Key="big")

    snap = collect(sess, region, days=14)
    assert snap.meta.source == "aws" and snap.meta.account.startswith("********")
    assert len(snap.instances) == 1 and snap.instances[0].type == "t3.micro"
    assert any(v.id == vol and v.state == "available" for v in snap.volumes)
    assert snap.addresses[0].associated_with is None
    assert snap.buckets[0].name == "lab-bucket" and len(snap.buckets[0].incomplete_uploads) == 1
