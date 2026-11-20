import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import EbsSnapshot, ElasticIp, Instance, Metrics, Scan, Volume  # noqa: E402
from app.prices import load_prices  # noqa: E402
from app.rules import build_report, volume_cost  # noqa: E402

NOW = datetime(2026, 11, 21, tzinfo=timezone.utc)
P = load_prices("ap-south-1")


def scan(**parts):
    return Scan(id="t", source="sample", account="x", region="ap-south-1", scanned_at=NOW, **parts)


def rules_hit(s):
    return {(f["resource_id"], f["rule"]) for f in build_report(s, P)["findings"]}


def vol(vid, state="available", **kw):
    return Volume(id=vid, type="gp3", size_gb=10, state=state, created=NOW - timedelta(days=3), **kw)


def server(iid, state="running", **kw):
    return Instance(id=iid, type="t3.micro", state=state, launch_time=NOW - timedelta(days=30), **kw)


def test_unattached_volume_found_attached_ignored():
    hits = rules_hit(scan(volumes=[vol("v-free"), vol("v-used", state="in-use")]))
    assert hits == {("v-free", "Unattached EBS volume")}


def test_gp3_only_charges_iops_above_free_3000():
    base, calc, _ = volume_cost(vol("a", iops=3000, throughput=125), P)
    extra, calc2, _ = volume_cost(vol("b", iops=4000, throughput=125), P)
    assert base == pytest.approx(10 * P.get("ebs_gp3_gb_month"))
    assert extra - base == pytest.approx(1000 * P.get("ebs_gp3_iops_month"))
    assert len(calc) == 1 and len(calc2) == 2


def test_unused_elastic_ip():
    hits = rules_hit(scan(elastic_ips=[ElasticIp(allocation_id="free", public_ip="1.1.1.1"),
                                       ElasticIp(allocation_id="used", public_ip="2.2.2.2", attached_to="i-1")]))
    assert hits == {("free", "Unused Elastic IP")}


def test_stopped_instance_charged_for_its_disk():
    s = scan(instances=[server("i-1", state="stopped", volume_ids=["v-root"])],
             volumes=[vol("v-root", state="in-use", attached_to="i-1")])
    f = build_report(s, P)["findings"][0]
    assert f["rule"] == "Stopped instance"
    assert f["monthly_cost"] == round(10 * P.get("ebs_gp3_gb_month"), 2)


def test_orphaned_snapshot_but_not_when_disk_exists_or_ami_uses_it():
    snaps = [EbsSnapshot(id="gone", volume_id="v-x", volume_exists=False, size_gb=5, created=NOW),
             EbsSnapshot(id="ok", volume_id="v-y", volume_exists=True, size_gb=5, created=NOW),
             EbsSnapshot(id="ami", volume_id="v-z", volume_exists=False, used_by_ami=True, size_gb=5, created=NOW)]
    assert rules_hit(scan(snapshots=snaps)) == {("gone", "Orphaned snapshot")}


def week(cpu, net_bytes_per_hour, hours=14 * 24):
    return Metrics(cpu=[cpu] * hours, network_in=[net_bytes_per_hour] * hours)


def test_idle_instance_needs_low_cpu_and_low_network():
    s = scan(instances=[server("idle"), server("busy-net"), server("busy-cpu")],
             metrics={"idle": week(0.5, 1000), "busy-net": week(0.5, 200 * 1024 * 3600),
                      "busy-cpu": week(40, 1000)})
    assert rules_hit(s) == {("idle", "Idle instance")}


def test_idle_rule_waits_for_7_days_and_says_so():
    s = scan(instances=[server("new")], metrics={"new": week(0.5, 1000, hours=48)})
    report = build_report(s, P)
    assert report["findings"] == []
    assert "only 48 hours" in report["notes"][0]


def test_missing_hours_are_not_counted_as_zero():
    m = week(0.5, 1000)
    m.cpu = [None if k % 3 else v for k, v in enumerate(m.cpu)]   # only 1/3 of hours present
    report = build_report(scan(instances=[server("gappy")], metrics={"gappy": m}), P)
    assert report["findings"] == [] and report["notes"]


def test_without_network_data_idle_is_judged_on_cpu_and_says_so():
    s = scan(instances=[server("cpu-only")], metrics={"cpu-only": Metrics(cpu=[0.2] * (14 * 24))})
    f = build_report(s, P)["findings"][0]
    assert f["rule"] == "Idle instance"
    assert "not recorded" in f["evidence"]["Average network in"]


def test_every_finding_has_evidence_price_and_fix():
    report = build_report(scan(volumes=[vol("v")], elastic_ips=[ElasticIp(allocation_id="e", public_ip="1.1.1.1")]), P)
    assert report["monthly_waste"] > 0
    for f in report["findings"]:
        assert f["evidence"] and f["calculation"] and f["prices_used"] and f["fix"]
