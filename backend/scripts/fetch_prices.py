"""Download real AWS prices from the public AWS Price List (no AWS account needed).

AWS publishes every price as a big CSV file. The EC2 file for one region is
about 200-300 MB, so we read it line by line and keep only the prices this
project uses. The result is a small JSON file per region in data/prices/.

Usage:
    python scripts/fetch_prices.py --region ap-south-1
    python scripts/fetch_prices.py --all        # the 17 regions every account has
"""

import argparse
import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "prices"

# Regions that are switched on in every AWS account
DEFAULT_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "sa-east-1",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-north-1",
    "ap-south-1", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
    "ap-southeast-1", "ap-southeast-2",
]

# Instance families we keep prices for
FAMILIES = ("t2", "t3", "t3a", "t4g", "m5", "m6i", "m7i", "m6g", "m7g",
            "c5", "c6i", "c7i", "c6g", "c7g", "r5", "r6i", "r7i", "r6g", "r7g")

# End of AWS's "usage type" name -> our name for that price
EC2_PRICES = {
    "EBS:VolumeUsage.gp3": "ebs_gp3_gb_month",
    "EBS:VolumeUsage.gp2": "ebs_gp2_gb_month",
    "EBS:VolumeUsage.st1": "ebs_st1_gb_month",
    "EBS:VolumeUsage.sc1": "ebs_sc1_gb_month",
    "EBS:VolumeUsage": "ebs_standard_gb_month",
    "EBS:VolumeP-IOPS.gp3": "ebs_gp3_iops_month",
    "EBS:VolumeP-Throughput.gp3": "ebs_gp3_mbps_month",
    "EBS:SnapshotUsage": "ebs_snapshot_gb_month",
    "NatGateway-Hours": "nat_gateway_hour",
}
VPC_PRICES = {
    "PublicIPv4:IdleAddress": "public_ipv4_idle_hour",
    "PublicIPv4:InUseAddress": "public_ipv4_inuse_hour",
}
ELB_PRICES = {  # product family -> our name (the hourly charge of a load balancer)
    "Load Balancer-Application": "alb_hour",
    "Load Balancer-Network": "nlb_hour",
}


def read_csv(url):
    """Open an AWS price CSV and return (version, rows). Rows are read one at a time."""
    text = io.TextIOWrapper(urllib.request.urlopen(url, timeout=120), encoding="utf-8", newline="")
    version = ""
    for _ in range(5):                      # 5 lines of information before the header
        line = next(csv.reader([text.readline()]))
        if line[0] == "Version":
            version = line[1]
    return version, csv.DictReader(text)


def match(usage_type, names):
    """'APS3-EBS:VolumeUsage.gp3' matches 'EBS:VolumeUsage.gp3' (the part after the region code)."""
    for end, key in names.items():
        if usage_type == end or usage_type.endswith("-" + end):
            return key
    return None


def price_entry(r):
    usd, unit = float(r["PricePerUnit"]), r["Unit"]
    if unit == "GiBps-mo":                  # gp3 throughput is listed per GiB/s, we use MiB/s
        usd, unit = usd / 1024, "MiBps-Mo"
    return {"usd": round(usd, 6), "unit": unit, "sku": r["SKU"], "description": r["PriceDescription"]}


def fetch(region):
    instances, other = {}, {}

    version, rows = read_csv(f"{BASE}/AmazonEC2/current/{region}/index.csv")
    for r in rows:
        if r["TermType"] != "OnDemand" or r["Location Type"] != "AWS Region":
            continue
        if r["Product Family"] == "Compute Instance":
            itype = r["Instance Type"]
            if (itype.split(".")[0] in FAMILIES and r["Tenancy"] == "Shared"
                    and r["Operating System"] == "Linux" and r["Pre Installed S/W"] == "NA"
                    and r["CapacityStatus"] == "Used" and r["License Model"] == "No License required"):
                instances[itype] = {
                    "usd_per_hour": float(r["PricePerUnit"]),
                    "vcpu": int(r["vCPU"]),
                    "memory_gib": float(r["Memory"].split()[0].replace(",", "")),
                    "sku": r["SKU"],
                    "description": r["PriceDescription"],
                }
        else:
            key = match(r["usageType"], EC2_PRICES)
            if key and key not in other and float(r["PricePerUnit"]) > 0:
                other[key] = price_entry(r)

    _, rows = read_csv(f"{BASE}/AmazonVPC/current/{region}/index.csv")
    for r in rows:
        key = match(r["usageType"], VPC_PRICES)
        if r["TermType"] == "OnDemand" and key and key not in other:
            other[key] = price_entry(r)

    _, rows = read_csv(f"{BASE}/AWSELB/current/{region}/index.csv")
    for r in rows:
        key = ELB_PRICES.get(r["Product Family"])
        # the load balancer's own hourly charge, e.g. "$0.0239 per Application LoadBalancer-hour"
        # (skip add-ons like "Trust Store unit-hour" and Outposts)
        is_hourly_charge = ("LoadBalancer-hour" in r["PriceDescription"]
                            and "Outposts" not in r["usageType"])
        if key and key not in other and r["TermType"] == "OnDemand" and is_hourly_charge:
            other[key] = price_entry(r)

    return {"region": region, "price_list_version": version,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "instances": instances, "other": other}


def save(region):
    data = fetch(region)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{region}.json").write_text(json.dumps(data, indent=1, sort_keys=True))
    wanted = set(EC2_PRICES.values()) | set(VPC_PRICES.values()) | set(ELB_PRICES.values())
    missing = sorted(wanted - set(data["other"]))
    print(f"{region}: {len(data['instances'])} instance types, {len(data['other'])} other prices"
          + (f", missing {missing}" if missing else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    for reg in (DEFAULT_REGIONS if args.all else [args.region]):
        save(reg)
