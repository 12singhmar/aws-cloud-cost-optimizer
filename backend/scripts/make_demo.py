"""Build the DEMO account (synthetic, clearly labelled) so the app works offline.

Why have a demo at all? So the app can be shown and tested without AWS keys
or internet. Every page labels it "Demo data". Real results come from
scripts/collect_snapshot.py on your own account.

Each demo resource is a small story the rules must handle correctly:
  web      busy m5.xlarge                      -> leave alone
  api      quiet m5.xlarge                     -> downsize to m5.large
  batch    quiet week 1, nightly job in week 2 -> no advice (backtest shows why)
  idle     t3.nano doing nothing               -> stop it
  proxy    t3.nano, ~0% CPU but busy network   -> leave alone (decoy for naive tools)
  old      stopped for 20 days                 -> clean up
  + disks, IPs, snapshots and S3 buckets with the same waste/decoy idea.

Writes: data/snapshots/demo.json, data/labs/demo.json, data/bills/demo.json
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import BILL_DIR, HOURS_PER_MONTH, LAB_DIR  # noqa: E402
from app.costs import (address_cost, bucket_cost, instance_cost, snapshot_cost,  # noqa: E402
                       volume_cost)
from app.models import (Address, Bucket, EbsSnapshot, IncompleteUpload, Instance,  # noqa: E402
                        InstanceMetrics, Snapshot, SnapshotMeta, Volume)
from app.pricing import load_pricebook  # noqa: E402
from app.store import save_snapshot  # noqa: E402

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
HOURS = 14 * 24
rng = random.Random(7)


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def series(base: float, noise: float, spikes: dict[int, float] | None = None,
           peak_extra: float = 0.0) -> tuple[list[float], list[float]]:
    """Hourly (avg, max) CPU with a gentle daily curve + optional spikes."""
    avg, mx = [], []
    for h in range(HOURS):
        hour_of_day = h % 24
        daily = 1 + 0.5 * (1 if 9 <= hour_of_day <= 18 else -0.3)
        a = max(0.05, base * daily + rng.uniform(-noise, noise))
        if spikes and h in spikes:
            a = spikes[h]
        avg.append(round(a, 2))
        mx.append(round(min(100.0, a * rng.uniform(1.3, 1.8) + peak_extra), 2))
    return avg, mx


def net(kbps: float) -> list[float]:
    return [round(max(0.0, kbps * 1024 * 3600 * rng.uniform(0.7, 1.3)), 0) for _ in range(HOURS)]


def build() -> tuple[Snapshot, dict, dict]:
    start = NOW - timedelta(hours=HOURS)
    web_avg, web_max = series(32, 6, peak_extra=8)
    api_avg, api_max = series(7, 1.5)
    # batch: quiet for 7 days, then a nightly 2-hour job at ~55% CPU
    batch_spikes = {h: 55.0 + rng.uniform(-5, 5) for h in range(7 * 24, HOURS) if h % 24 in (1, 2)}
    batch_avg, batch_max = series(6, 1.5, spikes=batch_spikes)
    idle_avg, idle_max = series(0.4, 0.2)
    proxy_avg, proxy_max = series(0.6, 0.3)

    instances = [
        Instance(id="i-0web00000000demo", name="web-frontend", type="m5.xlarge", state="running",
                 launch_time=ago(200), volume_ids=["vol-0webroot0000demo"], tags={"Name": "web-frontend"}),
        Instance(id="i-0api00000000demo", name="internal-api", type="m5.xlarge", state="running",
                 launch_time=ago(150), volume_ids=["vol-0apiroot0000demo"], public_ip="13.200.10.21",
                 tags={"Name": "internal-api", "team": "backend"}),
        Instance(id="i-0batch000000demo", name="report-batch", type="m5.xlarge", state="running",
                 launch_time=ago(90), volume_ids=["vol-0batchroot00demo"], tags={"Name": "report-batch"}),
        Instance(id="i-0idle0000000demo", name="old-experiment", type="t3.nano", state="running",
                 launch_time=ago(60), volume_ids=["vol-0idleroot000demo"], public_ip="13.200.10.40",
                 tags={"Name": "old-experiment"}),
        Instance(id="i-0proxy000000demo", name="egress-proxy", type="t3.nano", state="running",
                 launch_time=ago(60), volume_ids=["vol-0proxyroot00demo"], public_ip="13.200.10.41",
                 tags={"Name": "egress-proxy"}),
        Instance(id="i-0old00000000demo", name="intern-project", type="t3.small", state="stopped",
                 launch_time=ago(120), state_since=ago(20), volume_ids=["vol-0oldroot0000demo"],
                 tags={"Name": "intern-project"}),
    ]
    metrics = {
        "i-0web00000000demo": InstanceMetrics(start=start, cpu_avg=web_avg, cpu_max=web_max, net_in_bytes=net(900)),
        "i-0api00000000demo": InstanceMetrics(start=start, cpu_avg=api_avg, cpu_max=api_max, net_in_bytes=net(120)),
        "i-0batch000000demo": InstanceMetrics(start=start, cpu_avg=batch_avg, cpu_max=batch_max, net_in_bytes=net(40)),
        "i-0idle0000000demo": InstanceMetrics(start=start, cpu_avg=idle_avg, cpu_max=idle_max, net_in_bytes=net(0.3)),
        "i-0proxy000000demo": InstanceMetrics(start=start, cpu_avg=proxy_avg, cpu_max=proxy_max, net_in_bytes=net(350)),
    }
    root = dict(type="gp3", size_gb=8, iops=3000, throughput=125, state="in-use")
    volumes = [
        Volume(id="vol-0webroot0000demo", create_time=ago(200), attached_to="i-0web00000000demo", **{**root, "size_gb": 50}),
        Volume(id="vol-0apiroot0000demo", create_time=ago(150), attached_to="i-0api00000000demo", **{**root, "size_gb": 30}),
        Volume(id="vol-0batchroot00demo", create_time=ago(90), attached_to="i-0batch000000demo", **{**root, "size_gb": 30}),
        Volume(id="vol-0idleroot000demo", create_time=ago(60), attached_to="i-0idle0000000demo", **root),
        Volume(id="vol-0proxyroot00demo", create_time=ago(60), attached_to="i-0proxy000000demo", **root),
        Volume(id="vol-0oldroot0000demo", create_time=ago(120), attached_to="i-0old00000000demo", **{**root, "size_gb": 20}),
        Volume(id="vol-0orphan00000demo", name="", type="gp3", size_gb=100, iops=6000, throughput=250,
               state="available", create_time=ago(40), tags={"Name": "db-migration-temp"}),
        Volume(id="vol-0fresh000000demo", type="gp3", size_gb=20, iops=3000, throughput=125,
               state="available", create_time=ago(2), tags={"Name": "migration-in-progress"}),
    ]
    addresses = [
        Address(allocation_id="eipalloc-0idle00demo", public_ip="13.200.10.99"),
        Address(allocation_id="eipalloc-0web000demo", public_ip="13.200.10.20",
                associated_with="i-0web00000000demo"),
    ]
    snapshots = [
        EbsSnapshot(id="snap-0orphan000demo", volume_id="vol-0deleted0000demo", volume_exists=False,
                    size_gb=40, start_time=ago(60), description="before upgrade"),
        EbsSnapshot(id="snap-0keep00000demo", volume_id="vol-0webroot0000demo", volume_exists=True,
                    size_gb=50, start_time=ago(10), description="weekly backup"),
    ]
    buckets = [
        Bucket(name="demo-app-logs", size_gb=120.0, has_lifecycle=False),
        Bucket(name="demo-uploads", size_gb=3.5, has_lifecycle=False, incomplete_uploads=[
            IncompleteUpload(key=f"videos/raw-{k}.mp4", initiated=ago(20 + k), size_bytes=800 * 2**20)
            for k in range(3)]),
        Bucket(name="demo-static-site", size_gb=0.4, has_lifecycle=True),
    ]
    snap = Snapshot(
        meta=SnapshotMeta(id="demo", source="demo", region="ap-south-1", account="DEMO",
                          collected_at=NOW, metric_days=14,
                          notes="Synthetic demo account. Not real AWS data."),
        instances=instances, volumes=volumes, addresses=addresses, snapshots=snapshots,
        buckets=buckets, metrics=metrics)

    W, D = "waste", "decoy"
    items = [
        ("i-0idle0000000demo", "EC2 instance", W, "ec2-idle", "Running, no CPU, no traffic"),
        ("i-0proxy000000demo", "EC2 instance", D, None, "Near-zero CPU but steady network: it is working"),
        ("i-0api00000000demo", "EC2 instance", W, "ec2-rightsize", "Uses a fraction of an m5.xlarge"),
        ("i-0batch000000demo", "EC2 instance", D, None, "Looks quiet, but runs a nightly job"),
        ("i-0old00000000demo", "EC2 instance", W, "ec2-stopped", "Stopped 20 days, disk still billed"),
        ("vol-0orphan00000demo", "EBS volume", W, "ebs-unattached", "Unattached for 40 days"),
        ("vol-0fresh000000demo", "EBS volume", D, None, "Unattached, but only 2 days old"),
        ("eipalloc-0idle00demo", "Elastic IP", W, "eip-idle", "Reserved, attached to nothing"),
        ("eipalloc-0web000demo", "Elastic IP", D, None, "Attached to a running server"),
        ("snap-0orphan000demo", "EBS snapshot", W, "snapshot-orphan", "Its volume was deleted"),
        ("snap-0keep00000demo", "EBS snapshot", D, None, "Backup of a disk that still exists"),
        ("demo-uploads", "S3 bucket", W, "s3-incomplete-uploads", "3 abandoned uploads, 2.3 GB hidden"),
        ("demo-static-site", "S3 bucket", D, None, "Small and has a lifecycle rule"),
    ]
    manifest = {"lab_id": "demo", "synthetic": True, "created_at": ago(40).isoformat(),
                "region": "ap-south-1",
                "items": [{"resource_id": r, "kind": k, "role": role, "expected_rule": rule, "why": why}
                          for r, k, role, rule, why in items]}

    # Synthetic bill: our own estimate with realistic, explained differences.
    pb = load_pricebook("ap-south-1")
    hours = 14 * 24
    period_start = (NOW - timedelta(hours=hours)).isoformat()

    def entry(monthly: float, usage: str, factor: float = 1.0) -> dict:
        cost = round(monthly / HOURS_PER_MONTH * hours * factor, 6)
        return {"cost": cost, "usage_hours": hours, "usage_types": {usage: cost}}

    res = {}
    for i in instances:
        if i.state == "running":
            res[i.id] = entry(instance_cost(i, pb)[0], "APS3-BoxUsage:" + i.type)
    for v in volumes:
        if v.id != "vol-0fresh000000demo":
            res[v.id] = entry(volume_cost(v, pb)[0], "APS3-EBS:VolumeUsage.gp3")
    for a in addresses:
        res[a.public_ip] = entry(address_cost(a, pb)[0], "APS3-PublicIPv4:" +
                                 ("IdleAddress" if a.associated_with is None else "InUseAddress"))
    for s_ in snapshots:  # snapshots really store fewer blocks than the volume size
        res[s_.id] = entry(snapshot_cost(s_, pb)[0], "APS3-EBS:SnapshotUsage", factor=0.42)
    for b in buckets:
        res[b.name] = entry(bucket_cost(b, pb)[0], "APS3-TimedStorage-ByteHrs", factor=0.97)
    bill = {"source": "SYNTHETIC example bill (demo only)", "synthetic": True,
            "period_start": period_start, "period_end": NOW.isoformat(), "resources": res}
    return snap, manifest, bill


def main() -> None:
    snap, manifest, bill = build()
    print("Wrote", save_snapshot(snap))
    for folder, data in ((LAB_DIR, manifest), (BILL_DIR, bill)):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "demo.json").write_text(json.dumps(data, indent=1))
        print("Wrote", folder / "demo.json")


if __name__ == "__main__":
    main()
