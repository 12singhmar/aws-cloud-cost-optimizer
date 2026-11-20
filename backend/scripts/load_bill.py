"""Turn your real AWS bill (CUR 2.0 data export) into data/bills/<snapshot>.json.

Set up once in the AWS console (Billing -> Data Exports -> Create):
  type "Standard data export", table "CUR 2.0", tick "Include resource IDs",
  time granularity "Hourly", format "CSV (gzip)", deliver to an S3 bucket.
AWS starts writing files within 24 hours and refreshes them during the day.

Usage (either download the files yourself, or let the script fetch them):
    python scripts/load_bill.py --snapshot aws-2026-12-05-0900 --folder path/to/cur-files
    python scripts/load_bill.py --snapshot aws-2026-12-05-0900 --s3 s3://my-cur-bucket/prefix --profile ccx-readonly
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import BILL_DIR  # noqa: E402

KEEP_TYPES = {"Usage"}   # skip Credit, Tax, Refund, Fee... we compare usage charges only


def normalize(resource_id: str) -> str:
    """'arn:aws:ec2:ap-south-1:123:snapshot/snap-0abc' -> 'snap-0abc'."""
    return resource_id.rsplit("/", 1)[-1] if resource_id.startswith("arn:") else resource_id


def rows_from(blobs):
    for name, data in blobs:
        text = gzip.decompress(data).decode() if name.endswith(".gz") else data.decode()
        yield from csv.DictReader(io.StringIO(text))


def local_blobs(folder: Path):
    for p in sorted(folder.rglob("*.csv*")):
        yield p.name, p.read_bytes()


def s3_blobs(url: str, profile: str | None):
    import boto3
    bucket, _, prefix = url.removeprefix("s3://").partition("/")
    s3 = boto3.Session(profile_name=profile).client("s3")
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []):
            if ".csv" in o["Key"]:
                yield o["Key"], s3.get_object(Bucket=bucket, Key=o["Key"])["Body"].read()


def aggregate(rows) -> dict:
    res: dict[str, dict] = {}
    hours: dict[str, set] = {}
    starts, ends = [], []
    for r in rows:
        if r.get("line_item_line_item_type") not in KEEP_TYPES:
            continue
        rid = normalize(r.get("line_item_resource_id") or "")
        if not rid:
            continue
        cost = float(r.get("line_item_unblended_cost") or 0)
        ut = r.get("line_item_usage_type", "")
        e = res.setdefault(rid, {"cost": 0.0, "usage_types": {}})
        e["cost"] += cost
        e["usage_types"][ut] = e["usage_types"].get(ut, 0.0) + cost
        hours.setdefault(rid, set()).add(r["line_item_usage_start_date"])
        starts.append(r["line_item_usage_start_date"])
        ends.append(r.get("line_item_usage_end_date", r["line_item_usage_start_date"]))
    for rid, e in res.items():
        e["usage_hours"] = len(hours[rid])
        e["cost"] = round(e["cost"], 6)
    return {"period_start": min(starts) if starts else None,
            "period_end": max(ends) if ends else None, "resources": res}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="snapshot id to attach this bill to")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--folder", type=Path)
    g.add_argument("--s3")
    ap.add_argument("--profile")
    args = ap.parse_args()

    blobs = local_blobs(args.folder) if args.folder else s3_blobs(args.s3, args.profile)
    bill = {"source": "AWS CUR 2.0 data export (hourly, resource IDs)", "synthetic": False,
            **aggregate(rows_from(blobs))}
    BILL_DIR.mkdir(parents=True, exist_ok=True)
    out = BILL_DIR / f"{args.snapshot}.json"
    out.write_text(json.dumps(bill, indent=1))
    print(f"Saved {out}: {len(bill['resources'])} resources, "
          f"{bill['period_start']} -> {bill['period_end']}")


if __name__ == "__main__":
    main()
