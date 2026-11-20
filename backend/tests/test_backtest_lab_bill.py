from app.analyzer import analyze
from app.billcheck import compare
from app.lab import score
from app.models import Address, Instance, Volume
from conftest import ago, flat_metrics, make_snapshot
from load_bill import aggregate, normalize


def inst(iid, itype="m5.xlarge"):
    return Instance(id=iid, type=itype, state="running", launch_time=ago(100))


# --- backtest -----------------------------------------------------------------

def test_steady_quiet_instance_backtest_holds_up():
    r = analyze(make_snapshot(instances=[inst("i-1")], metrics={"i-1": flat_metrics(8, peak=25)}))
    f = r["findings"][0]
    assert f["backtest"]["verdict"] == "Held up" and f["status"] == "active"


def test_new_nightly_job_blocks_the_advice():
    # quiet week 1, then 2 hours at 60% every night in week 2 (only ~4% of all hours,
    # so the p95 rule misses it - the backtest must catch it)
    spikes = {h: 60.0 for h in range(7 * 24, 14 * 24) if h % 24 in (1, 2)}
    r = analyze(make_snapshot(instances=[inst("i-1")],
                              metrics={"i-1": flat_metrics(6, peak=15, spikes=spikes)}))
    f = r["findings"][0]
    assert f["rule_id"] == "ec2-rightsize"
    assert f["backtest"]["verdict"] == "Would have hurt"
    assert f["status"] == "blocked"
    assert r["summary"]["potential_savings"] == 0      # blocked advice is not counted


def test_idle_instance_that_wakes_up_is_blocked():
    spikes = {h: 40.0 for h in range(8 * 24, 14 * 24, 3)}
    r = analyze(make_snapshot(instances=[inst("i-1", "t3.micro")],
                              metrics={"i-1": flat_metrics(0.3, spikes=spikes)}))
    bt = r["backtests"][0]
    assert bt["advice_week1"].startswith("Stop") and bt["verdict"] == "Would have hurt"


def test_backtest_needs_ten_days():
    r = analyze(make_snapshot(instances=[inst("i-1")], metrics={"i-1": flat_metrics(8, peak=25, hours=200)}))
    assert r["backtests"] == []


# --- lab scoring -----------------------------------------------------------------

def test_lab_precision_and_recall():
    findings = [
        {"resource_id": "w1", "rule_id": "ebs-unattached", "status": "active", "title": ""},
        {"resource_id": "w2", "rule_id": "ec2-rightsize", "status": "active", "title": ""},  # wrong rule
        {"resource_id": "d1", "rule_id": "ec2-idle", "status": "active", "title": ""},       # decoy hit
        {"resource_id": "d2", "rule_id": "ec2-rightsize", "status": "active", "title": ""},  # allowed
        {"resource_id": "d3", "rule_id": "ec2-idle", "status": "blocked", "title": ""},      # not advice
        {"resource_id": "x", "rule_id": "eip-idle", "status": "active", "title": ""},        # outside lab
    ]
    manifest = {"items": [
        {"resource_id": "w1", "role": "waste", "expected_rule": "ebs-unattached"},
        {"resource_id": "w2", "role": "waste", "expected_rule": "ec2-idle"},
        {"resource_id": "d1", "role": "decoy", "expected_rule": None},
        {"resource_id": "d2", "role": "decoy", "expected_rule": None, "must_not": ["ec2-idle"]},
        {"resource_id": "d3", "role": "decoy", "expected_rule": None},
    ]}
    s = score(manifest, findings)
    assert s["counts"] == {"TP": 1, "FN": 1, "FP": 1, "TN": 2}
    assert s["precision"] == 0.5 and s["recall"] == 0.5
    assert [o["resource_id"] for o in s["other_findings"]] == ["x"]


# --- bill check -----------------------------------------------------------------

def test_bill_check_compares_rates_and_flags_differences(pb):
    s = make_snapshot(volumes=[Volume(id="vol-1", type="gp3", size_gb=100, state="available",
                                      create_time=ago(30))],
                      addresses=[Address(allocation_id="eipalloc-1", public_ip="3.3.3.3")])
    vol_hourly = 100 * pb.get("ebs_gp3_gb_month") / 730
    bill = {"resources": {
        "vol-1": {"cost": vol_hourly * 48, "usage_hours": 48,
                  "usage_types": {"APS3-EBS:VolumeUsage.gp3": vol_hourly * 48}},
        "3.3.3.3": {"cost": 0.0, "usage_hours": 48, "usage_types": {"APS3-PublicIPv4:IdleAddress": 0.0}},
    }}
    out = compare(s, bill, pb)
    rows = {r["resource_id"]: r for r in out["rows"]}
    assert abs(rows["vol-1"]["error_pct"]) < 0.1
    assert rows["eipalloc-1"]["error_pct"] is None        # $0 billed -> explained, not divided by 0


def test_load_bill_aggregates_usage_and_skips_credits():
    rows = [
        {"line_item_line_item_type": "Usage", "line_item_resource_id":
         "arn:aws:ec2:ap-south-1:1:snapshot/snap-1", "line_item_unblended_cost": "0.01",
         "line_item_usage_type": "APS3-EBS:SnapshotUsage", "line_item_usage_start_date": "2026-11-01T00:00:00Z"},
        {"line_item_line_item_type": "Usage", "line_item_resource_id":
         "arn:aws:ec2:ap-south-1:1:snapshot/snap-1", "line_item_unblended_cost": "0.01",
         "line_item_usage_type": "APS3-EBS:SnapshotUsage", "line_item_usage_start_date": "2026-11-01T01:00:00Z"},
        {"line_item_line_item_type": "Credit", "line_item_resource_id": "snap-1",
         "line_item_unblended_cost": "-0.02", "line_item_usage_type": "",
         "line_item_usage_start_date": "2026-11-01T00:00:00Z"},
    ]
    out = aggregate(rows)
    assert normalize("arn:aws:s3:::bucket/x") == "x"
    assert out["resources"]["snap-1"]["cost"] == 0.02
    assert out["resources"]["snap-1"]["usage_hours"] == 2
