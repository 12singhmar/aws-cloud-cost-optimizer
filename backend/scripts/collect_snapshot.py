"""Collect a READ-ONLY snapshot of your real AWS account.

Only "describe/list/get" calls are made - this script cannot change anything.
Cost: the EC2/S3 describe calls are free; CloudWatch GetMetricStatistics is
inside the free tier (1 million requests/month). We deliberately do NOT use
GetMetricData or the Cost Explorer API, because those are always charged.

Usage:
    python scripts/collect_snapshot.py --profile ccx-readonly
    python scripts/collect_snapshot.py --profile ccx-readonly --lab lab-2026-11-25

Output: data/snapshots/aws-<date>.json  (+ data/labs/<same id>.json with --lab)
"""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timedelta, timezone

from _aws import ClientError, mask_account, session, tags_to_dict

from app.config import LAB_DIR
from app.models import (Address, Bucket, EbsSnapshot, IncompleteUpload, Instance,
                        InstanceMetrics, Snapshot, SnapshotMeta, Volume)
from app.store import save_snapshot

STOP_TIME = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)")


def hourly(cw, namespace: str, metric: str, dims: list, stat: str,
           start: datetime, hours: int) -> list:
    """One CloudWatch call -> list of `hours` values (None where no datapoint)."""
    resp = cw.get_metric_statistics(Namespace=namespace, MetricName=metric, Dimensions=dims,
                                    StartTime=start, EndTime=start + timedelta(hours=hours),
                                    Period=3600, Statistics=[stat])
    out = [None] * hours
    for p in resp["Datapoints"]:
        k = int((p["Timestamp"] - start).total_seconds() // 3600)
        if 0 <= k < hours:
            out[k] = round(p[stat], 4)
    return out


def collect(sess, region: str, days: int) -> Snapshot:
    ec2, cw, s3 = sess.client("ec2"), sess.client("cloudwatch"), sess.client("s3")
    account = sess.client("sts").get_caller_identity()["Account"]
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hours = days * 24
    start = now - timedelta(hours=hours)

    print("Instances...")
    instances, metrics = [], {}
    for page in ec2.get_paginator("describe_instances").paginate():
        for r in page["Reservations"]:
            for i in r["Instances"]:
                state = i["State"]["Name"]
                if state in ("terminated", "shutting-down"):
                    continue
                m = STOP_TIME.search(i.get("StateTransitionReason", ""))
                since = (datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                         if m and state == "stopped" else None)
                tags = tags_to_dict(i.get("Tags"))
                instances.append(Instance(
                    id=i["InstanceId"], name=tags.get("Name", ""), type=i["InstanceType"], state=state,
                    launch_time=i["LaunchTime"], state_since=since, tags=tags,
                    public_ip=i.get("PublicIpAddress"),
                    volume_ids=[b["Ebs"]["VolumeId"] for b in i.get("BlockDeviceMappings", []) if "Ebs" in b]))
                if state == "running":
                    dims = [{"Name": "InstanceId", "Value": i["InstanceId"]}]
                    metrics[i["InstanceId"]] = InstanceMetrics(
                        start=start,
                        cpu_avg=hourly(cw, "AWS/EC2", "CPUUtilization", dims, "Average", start, hours),
                        cpu_max=hourly(cw, "AWS/EC2", "CPUUtilization", dims, "Maximum", start, hours),
                        net_in_bytes=hourly(cw, "AWS/EC2", "NetworkIn", dims, "Sum", start, hours))

    print("Volumes...")
    volumes = []
    for page in ec2.get_paginator("describe_volumes").paginate():
        for v in page["Volumes"]:
            att = v.get("Attachments") or []
            tags = tags_to_dict(v.get("Tags"))
            volumes.append(Volume(id=v["VolumeId"], name=tags.get("Name", ""), type=v["VolumeType"],
                                  size_gb=v["Size"], iops=v.get("Iops"), throughput=v.get("Throughput"),
                                  state=v["State"], create_time=v["CreateTime"], tags=tags,
                                  attached_to=att[0]["InstanceId"] if att else None))
    volume_ids = {v.id for v in volumes}

    print("Elastic IPs...")
    addresses = [Address(allocation_id=a["AllocationId"], public_ip=a["PublicIp"],
                         # empty string counts as "not associated" too
                         associated_with=a.get("InstanceId") or a.get("NetworkInterfaceId") or None,
                         tags=tags_to_dict(a.get("Tags")))
                 for a in ec2.describe_addresses()["Addresses"] if "AllocationId" in a]

    print("EBS snapshots...")
    ami_snaps = {b["Ebs"]["SnapshotId"]
                 for img in ec2.describe_images(Owners=["self"])["Images"]
                 for b in img.get("BlockDeviceMappings", []) if b.get("Ebs", {}).get("SnapshotId")}
    snapshots = []
    for page in ec2.get_paginator("describe_snapshots").paginate(OwnerIds=["self"]):
        for sn in page["Snapshots"]:
            vid = sn.get("VolumeId")
            snapshots.append(EbsSnapshot(
                id=sn["SnapshotId"], volume_id=vid, size_gb=sn["VolumeSize"],
                volume_exists=bool(vid) and vid in volume_ids,
                used_by_ami=sn["SnapshotId"] in ami_snaps,
                start_time=sn["StartTime"], description=sn.get("Description", ""),
                tags=tags_to_dict(sn.get("Tags"))))

    print("S3 buckets...")
    buckets = []
    for b in s3.list_buckets()["Buckets"]:
        name = b["Name"]
        try:
            loc = s3.get_bucket_location(Bucket=name)["LocationConstraint"] or "us-east-1"
        except ClientError:
            continue
        if loc != region:
            continue
        try:
            s3.get_bucket_lifecycle_configuration(Bucket=name)
            has_lc = True
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchLifecycleConfiguration":
                raise
            has_lc = False
        uploads = []
        for page in s3.get_paginator("list_multipart_uploads").paginate(Bucket=name):
            for u in page.get("Uploads", []):
                size = sum(p["Size"] for pg in s3.get_paginator("list_parts").paginate(
                    Bucket=name, Key=u["Key"], UploadId=u["UploadId"]) for p in pg.get("Parts", []))
                uploads.append(IncompleteUpload(key=u["Key"], initiated=u["Initiated"], size_bytes=size))
        size = cw.get_metric_statistics(
            Namespace="AWS/S3", MetricName="BucketSizeBytes", Period=86400, Statistics=["Average"],
            Dimensions=[{"Name": "BucketName", "Value": name},
                        {"Name": "StorageType", "Value": "StandardStorage"}],
            StartTime=now - timedelta(days=3), EndTime=now)["Datapoints"]
        size_gb = (max(size, key=lambda p: p["Timestamp"])["Average"] / 2**30) if size else 0.0
        try:
            tags = tags_to_dict(s3.get_bucket_tagging(Bucket=name)["TagSet"])
        except ClientError:
            tags = {}
        buckets.append(Bucket(name=name, size_gb=round(size_gb, 4), has_lifecycle=has_lc,
                              incomplete_uploads=uploads, tags=tags))

    snap_id = f"aws-{now:%Y-%m-%d-%H%M}"
    return Snapshot(
        meta=SnapshotMeta(id=snap_id, source="aws", region=region, account=mask_account(account),
                          collected_at=now, metric_days=days,
                          notes="Collected read-only with scripts/collect_snapshot.py"),
        instances=instances, volumes=volumes, addresses=addresses, snapshots=snapshots,
        buckets=buckets, metrics=metrics)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", help="AWS CLI profile (use the read-only one)")
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--days", type=int, default=14, help="days of CloudWatch history (max 14 here)")
    ap.add_argument("--lab", help="lab id from lab_plant.py; links its answer key to this snapshot")
    args = ap.parse_args()

    snap = collect(session(args.profile, args.region), args.region, min(args.days, 14))
    path = save_snapshot(snap)
    print(f"\nSaved {path}")
    print(f"  {len(snap.instances)} instances, {len(snap.volumes)} volumes, {len(snap.addresses)} IPs, "
          f"{len(snap.snapshots)} snapshots, {len(snap.buckets)} buckets")
    if args.lab:
        src = LAB_DIR / f"manifest-{args.lab}.json"
        if not src.exists():
            raise SystemExit(f"Lab manifest {src} not found")
        dst = LAB_DIR / f"{snap.meta.id}.json"
        shutil.copy(src, dst)
        print(f"  Lab answer key linked: {dst}")
    print("Open the app and pick this snapshot in the top bar.")


if __name__ == "__main__":
    main()
