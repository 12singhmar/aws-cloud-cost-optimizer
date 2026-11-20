"""Download real AWS prices from the public AWS Price List (no AWS account needed).

AWS publishes every price as a big CSV file at pricing.us-east-1.amazonaws.com.
The EC2 file for one region is ~200 MB, so we *stream* it line by line and keep
only the handful of prices this project uses. The result is a small JSON file
(backend/data/prices/<region>.json) that the app reads.

Every price we keep remembers its SKU (AWS's ID for that price), so each
finding in the app can say exactly which official price it used.

Usage:
    python scripts/fetch_prices.py                # default region ap-south-1 (Mumbai)
    python scripts/fetch_prices.py --region us-east-1
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "prices"

# Instance families we price. Keeping the list short keeps the JSON small.
FAMILIES = (
    "t3", "t3a", "t4g",                    # burstable (t4g = ARM / Graviton)
    "m5", "m6i", "m7i", "m6g", "m7g",      # general purpose
    "c5", "c6i", "c7i", "c6g", "c7g",      # compute optimized
    "r5", "r6i", "r7i", "r6g", "r7g",      # memory optimized
)
# Standard Reserved Instance terms we keep (lease_purchase-option)
RESERVED_TERMS = ("1yr_no_upfront", "1yr_all_upfront", "3yr_all_upfront")

# usageType suffix -> our key. AWS prefixes usage types with a region code
# (e.g. "APS3-EBS:VolumeUsage.gp3"), so we match on the part after the prefix.
EC2_OTHER = {
    "EBS:VolumeUsage.gp3": "ebs_gp3_gb_month",
    "EBS:VolumeUsage.gp2": "ebs_gp2_gb_month",
    "EBS:VolumeUsage.st1": "ebs_st1_gb_month",
    "EBS:VolumeUsage.sc1": "ebs_sc1_gb_month",
    "EBS:VolumeUsage": "ebs_standard_gb_month",
    "EBS:VolumeP-IOPS.gp3": "ebs_gp3_iops_month",
    "EBS:VolumeP-Throughput.gp3": "ebs_gp3_mbps_month",
    "EBS:SnapshotUsage": "ebs_snapshot_gb_month",
}
# Public IPv4 addresses are billed under Amazon VPC, not EC2.
VPC_KEYS = {
    "PublicIPv4:IdleAddress": "public_ipv4_idle_hour",
    "PublicIPv4:InUseAddress": "public_ipv4_inuse_hour",
}
S3_KEYS = {"TimedStorage-ByteHrs": "s3_standard_gb_month"}


def _entry(r: dict) -> dict:
    usd, unit = float(r["PricePerUnit"]), r["Unit"]
    if unit == "GiBps-mo":  # gp3 throughput is listed per GiB/s; we use MiB/s
        usd, unit = usd / 1024, "MiBps-Mo"
    return {"usd": round(usd, 6), "unit": unit, "sku": r["SKU"],
            "description": r["PriceDescription"]}


def _stream_csv(url: str):
    """Yield rows of an AWS price-list CSV without loading it into memory."""
    resp = urllib.request.urlopen(url, timeout=120)
    text = io.TextIOWrapper(resp, encoding="utf-8", newline="")
    meta = {}
    for _ in range(5):  # 5 metadata lines before the real header
        line = next(csv.reader([text.readline()]))
        meta[line[0]] = line[1]
    return meta, csv.DictReader(text)


def _suffix(usage_type: str) -> str:
    # "APS3-EBS:VolumeUsage.gp3" -> "EBS:VolumeUsage.gp3"; "EBS:VolumeUsage" stays
    head, _, rest = usage_type.partition("-")
    return rest if rest and ":" in rest or rest.startswith("TimedStorage") else usage_type


def fetch(region: str) -> dict:
    prices: dict = {"instances": {}, "other": {}}

    meta, rows = _stream_csv(f"{BASE}/AmazonEC2/current/{region}/index.csv")
    print(f"EC2 price list version {meta.get('Version')} - streaming...")
    reserved: dict[str, dict] = {}
    for r in rows:
        if r["Location Type"] != "AWS Region":
            continue
        family = r["Product Family"]
        if family == "Compute Instance":
            itype = r["Instance Type"]
            if not (
                itype.split(".")[0] in FAMILIES
                and r["Tenancy"] == "Shared"
                and r["Operating System"] == "Linux"
                and r["Pre Installed S/W"] == "NA"
                and r["CapacityStatus"] == "Used"
                and r["License Model"] == "No License required"
            ):
                continue
            if r["TermType"] == "OnDemand":
                prices["instances"][itype] = {
                    "usd_per_hour": float(r["PricePerUnit"]),
                    "vcpu": int(r["vCPU"]),
                    "memory_gib": float(r["Memory"].split()[0].replace(",", "")),
                    "category": r["Instance Family"],          # General purpose, Compute optimized...
                    "arm": "Graviton" in r["Physical Processor"],
                    "sku": r["SKU"],
                    "description": r["PriceDescription"],
                }
            elif r["TermType"] == "Reserved" and r["OfferingClass"] == "standard":
                # Reserved Instance price: an upfront part ("Quantity") and/or an hourly part ("Hrs")
                key = f"{r['LeaseContractLength']}_{r['PurchaseOption'].lower().replace(' ', '_')}"
                if key not in RESERVED_TERMS:
                    continue
                term = reserved.setdefault(itype, {}).setdefault(key, {"upfront": 0.0, "hourly": 0.0})
                if r["Unit"] == "Quantity":
                    term["upfront"] = float(r["PricePerUnit"])
                else:
                    term["hourly"] = float(r["PricePerUnit"])
        elif r["TermType"] == "OnDemand":
            key = EC2_OTHER.get(_suffix(r["usageType"]))
            if key and float(r["PricePerUnit"]) > 0 and key not in prices["other"]:
                prices["other"][key] = _entry(r)
    for itype, terms in reserved.items():
        if itype in prices["instances"]:
            prices["instances"][itype]["reserved"] = terms

    _, rows = _stream_csv(f"{BASE}/AmazonVPC/current/{region}/index.csv")
    print("VPC price list - streaming...")
    for r in rows:
        key = VPC_KEYS.get(_suffix(r["usageType"]))
        if r["TermType"] == "OnDemand" and key and key not in prices["other"]:
            prices["other"][key] = _entry(r)

    meta_s3, rows = _stream_csv(f"{BASE}/AmazonS3/current/{region}/index.csv")
    print(f"S3 price list version {meta_s3.get('Version')} - streaming...")
    for r in rows:
        if r["TermType"] != "OnDemand" or r["StartingRange"] != "0":
            continue
        key = S3_KEYS.get(_suffix(r["usageType"]))
        if key and r.get("Volume Type") == "Standard" and key not in prices["other"]:
            prices["other"][key] = _entry(r)

    return {
        "region": region,
        "source": f"{BASE}/AmazonEC2/current/{region}/index.csv (+ AmazonS3)",
        "ec2_price_list_version": meta.get("Version"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hours_per_month": 730,  # AWS's own convention for monthly estimates
        **prices,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="ap-south-1")
    args = ap.parse_args()
    data = fetch(args.region)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.region}.json"
    out.write_text(json.dumps(data, indent=1, sort_keys=True))
    print(f"Saved {len(data['instances'])} instance prices and "
          f"{len(data['other'])} other prices to {out}")
    missing = set(EC2_OTHER.values()) | set(VPC_KEYS.values()) | set(S3_KEYS.values())
    missing -= set(data["other"])
    if missing:
        print("WARNING: not found:", sorted(missing))


if __name__ == "__main__":
    main()
