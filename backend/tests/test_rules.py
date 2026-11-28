"""Waste rules and cost formulas, on small hand-made scans."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.costs import monthly_cost  # noqa: E402
from app.models import Metrics, Resource, Scan  # noqa: E402
from app.prices import load_prices  # noqa: E402
from app.rules import find_waste, report  # noqa: E402

NOW = datetime(2026, 11, 29, tzinfo=timezone.utc)
P = load_prices("ap-south-1")


def scan(*resources, metrics=None):
    return Scan(id="t", account="x", scanned_at=NOW, regions=["ap-south-1"],
                resources=list(resources), metrics=metrics or {})


def res(kind, rid, state="", **info):
    return Resource(kind=kind, region="ap-south-1", id=rid, state=state, created=NOW - timedelta(days=10), info=info)


def disk(rid, state="available", gb=10, vtype="gp3", attached=None):
    return res("volume", rid, state, size_gb=gb, type=vtype, iops=3000, throughput=125, attached_to=attached)


def server(rid, state="running", itype="t3.medium", volumes=()):
    return res("instance", rid, state, type=itype, public_ip=None, stopped_since=None, volume_ids=list(volumes))


def rules_found(s):
    return {(f.resource_id, f.rule) for f in find_waste(s)[0]}


def test_spare_disk_found_attached_disk_ignored():
    s = scan(disk("v-spare"), disk("v-used", state="in-use", attached="i-1"))
    assert rules_found(s) == {("v-spare", "Unattached disk")}


def test_disk_cost_is_size_times_price():
    cost, _ = monthly_cost(disk("v", gb=50), P)
    assert cost == pytest.approx(50 * P.get("ebs_gp3_gb_month"))


def test_unused_ip_found_used_ip_ignored():
    s = scan(res("elastic_ip", "free", public_ip="1.1.1.1", attached_to=None),
             res("elastic_ip", "used", public_ip="2.2.2.2", attached_to="i-1"))
    f = find_waste(s)[0]
    assert [x.resource_id for x in f] == ["free"]
    assert f[0].monthly_cost == round(P.get("public_ipv4_idle_hour") * 730, 2)    # $3.65


def test_stopped_server_is_charged_for_its_disks():
    s = scan(server("i-1", state="stopped", volumes=["v-root"]), disk("v-root", state="in-use", gb=20, attached="i-1"))
    f = [x for x in find_waste(s)[0] if x.rule == "Stopped server"][0]
    assert f.monthly_cost == round(20 * P.get("ebs_gp3_gb_month"), 2)


def test_old_snapshot_only_when_disk_is_gone_and_not_used_by_an_image():
    s = scan(res("snapshot", "gone", size_gb=5, volume_id="v-x", volume_exists=False, used_by_ami=False),
             res("snapshot", "ok", size_gb=5, volume_id="v-y", volume_exists=True, used_by_ami=False),
             res("snapshot", "ami", size_gb=5, volume_id="v-z", volume_exists=False, used_by_ami=True))
    assert rules_found(s) == {("gone", "Old snapshot")}


def test_nat_gateway_with_no_traffic_is_idle():
    s = scan(res("nat_gateway", "nat-idle", "available", bytes_sent_7d=0),
             res("nat_gateway", "nat-busy", "available", bytes_sent_7d=5e9))
    f = find_waste(s)[0]
    assert [x.resource_id for x in f] == ["nat-idle"]
    assert f[0].monthly_cost == round(P.get("nat_gateway_hour") * 730, 2)


def test_load_balancer_with_no_servers_is_flagged():
    s = scan(res("load_balancer", "lb-empty", "active", lb_type="application", targets=0),
             res("load_balancer", "lb-used", "active", lb_type="application", targets=2))
    assert rules_found(s) == {("lb-empty", "Empty load balancer")}


def week_of_cpu(avg, peak, hours=7 * 24):
    return Metrics(cpu_avg=[avg] * hours, cpu_max=[peak] * hours)


def test_idle_and_oversized_servers():
    s = scan(server("i-idle"), server("i-big"), server("i-busy"),
             metrics={"i-idle": week_of_cpu(0.5, 2), "i-big": week_of_cpu(10, 25), "i-busy": week_of_cpu(50, 90)})
    assert rules_found(s) == {("i-idle", "Idle server"), ("i-big", "Oversized server")}
    big = [x for x in find_waste(s)[0] if x.resource_id == "i-big"][0]
    expected = (P.instance_hourly("t3.medium") - P.instance_hourly("t3.small")) * 730
    assert big.monthly_cost == round(expected, 2)


def test_cpu_rules_wait_for_a_full_week_and_say_so():
    s = scan(server("i-new"), metrics={"i-new": week_of_cpu(0.5, 2, hours=48)})
    findings, notes = find_waste(s)
    assert findings == [] and "48 hours" in notes[0]


def test_report_totals_add_up():
    s = scan(disk("v1", gb=10), disk("v2", gb=30), res("elastic_ip", "ip", public_ip="1.1.1.1", attached_to=None))
    r = report(s)
    assert r["monthly_total"] == pytest.approx(sum(x["monthly_cost"] for x in r["inventory"]), abs=0.02)
    assert r["monthly_waste"] == pytest.approx(r["monthly_total"], abs=0.02)   # all three are waste
