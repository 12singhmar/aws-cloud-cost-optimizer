"""Waste Lab, last step: delete EVERYTHING the lab created.

Finds resources by the tag ccx-lab=<lab id>, so it never touches anything else.
Run with --dry-run first to see the list.

Usage:
    python scripts/lab_teardown.py --profile ccx-lab-admin --lab lab-2026-11-25-ab12 --dry-run
    python scripts/lab_teardown.py --profile ccx-lab-admin --lab lab-2026-11-25-ab12 --yes
"""

from __future__ import annotations

import argparse

from _aws import LAB_TAG, ClientError, session, tags_to_dict


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile")
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--lab", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    if not (args.yes or args.dry_run):
        raise SystemExit("Add --dry-run to preview, or --yes to delete.")

    sess = session(args.profile, args.region)
    ec2, s3 = sess.client("ec2"), sess.client("s3")
    f = [{"Name": f"tag:{LAB_TAG}", "Values": [args.lab]}]
    dry = args.dry_run

    def act(label, fn, **kw):
        print(("[dry-run] " if dry else "") + label)
        if not dry:
            try:
                fn(**kw)
            except ClientError as e:
                print("   skipped:", e.response["Error"]["Message"])

    for a in ec2.describe_addresses(Filters=f)["Addresses"]:
        if "AssociationId" in a:
            act(f"disassociate {a['PublicIp']}", ec2.disassociate_address, AssociationId=a["AssociationId"])
        act(f"release {a['PublicIp']}", ec2.release_address, AllocationId=a["AllocationId"])

    ids = [i["InstanceId"] for r in ec2.describe_instances(Filters=f)["Reservations"]
           for i in r["Instances"] if i["State"]["Name"] != "terminated"]
    if ids:
        act(f"terminate {ids}", ec2.terminate_instances, InstanceIds=ids)
        if not dry:
            print("   waiting for termination (deletes their root disks too)...")
            ec2.get_waiter("instance_terminated").wait(InstanceIds=ids)

    for v in ec2.describe_volumes(Filters=f)["Volumes"]:
        act(f"delete volume {v['VolumeId']}", ec2.delete_volume, VolumeId=v["VolumeId"])
    for sn in ec2.describe_snapshots(OwnerIds=["self"], Filters=f)["Snapshots"]:
        act(f"delete snapshot {sn['SnapshotId']}", ec2.delete_snapshot, SnapshotId=sn["SnapshotId"])

    for b in s3.list_buckets()["Buckets"]:
        name = b["Name"]
        if not name.startswith(args.lab):
            continue
        try:
            if tags_to_dict(s3.get_bucket_tagging(Bucket=name)["TagSet"]).get(LAB_TAG) != args.lab:
                continue
        except ClientError:
            continue
        for u in s3.list_multipart_uploads(Bucket=name).get("Uploads", []):
            act(f"abort upload {name}/{u['Key']}", s3.abort_multipart_upload,
                Bucket=name, Key=u["Key"], UploadId=u["UploadId"])
        for o in s3.list_objects_v2(Bucket=name).get("Contents", []):
            act(f"delete {name}/{o['Key']}", s3.delete_object, Bucket=name, Key=o["Key"])
        act(f"delete bucket {name}", s3.delete_bucket, Bucket=name)

    print("\nDone." if not dry else "\nNothing deleted (dry run).")
    print("Also: in the Billing console you may delete the CUR export and its bucket when finished.")


if __name__ == "__main__":
    main()
