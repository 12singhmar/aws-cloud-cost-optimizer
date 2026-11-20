"""Reads an AWS account with boto3. Read-only: only describe/get calls.

Credentials come from the normal AWS chain, so any of these work:
  - `aws login --profile ccx` (console sign-in, no access keys)
  - access keys from `aws configure`
  - temporary keys in environment variables (e.g. a sandbox account)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import boto3

from app.models import EbsSnapshot, ElasticIp, Instance, Metrics, Scan, Volume

METRIC_DAYS = 14
STOP_TIME = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)")


def make_session(profile: str | None = None, region: str | None = None):
    return boto3.Session(profile_name=profile, region_name=region)


def whoami(session) -> dict:
    """Which account are we connected to? Raises if credentials are missing/invalid."""
    ident = session.client("sts").get_caller_identity()
    return {"account": mask(ident["Account"]),
            "arn_type": ident["Arn"].split(":")[5].split("/")[0],   # user, assumed-role, root
            "region": session.region_name}


def mask(account_id: str) -> str:
    return "********" + account_id[-4:]


def _name(tags) -> str:
    return next((t["Value"] for t in tags or [] if t["Key"] == "Name"), "")


def _hourly(cw, instance_id: str, metric: str, stat: str, start: datetime, hours: int) -> list:
    resp = cw.get_metric_statistics(
        Namespace="AWS/EC2", MetricName=metric, Statistics=[stat], Period=3600,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start, EndTime=start + timedelta(hours=hours))
    values = [None] * hours
    for point in resp["Datapoints"]:
        k = int((point["Timestamp"] - start).total_seconds() // 3600)
        if 0 <= k < hours:
            values[k] = point[stat]
    return values


def scan_account(session) -> Scan:
    ec2 = session.client("ec2")
    cw = session.client("cloudwatch")
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hours = METRIC_DAYS * 24
    start = now - timedelta(hours=hours)

    instances, metrics = [], {}
    for page in ec2.get_paginator("describe_instances").paginate():
        for res in page["Reservations"]:
            for i in res["Instances"]:
                state = i["State"]["Name"]
                if state in ("terminated", "shutting-down"):
                    continue
                stopped = STOP_TIME.search(i.get("StateTransitionReason", ""))
                instances.append(Instance(
                    id=i["InstanceId"], name=_name(i.get("Tags")), type=i["InstanceType"],
                    state=state, launch_time=i["LaunchTime"],
                    stopped_since=(datetime.strptime(stopped.group(1), "%Y-%m-%d %H:%M:%S")
                                   .replace(tzinfo=timezone.utc) if stopped and state == "stopped" else None),
                    volume_ids=[b["Ebs"]["VolumeId"] for b in i.get("BlockDeviceMappings", []) if "Ebs" in b]))
                if state == "running":
                    metrics[i["InstanceId"]] = Metrics(
                        cpu=_hourly(cw, i["InstanceId"], "CPUUtilization", "Average", start, hours),
                        network_in=_hourly(cw, i["InstanceId"], "NetworkIn", "Sum", start, hours))

    volumes = []
    for page in ec2.get_paginator("describe_volumes").paginate():
        for v in page["Volumes"]:
            att = v.get("Attachments") or []
            volumes.append(Volume(
                id=v["VolumeId"], name=_name(v.get("Tags")), type=v["VolumeType"], size_gb=v["Size"],
                iops=v.get("Iops"), throughput=v.get("Throughput"), state=v["State"],
                created=v["CreateTime"], attached_to=att[0]["InstanceId"] if att else None))
    volume_ids = {v.id for v in volumes}

    elastic_ips = [ElasticIp(allocation_id=a["AllocationId"], public_ip=a["PublicIp"],
                             # an empty string also means "not attached"
                             attached_to=a.get("InstanceId") or a.get("NetworkInterfaceId") or None)
                   for a in ec2.describe_addresses()["Addresses"] if "AllocationId" in a]

    ami_snapshots = {b["Ebs"]["SnapshotId"]
                     for img in ec2.describe_images(Owners=["self"])["Images"]
                     for b in img.get("BlockDeviceMappings", []) if "SnapshotId" in b.get("Ebs", {})}
    snapshots = []
    for page in ec2.get_paginator("describe_snapshots").paginate(OwnerIds=["self"]):
        for s in page["Snapshots"]:
            snapshots.append(EbsSnapshot(
                id=s["SnapshotId"], volume_id=s.get("VolumeId"), size_gb=s["VolumeSize"],
                volume_exists=s.get("VolumeId") in volume_ids,
                used_by_ami=s["SnapshotId"] in ami_snapshots, created=s["StartTime"]))

    return Scan(id=f"scan-{now:%Y%m%d-%H%M}", source="aws",
                account=whoami(session)["account"], region=session.region_name, scanned_at=now,
                instances=instances, volumes=volumes, elastic_ips=elastic_ips,
                snapshots=snapshots, metrics=metrics)
