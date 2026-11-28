"""Cost checker."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.estimate import Server, Setup, check  # noqa: E402
from app.prices import load_prices  # noqa: E402

P = load_prices("ap-south-1")


def test_one_small_server_with_credits():
    r = check(Setup(servers=[Server(instance_type="t3.micro", disk_gb=8, disk_type="gp3")], credits_usd=100))
    expected = (P.instance_hourly("t3.micro") * 730 + 8 * P.get("ebs_gp3_gb_month")
                + P.get("public_ipv4_inuse_hour") * 730)
    assert r["monthly_total"] == pytest.approx(expected, abs=0.02)
    assert r["credits_last_days"] == round(100 / (r["monthly_total"] / (730 / 24)))


def test_fewer_hours_cost_less():
    always = check(Setup(servers=[Server(public_ip=False, disk_gb=0)]))
    weekdays = check(Setup(servers=[Server(public_ip=False, disk_gb=0, hours_per_day=12, days_per_week=5)]))
    assert weekdays["monthly_total"] == pytest.approx(always["monthly_total"] * 60 / 168, abs=0.02)


def test_tips_for_gp2_always_on_and_nat():
    r = check(Setup(servers=[Server(disk_gb=100, disk_type="gp2")], nat_gateways=1))
    tips = " ".join(t["tip"] for t in r["tips"])
    assert "gp3" in tips and "night" in tips and "NAT" in tips


def test_regions_are_compared_cheapest_first():
    r = check(Setup())
    prices = [x["monthly"] for x in r["regions"]]
    assert prices == sorted(prices) and len(prices) > 1


def test_unknown_instance_type_is_an_error():
    with pytest.raises(ValueError):
        check(Setup(servers=[Server(instance_type="x9.huge")]))
