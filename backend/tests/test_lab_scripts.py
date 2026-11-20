"""End-to-end on a FAKE AWS (moto): plant the lab -> collect -> tear down.

Proves the scripts that touch a real account do what they claim, without
spending anything.
"""

import json
import sys

import pytest

moto = pytest.importorskip("moto")


@moto.mock_aws
def test_plant_collect_teardown(tmp_path, monkeypatch):
    import boto3

    import collect_snapshot
    import lab_plant
    import lab_teardown

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setattr(lab_plant, "LAB_DIR", tmp_path)

    monkeypatch.setattr(sys, "argv", ["lab_plant", "--yes"])
    lab_plant.main()
    manifest = json.loads(next(tmp_path.glob("manifest-*.json")).read_text())
    roles = [i["role"] for i in manifest["items"]]
    assert roles.count("waste") == 6 and roles.count("decoy") == 5

    sess = boto3.Session(region_name="ap-south-1")
    snap = collect_snapshot.collect(sess, "ap-south-1", 14)
    ids = {i["resource_id"] for i in manifest["items"]}
    states = {i.id: i.state for i in snap.instances if i.id in ids}
    assert sorted(states.values()) == ["running", "running", "running", "stopped"]
    assert any(v.id in ids and v.state == "available" for v in snap.volumes)
    assert any(s.id in ids and not s.volume_exists for s in snap.snapshots)

    monkeypatch.setattr(sys, "argv", ["lab_teardown", "--lab", manifest["lab_id"], "--yes"])
    lab_teardown.main()
    after = collect_snapshot.collect(sess, "ap-south-1", 14)
    left = ({i.id for i in after.instances} | {v.id for v in after.volumes}
            | {s.id for s in after.snapshots} | {a.allocation_id for a in after.addresses}
            | {b.name for b in after.buckets})
    assert not (left & ids), f"teardown left lab resources behind: {left & ids}"
