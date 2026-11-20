"""Each rule: one case that must fire, and the cases that must NOT fire."""

from app.analyzer import analyze, strip_lab_tags
from app.models import Address, Bucket, EbsSnapshot, IncompleteUpload, Instance, Volume
from conftest import ago, flat_metrics, make_snapshot


def run(**parts):
    return analyze(make_snapshot(**parts))


def rules_for(result, resource_id):
    return [f["rule_id"] for f in result["findings"]
            if f["resource_id"] == resource_id and f["status"] == "active"]


def inst(iid="i-1", itype="m5.xlarge", state="running", **kw):
    return Instance(id=iid, type=itype, state=state, launch_time=ago(100), **kw)


# --- idle -------------------------------------------------------------------

def test_idle_instance_is_flagged():
    r = run(instances=[inst(itype="t3.micro")], metrics={"i-1": flat_metrics(0.5)})
    assert rules_for(r, "i-1") == ["ec2-idle"]


def test_low_cpu_but_busy_network_is_not_idle():
    r = run(instances=[inst(itype="t3.nano")], metrics={"i-1": flat_metrics(0.5, net_kbps=200)})
    assert "ec2-idle" not in rules_for(r, "i-1")


def test_too_little_data_gives_notice_not_finding():
    r = run(instances=[inst()], metrics={"i-1": flat_metrics(0.5, hours=100)})
    assert rules_for(r, "i-1") == []
    assert any(n["resource_id"] == "i-1" for n in r["notices"])


def test_missing_metrics_are_not_treated_as_zero():
    m = flat_metrics(0.5)
    m.cpu_avg = [None if k % 2 else v for k, v in enumerate(m.cpu_avg)]  # 50% coverage
    r = run(instances=[inst()], metrics={"i-1": m})
    assert rules_for(r, "i-1") == []


def test_young_instance_leading_gap_does_not_count_as_missing():
    m = flat_metrics(0.5)
    for k in range(96):             # instance launched 4 days into the 14-day window
        m.cpu_avg[k] = m.cpu_max[k] = None
    r = run(instances=[inst(itype="t3.micro")], metrics={"i-1": m})
    assert rules_for(r, "i-1") == ["ec2-idle"]


# --- rightsizing --------------------------------------------------------------

def test_quiet_m5_is_downsized_with_correct_saving(pb):
    r = run(instances=[inst()], metrics={"i-1": flat_metrics(8, peak=25)})
    f = next(f for f in r["findings"] if f["resource_id"] == "i-1")
    assert f["rule_id"] == "ec2-rightsize" and "m5.large" in f["title"]
    assert f["monthly_savings"] == round(pb.instance_monthly("m5.xlarge") - pb.instance_monthly("m5.large"), 2)


def test_peaky_instance_is_not_downsized():
    # p95 of hourly max = 45% -> would be 90% after halving -> unsafe
    r = run(instances=[inst()], metrics={"i-1": flat_metrics(8, peak=45)})
    assert rules_for(r, "i-1") == []


def test_boundary_just_under_40_percent_is_downsized():
    r = run(instances=[inst()], metrics={"i-1": flat_metrics(8, peak=39.9)})
    assert rules_for(r, "i-1") == ["ec2-rightsize"]


def test_smallest_size_has_nothing_to_downsize_to():
    r = run(instances=[inst(itype="m5.large")], metrics={"i-1": flat_metrics(8, peak=20)})
    assert rules_for(r, "i-1") == []


def test_burstable_respects_cpu_credit_baseline():
    # t3.small -> t3.micro baseline 10%, x0.8 margin = 8%. Avg 9% is too high.
    r = run(instances=[inst(itype="t3.small")], metrics={"i-1": flat_metrics(9, peak=20)})
    assert rules_for(r, "i-1") == []
    r = run(instances=[inst(itype="t3.small")], metrics={"i-1": flat_metrics(5, peak=20)})
    assert rules_for(r, "i-1") == ["ec2-rightsize"]


def test_idle_and_rightsize_never_both_fire():
    r = run(instances=[inst()], metrics={"i-1": flat_metrics(0.5)})
    assert rules_for(r, "i-1") == ["ec2-idle"]


# --- storage / network -----------------------------------------------------------

def vol(vid="vol-1", state="available", days=30, **kw):
    return Volume(id=vid, type="gp3", size_gb=10, state=state, create_time=ago(days), **kw)


def test_unattached_volume_flagged_only_after_7_days():
    r = run(volumes=[vol(), vol("vol-new", days=2), vol("vol-used", state="in-use")])
    assert rules_for(r, "vol-1") == ["ebs-unattached"]
    assert rules_for(r, "vol-new") == []
    assert rules_for(r, "vol-used") == []


def test_only_unassociated_elastic_ip_is_flagged():
    r = run(addresses=[Address(allocation_id="a-idle", public_ip="1.1.1.1"),
                       Address(allocation_id="a-used", public_ip="2.2.2.2", associated_with="i-9")])
    assert rules_for(r, "a-idle") == ["eip-idle"]
    assert rules_for(r, "a-used") == []


def test_stopped_instance_needs_7_days_and_disks():
    r = run(instances=[inst("i-old", "t3.small", "stopped", state_since=ago(20), volume_ids=["vol-r"]),
                       inst("i-recent", "t3.small", "stopped", state_since=ago(2), volume_ids=["vol-r"])],
            volumes=[vol("vol-r", state="in-use")])
    assert rules_for(r, "i-old") == ["ec2-stopped"]
    assert rules_for(r, "i-recent") == []


def test_orphan_snapshot_only_when_volume_gone():
    r = run(snapshots=[
        EbsSnapshot(id="snap-gone", volume_id="vol-x", volume_exists=False, size_gb=5, start_time=ago(30)),
        EbsSnapshot(id="snap-ok", volume_id="vol-y", volume_exists=True, size_gb=5, start_time=ago(30)),
        EbsSnapshot(id="snap-ami", volume_id="vol-z", volume_exists=False, used_by_ami=True,
                    size_gb=5, start_time=ago(30))])
    assert rules_for(r, "snap-gone") == ["snapshot-orphan"]
    assert rules_for(r, "snap-ok") == []
    assert rules_for(r, "snap-ami") == []     # backing an AMI: deleting would break it


def test_old_incomplete_uploads_flagged_and_lifecycle_rule_has_no_made_up_saving():
    up = IncompleteUpload(key="k", initiated=ago(10), size_bytes=2**30)
    r = run(buckets=[Bucket(name="b1", incomplete_uploads=[up]),
                     Bucket(name="big", size_gb=100)])
    assert rules_for(r, "b1") == ["s3-incomplete-uploads"]
    lc = next(f for f in r["findings"] if f["rule_id"] == "s3-no-lifecycle")
    assert lc["monthly_savings"] is None


# --- fairness -------------------------------------------------------------------

def test_lab_tags_are_hidden_from_the_detector():
    s = make_snapshot(volumes=[vol(tags={"ccx-lab": "lab-1", "Name": "x"})])
    clean = strip_lab_tags(s)
    assert clean.volumes[0].tags == {"Name": "x"}
    assert s.volumes[0].tags["ccx-lab"] == "lab-1"     # original not modified


def test_every_finding_is_explained():
    r = run(instances=[inst()], metrics={"i-1": flat_metrics(8, peak=25)},
            volumes=[vol()], addresses=[Address(allocation_id="a", public_ip="1.1.1.1")])
    for f in r["findings"]:
        assert f["evidence"] and f["calculation"] and f["prices_used"] and f["fix_steps"]
        assert all(p["sku"] for p in f["prices_used"])
