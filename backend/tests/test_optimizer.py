import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.optimizer import WEEKS_PER_MONTH, Workload, fits, optimize  # noqa: E402
from app.prices import HOURS_PER_MONTH, load_prices  # noqa: E402

P = load_prices("ap-south-1")


def step(result, lever):
    return next(s for s in result["steps"] if s["lever"] == lever)


def test_baseline_is_hours_times_price():
    r = optimize(Workload(instance_type="m5.large", running_hours_per_week=168, needed_hours_per_week=168))
    assert r["baseline_monthly"] == round(P.instance_hourly("m5.large") * 168 * WEEKS_PER_MONTH, 2)


def test_no_cpu_data_means_no_rightsizing():
    r = optimize(Workload(instance_type="m5.xlarge"))
    assert step(r, "rightsize")["applied"] is False


def test_rightsize_picks_cheapest_type_with_enough_vcpu_and_memory():
    r = optimize(Workload(instance_type="m5.xlarge", peak_cpu=25, avg_cpu=8))
    chosen = P.instances[r["plan"]["instance_type"]]
    need_vcpu = 4 * 25 / 70
    assert chosen["vcpu"] >= need_vcpu and chosen["memory_gib"] >= 16
    assert not chosen["arm"]                           # ARM not allowed by default
    cheaper_fits = [c for c in r["candidates"] if not c["arm"] and c["hourly"] < chosen["usd_per_hour"]]
    assert cheaper_fits == []                          # nothing cheaper fits


def test_busy_server_is_not_shrunk_and_gets_a_warning():
    r = optimize(Workload(instance_type="m5.large", peak_cpu=95, avg_cpu=60))
    assert r["plan"]["instance_type"] != "m5.large" or step(r, "rightsize")["applied"] is False
    assert any("too small" in w for w in r["warnings"])


def test_burstable_checks_cpu_credit_baseline():
    # t3a.large: 2 vCPU, baseline 30% -> safe up to 24% average (80% margin)
    info = P.instances["t3a.large"]
    ok, _ = fits(info, "t3a.large", need_vcpu=1, need_mem=4, avg_cpu=20, cur_vcpu=2, arm_ok=False)
    too_busy, why = fits(info, "t3a.large", need_vcpu=1, need_mem=4, avg_cpu=45, cur_vcpu=2, arm_ok=False)
    unknown, _ = fits(info, "t3a.large", need_vcpu=1, need_mem=4, avg_cpu=None, cur_vcpu=2, arm_ok=False)
    assert ok and not too_busy and "baseline" in why and not unknown


def test_arm_only_when_allowed():
    no = optimize(Workload(instance_type="m5.xlarge", peak_cpu=25, avg_cpu=8))
    yes = optimize(Workload(instance_type="m5.xlarge", peak_cpu=25, avg_cpu=8, arm_ok=True))
    assert not P.instances[no["plan"]["instance_type"]]["arm"]
    assert yes["optimized_monthly"] <= no["optimized_monthly"]


def test_schedule_beats_reservation_for_part_time_server():
    r = optimize(Workload(instance_type="m5.large", needed_hours_per_week=45, commit_years=1))
    assert r["plan"]["pricing"].startswith("On-demand") and r["plan"]["hours_per_week"] == 45


def test_reservation_beats_on_demand_for_always_on_server():
    r = optimize(Workload(instance_type="m5.large", needed_hours_per_week=168, commit_years=3))
    assert "reservation" in r["plan"]["pricing"]
    ri = P.instances["m5.large"]["reserved"]["3yr_all_upfront"]
    assert r["optimized_monthly"] == pytest.approx(ri["upfront"] / 36 + ri["hourly"] * HOURS_PER_MONTH, abs=0.01)


def test_no_reservation_without_commitment():
    r = optimize(Workload(instance_type="m5.large", commit_years=0))
    assert r["plan"]["pricing"].startswith("On-demand")


def test_gp2_to_gp3_keeps_performance_for_big_disks():
    r = optimize(Workload(instance_type="m5.large", storage_gb=6000, storage_type="gp2"))
    s = step(r, "storage")
    assert s["applied"] and "13,000 IOPS" in s["details"][1]


def test_region_only_moves_when_allowed():
    stay = optimize(Workload(instance_type="m5.large", region="ap-southeast-1"))
    move = optimize(Workload(instance_type="m5.large", region="ap-southeast-1", region_flexible=True))
    assert stay["plan"]["region"] == "ap-southeast-1"
    assert move["optimized_monthly"] <= stay["optimized_monthly"]


def test_savings_add_up():
    r = optimize(Workload(instance_type="r5.xlarge", peak_cpu=20, avg_cpu=8, needed_hours_per_week=60,
                          storage_gb=500, arm_ok=True, commit_years=1, region_flexible=True))
    total = sum(s["saving"] for s in r["steps"])
    assert total == pytest.approx(r["saving_monthly"], abs=0.05)
