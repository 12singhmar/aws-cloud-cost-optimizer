import pytest

from app.costs import address_cost, volume_cost
from app.models import Address, Volume
from app.pricing import PriceNotFound
from app.stats import percentile
from conftest import ago


def test_prices_are_real_and_have_skus(pb):
    m5 = pb.instance("m5.large")
    assert m5["vcpu"] == 2 and m5["usd_per_hour"] > 0
    assert len(m5["sku"]) >= 10            # every price is traceable to an AWS SKU
    assert pb.ref("ebs_gp3_gb_month").unit == "GB-Mo"


def test_unknown_price_raises_instead_of_guessing(pb):
    with pytest.raises(PriceNotFound):
        pb.instance("x9.mega")
    with pytest.raises(PriceNotFound):
        pb.get("no_such_price")


def test_gp3_cost_includes_only_iops_and_throughput_above_free_baseline(pb):
    base = Volume(id="v", type="gp3", size_gb=100, iops=3000, throughput=125,
                  state="available", create_time=ago(1))
    extra = base.model_copy(update={"iops": 4000, "throughput": 225})
    c_base, steps_base, _ = volume_cost(base, pb)
    c_extra, steps_extra, _ = volume_cost(extra, pb)
    assert c_base == pytest.approx(100 * pb.get("ebs_gp3_gb_month"), abs=1e-4)
    assert len(steps_base) == 1            # no extra lines when within free baseline
    expected = (c_base + 1000 * pb.get("ebs_gp3_iops_month") + 100 * pb.get("ebs_gp3_mbps_month"))
    assert c_extra == pytest.approx(expected, abs=1e-4)
    assert len(steps_extra) == 3


def test_idle_ip_costs_730_hours(pb):
    usd, _, refs = address_cost(Address(allocation_id="a", public_ip="1.2.3.4"), pb)
    assert usd == pytest.approx(pb.get("public_ipv4_idle_hour") * 730)
    assert refs[0].key == "public_ipv4_idle_hour"


def test_percentile_nearest_rank():
    data = list(range(1, 101))
    assert percentile(data, 95) == 95
    assert percentile(data, 100) == 100
    assert percentile([], 95) == 0.0
