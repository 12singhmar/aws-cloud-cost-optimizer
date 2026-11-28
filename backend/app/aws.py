"""Reads an AWS account with boto3, in every region. Only describe/get/list calls.

Credentials come from the normal AWS places: `aws login --profile ccx`,
`aws configure`, or environment variables.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.models import Metrics, Resource, Scan

CPU_DAYS = 14
STOP_TIME = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)")


def make_session(profile=None, region=None):
    return boto3.Session(profile_name=profile, region_name=region or "us-east-1")


def is_fake_aws():
    """Test mode: boto3 is pointed at a fake AWS on this computer (moto), not the real one."""
    return bool(os.environ.get("AWS_ENDPOINT_URL"))


def mask(account_id):
    return "********" + account_id[-4:]


def whoami(session):
    ident = session.client("sts").get_caller_identity()
    return {"account": mask(ident["Account"]), "user": ident["Arn"].split(":")[-1]}


def enabled_regions(session):
    ec2 = session.client("ec2")
    regions = ec2.describe_regions(
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}])["Regions"]
    return sorted(r["RegionName"] for r in regions)


def name_of(tags):
    for t in tags or []:
        if t["Key"] == "Name":
            return t["Value"]
    return ""


def hourly(cw, namespace, metric, dims, stat, start, hours):
    """One CloudWatch call -> one value per hour (None where there is no data)."""
    resp = cw.get_metric_statistics(Namespace=namespace, MetricName=metric, Dimensions=dims,
                                    Statistics=[stat], Period=3600,
                                    StartTime=start, EndTime=start + timedelta(hours=hours))
    values = [None] * hours
    for p in resp["Datapoints"]:
        k = int((p["Timestamp"] - start).total_seconds() // 3600)
        if 0 <= k < hours:
            values[k] = p[stat]
    return values


def scan_region(clients, region, now):
    """Everything that can cost money in one region."""
    ec2, cw, elb = clients["ec2"], clients["cloudwatch"], clients["elbv2"]
    found, metrics = [], {}
    hours = CPU_DAYS * 24
    start = now - timedelta(hours=hours)

    # Servers
    for page in ec2.get_paginator("describe_instances").paginate():
        for res in page["Reservations"]:
            for i in res["Instances"]:
                state = i["State"]["Name"]
                if state in ("terminated", "shutting-down"):
                    continue
                stopped = STOP_TIME.search(i.get("StateTransitionReason", ""))
                found.append(Resource(
                    kind="instance", region=region, id=i["InstanceId"], name=name_of(i.get("Tags")),
                    state=state, created=i["LaunchTime"],
                    info={"type": i["InstanceType"], "public_ip": i.get("PublicIpAddress"),
                          "stopped_since": stopped.group(1) if stopped and state == "stopped" else None,
                          "volume_ids": [b["Ebs"]["VolumeId"] for b in i.get("BlockDeviceMappings", [])
                                         if "Ebs" in b]}))
                if state == "running":
                    dims = [{"Name": "InstanceId", "Value": i["InstanceId"]}]
                    metrics[i["InstanceId"]] = Metrics(
                        cpu_avg=hourly(cw, "AWS/EC2", "CPUUtilization", dims, "Average", start, hours),
                        cpu_max=hourly(cw, "AWS/EC2", "CPUUtilization", dims, "Maximum", start, hours))

    # Disks
    volume_ids = set()
    for page in ec2.get_paginator("describe_volumes").paginate():
        for v in page["Volumes"]:
            volume_ids.add(v["VolumeId"])
            att = v.get("Attachments") or []
            found.append(Resource(
                kind="volume", region=region, id=v["VolumeId"], name=name_of(v.get("Tags")),
                state=v["State"], created=v["CreateTime"],
                info={"size_gb": v["Size"], "type": v["VolumeType"], "iops": v.get("Iops"),
                      "throughput": v.get("Throughput"),
                      "attached_to": att[0]["InstanceId"] if att else None}))

    # Elastic IPs
    for a in ec2.describe_addresses()["Addresses"]:
        found.append(Resource(
            kind="elastic_ip", region=region, id=a["AllocationId"], name=a["PublicIp"],
            info={"public_ip": a["PublicIp"],
                  # an empty string also means "not attached"
                  "attached_to": a.get("InstanceId") or a.get("NetworkInterfaceId") or None}))

    # Snapshots (ours only), and which of them belong to our own machine images
    ami_snapshots = set()
    for img in ec2.describe_images(Owners=["self"])["Images"]:
        for b in img.get("BlockDeviceMappings", []):
            if "SnapshotId" in b.get("Ebs", {}):
                ami_snapshots.add(b["Ebs"]["SnapshotId"])
    for page in ec2.get_paginator("describe_snapshots").paginate(OwnerIds=["self"]):
        for s in page["Snapshots"]:
            if s.get("Description", "").startswith("Auto-created snapshot for AMI"):
                continue        # moto (the fake AWS used in tests) adds these; real AWS does not
            found.append(Resource(
                kind="snapshot", region=region, id=s["SnapshotId"], name=name_of(s.get("Tags")),
                state=s["State"], created=s["StartTime"],
                info={"size_gb": s["VolumeSize"], "volume_id": s.get("VolumeId"),
                      "volume_exists": s.get("VolumeId") in volume_ids,
                      "used_by_ami": s["SnapshotId"] in ami_snapshots,
                      "made_by_us": any(t["Key"] == "created-by" and t["Value"] == "aws-cost-cleaner"
                                        for t in s.get("Tags", []))}))

    # NAT gateways, and how much data each sent in the last 7 days
    for n in ec2.describe_nat_gateways(
            Filters=[{"Name": "state", "Values": ["pending", "available"]}])["NatGateways"]:
        sent = hourly(cw, "AWS/NATGateway", "BytesOutToDestination",
                      [{"Name": "NatGatewayId", "Value": n["NatGatewayId"]}], "Sum",
                      now - timedelta(days=7), 7 * 24)
        found.append(Resource(
            kind="nat_gateway", region=region, id=n["NatGatewayId"], name=name_of(n.get("Tags")),
            state=n["State"], created=n["CreateTime"],
            info={"bytes_sent_7d": sum(x for x in sent if x)}))

    # Load balancers, and how many servers are behind each
    for lb in elb.describe_load_balancers()["LoadBalancers"]:
        targets = 0
        try:
            groups = elb.describe_target_groups(LoadBalancerArn=lb["LoadBalancerArn"])["TargetGroups"]
        except ClientError as e:
            if e.response["Error"]["Code"] != "TargetGroupNotFound":
                raise
            groups = []        # no target groups at all
        for tg in groups:
            targets += len(elb.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
                           ["TargetHealthDescriptions"])
        found.append(Resource(
            kind="load_balancer", region=region, id=lb["LoadBalancerArn"], name=lb["LoadBalancerName"],
            state=lb["State"]["Code"], created=lb["CreatedTime"],
            info={"lb_type": lb["Type"], "targets": targets}))

    return found, metrics


def scan_account(session):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    regions = enabled_regions(session)
    # boto3 sessions are not thread-safe, so make every client here, then use them in threads
    clients = {r: {s: session.client(s, region_name=r) for s in ("ec2", "cloudwatch", "elbv2")}
               for r in regions}

    def one(region):
        try:
            return region, scan_region(clients[region], region, now), None
        except (BotoCoreError, ClientError) as e:
            return region, ([], {}), f"{region}: {e}"

    taken = datetime.now(timezone.utc)      # exact time; "now" above is rounded to the hour for CloudWatch
    scan = Scan(id=f"scan-{taken:%Y%m%d-%H%M%S}", account=whoami(session)["account"], scanned_at=taken,
                fake_aws=is_fake_aws(), regions=regions)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for region, (found, metrics), error in pool.map(one, regions):
            scan.resources += found
            scan.metrics.update(metrics)
            if error:
                scan.errors.append(error)

    # S3 is global: list buckets that have no lifecycle rule
    s3 = session.client("s3")
    try:
        for b in s3.list_buckets()["Buckets"]:
            try:
                s3.get_bucket_lifecycle_configuration(Bucket=b["Name"])
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
                    scan.buckets_without_lifecycle.append(b["Name"])
    except ClientError as e:
        scan.errors.append(f"S3: {e}")
    return scan
