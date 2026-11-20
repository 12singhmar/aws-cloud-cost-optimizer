"""Waste Lab, step 1: plant KNOWN waste (and decoys) in your own AWS account.

This is the only script that creates things. Everything is tiny, tagged
`ccx-lab=<lab id>`, and removed by lab_teardown.py.

What it creates (region ap-south-1 by default):

  WASTE (the tool should flag these)
    idle      t3.micro running, doing nothing, no public IP     -> ec2-idle
    stopped   t3.micro started then stopped (its disk is billed) -> ec2-stopped
    volume    1 GB gp3 disk not attached to anything             -> ebs-unattached
    ip        Elastic IP not attached to anything                -> eip-idle
    snapshot  snapshot of a 1 GB disk that is then deleted       -> snapshot-orphan
    uploads   S3 bucket with an unfinished 5 MiB upload          -> s3-incomplete-uploads

  DECOYS (look suspicious to a naive tool, but must NOT be flagged)
    proxy     t3.micro with ~0% CPU but steady downloads   (must not be called idle)
    batch     t3.micro quiet for 7 days, then a nightly 2-hour job at 100% CPU
    ip-used   Elastic IP attached to the proxy
    snap-ok   snapshot of a disk that still exists
    bucket-ok S3 bucket with a lifecycle rule and a normal file

Cost: about 10 days x (3 t3.micro + IPv4 + tiny disks) = roughly USD 8-10,
paid from the free plan's credits. On the AWS *free plan* you are not charged
money unless you upgrade to a paid plan. Check your plan before running.

Usage:
    python scripts/lab_plant.py --profile ccx-lab-admin --yes
Then wait 10 days (7 to decide + 3 to check), and run collect_snapshot.py --lab <id>.
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
from datetime import datetime, timezone

from _aws import LAB_TAG, session

from app.config import LAB_DIR

INSTANCE_TYPE = "t3.micro"   # free-tier eligible for accounts created after 15 July 2025
AMI_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"

PROXY_SCRIPT = """#!/bin/bash
# Decoy: almost no CPU, but a steady ~50 KB/s download (inbound data is free).
cat > /usr/local/bin/lab-traffic.sh <<'EOF'
#!/bin/bash
while true; do
  curl -s --limit-rate 50k -o /dev/null \
    https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/region_index.json
  sleep 1
done
EOF
chmod +x /usr/local/bin/lab-traffic.sh
cat > /etc/systemd/system/lab-traffic.service <<'EOF'
[Service]
ExecStart=/usr/local/bin/lab-traffic.sh
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now lab-traffic.service
"""

BATCH_SCRIPT = """#!/bin/bash
# Decoy: quiet for 7 days, then a 2-hour job at 100% CPU every night (01:00 UTC).
date +%s > /etc/lab-start
cat > /usr/local/bin/lab-batch.sh <<'EOF'
#!/bin/bash
start=$(cat /etc/lab-start); now=$(date +%s)
[ $((now - start)) -lt 604800 ] && exit 0      # first 7 days: do nothing
for c in 1 2; do timeout 7200 sh -c 'while :; do :; done' & done; wait
EOF
chmod +x /usr/local/bin/lab-batch.sh
cat > /etc/systemd/system/lab-batch.service <<'EOF'
[Service]
Type=oneshot
ExecStart=/usr/local/bin/lab-batch.sh
EOF
cat > /etc/systemd/system/lab-batch.timer <<'EOF'
[Timer]
OnCalendar=*-*-* 01:00:00
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload && systemctl enable --now lab-batch.timer
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", help="AWS CLI profile with permission to create resources")
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--yes", action="store_true", help="confirm you want to create resources")
    args = ap.parse_args()
    if not args.yes:
        raise SystemExit("This CREATES resources (about USD 8-10 of free-plan credit over 10 days).\n"
                         "Read the docstring, then re-run with --yes.")

    sess = session(args.profile, args.region)
    ec2, s3, ssm = sess.client("ec2"), sess.client("s3"), sess.client("ssm")
    lab_id = f"lab-{datetime.now(timezone.utc):%Y-%m-%d}-{secrets.token_hex(2)}"
    tag = {"Key": LAB_TAG, "Value": lab_id}
    items: list[dict] = []

    def add(rid, kind, role, why, expected=None, must_not=None):
        items.append({"resource_id": rid, "kind": kind, "role": role, "expected_rule": expected,
                      "must_not": must_not or [], "why": why})
        print(f"  {role:5} {kind:13} {rid}")

    def tags(name, rtype):
        return [{"ResourceType": rtype, "Tags": [tag, {"Key": "Name", "Value": f"{lab_id}-{name}"}]}]

    # Safety check: is t3.micro free-tier eligible in this account/region?
    eligible = ec2.describe_instance_types(
        InstanceTypes=[INSTANCE_TYPE],
        Filters=[{"Name": "free-tier-eligible", "Values": ["true"]}])["InstanceTypes"]
    if not eligible:
        print(f"WARNING: {INSTANCE_TYPE} is not marked free-tier eligible here. Press Ctrl+C to stop.")

    ami = ssm.get_parameter(Name=AMI_PARAM)["Parameter"]["Value"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "default-for-az", "Values": ["true"]}])["Subnets"]
    if not subnets:
        raise SystemExit("No default VPC subnet found. Create one: aws ec2 create-default-vpc")
    subnet, az = subnets[0]["SubnetId"], subnets[0]["AvailabilityZone"]
    print(f"Lab {lab_id} in {args.region} ({az}, {subnet}), AMI {ami}")

    def launch(name, user_data=None, public=False):
        # Only the proxy gets a public IP (it needs internet). The others don't,
        # which avoids paying for public IPv4 addresses we don't need.
        kw = dict(ImageId=ami, InstanceType=INSTANCE_TYPE, MinCount=1, MaxCount=1,
                  CreditSpecification={"CpuCredits": "standard"},  # no surprise surplus-credit charges
                  NetworkInterfaces=[{"DeviceIndex": 0, "SubnetId": subnet,
                                      "AssociatePublicIpAddress": public}],
                  TagSpecifications=tags(name, "instance") + tags(name, "volume"))
        if user_data:
            kw["UserData"] = base64.b64encode(user_data.encode()).decode()
        return ec2.run_instances(**kw)["Instances"][0]["InstanceId"]

    idle = launch("idle")
    stopped = launch("stopped")
    batch = launch("batch", BATCH_SCRIPT)
    proxy = launch("proxy", PROXY_SCRIPT, public=True)   # needs internet for its downloads
    print("Waiting for instances to start...")
    ec2.get_waiter("instance_running").wait(InstanceIds=[idle, stopped, batch, proxy])
    ec2.stop_instances(InstanceIds=[stopped])
    add(idle, "EC2 instance", "waste", "Running, nothing installed, no traffic", "ec2-idle")
    add(stopped, "EC2 instance", "waste", "Stopped; its 8 GB disk is still billed", "ec2-stopped")
    add(proxy, "EC2 instance", "decoy", "Near-zero CPU but steady downloads: it is working",
        must_not=["ec2-idle"])
    add(batch, "EC2 instance", "decoy", "Quiet for 7 days, then a nightly 2-hour job")

    vol = ec2.create_volume(AvailabilityZone=az, Size=1, VolumeType="gp3",
                            TagSpecifications=tags("unattached", "volume"))["VolumeId"]
    tmp = ec2.create_volume(AvailabilityZone=az, Size=1, VolumeType="gp3",
                            TagSpecifications=tags("to-delete", "volume"))["VolumeId"]
    ec2.get_waiter("volume_available").wait(VolumeIds=[vol, tmp])
    add(vol, "EBS volume", "waste", "1 GB disk attached to nothing", "ebs-unattached")

    orphan = ec2.create_snapshot(VolumeId=tmp, TagSpecifications=tags("orphan", "snapshot"))["SnapshotId"]
    keep = ec2.create_snapshot(VolumeId=vol, TagSpecifications=tags("keep", "snapshot"))["SnapshotId"]
    ec2.get_waiter("snapshot_completed").wait(SnapshotIds=[orphan, keep])
    ec2.delete_volume(VolumeId=tmp)
    add(orphan, "EBS snapshot", "waste", "Its source disk has been deleted", "snapshot-orphan")
    add(keep, "EBS snapshot", "decoy", "Backup of a disk that still exists")

    eip_idle = ec2.allocate_address(Domain="vpc", TagSpecifications=tags("idle-ip", "elastic-ip"))
    eip_used = ec2.allocate_address(Domain="vpc", TagSpecifications=tags("used-ip", "elastic-ip"))
    ec2.associate_address(AllocationId=eip_used["AllocationId"], InstanceId=proxy)
    add(eip_idle["AllocationId"], "Elastic IP", "waste", "Reserved, attached to nothing", "eip-idle")
    add(eip_used["AllocationId"], "Elastic IP", "decoy", "Attached to the running proxy")

    suffix = secrets.token_hex(3)
    loc = {} if args.region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": args.region}}
    waste_bucket, ok_bucket = f"{lab_id}-{suffix}-uploads", f"{lab_id}-{suffix}-ok"
    for b in (waste_bucket, ok_bucket):
        s3.create_bucket(Bucket=b, **loc)
        s3.put_bucket_tagging(Bucket=b, Tagging={"TagSet": [tag]})
    up = s3.create_multipart_upload(Bucket=waste_bucket, Key="big-video.mp4")
    s3.upload_part(Bucket=waste_bucket, Key="big-video.mp4", UploadId=up["UploadId"],
                   PartNumber=1, Body=b"0" * (5 * 2**20))   # 5 MiB, never completed
    s3.put_object(Bucket=ok_bucket, Key="index.html", Body=b"<h1>ok</h1>")
    s3.put_bucket_lifecycle_configuration(Bucket=ok_bucket, LifecycleConfiguration={"Rules": [{
        "ID": "abort-mpu", "Status": "Enabled", "Filter": {},
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}}]})
    add(waste_bucket, "S3 bucket", "waste", "Unfinished 5 MiB upload, invisible in the console",
        "s3-incomplete-uploads")
    add(ok_bucket, "S3 bucket", "decoy", "Normal file and a lifecycle rule")

    manifest = {"lab_id": lab_id, "synthetic": False, "region": args.region,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "items": items}
    LAB_DIR.mkdir(parents=True, exist_ok=True)
    out = LAB_DIR / f"manifest-{lab_id}.json"
    out.write_text(json.dumps(manifest, indent=1))
    print(f"\nAnswer key saved to {out}")
    print(f"Next: wait 10 days, then\n  python scripts/collect_snapshot.py --profile <read-only> --lab {lab_id}")
    print(f"Clean up afterwards:\n  python scripts/lab_teardown.py --profile <admin> --lab {lab_id} --yes")


if __name__ == "__main__":
    main()
