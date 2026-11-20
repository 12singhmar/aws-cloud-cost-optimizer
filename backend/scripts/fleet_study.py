"""Fleet study: test our rightsizing rule on 2.6 million REAL virtual machines.

Data: Azure Public Dataset V2 (Microsoft, 2019) - a real 30-day trace of VMs
running in production. File used: vmtable.csv.gz (one row per VM, ~437 MB).
https://github.com/Azure/AzurePublicDataset

Question we answer:
    Many cost tools say "average CPU < 10%  ->  downsize the VM".
    How often would that advice actually hurt the workload?

How we decide "hurt":
    Halving the vCPUs roughly doubles CPU utilisation. The dataset gives, for
    each VM, the 95th percentile of its 5-minute *max* CPU (p95max).
    If 2 x p95max > 100%, the smaller VM would be maxed out in at least 5% of
    all 5-minute windows (about 1 hour 12 min per day) -> we call that harmful.

Rules compared:
    naive       : avg CPU < 10%
    peak-aware  : avg CPU < 10%  AND  p95max < 40%   (this project's rule:
                  after halving, the busy-time CPU stays under 80%)

The file is streamed, never fully stored. Output: data/fleet/azure_study.json

Usage:
    python scripts/fleet_study.py              # streams from GitHub (~437 MB)
    python scripts/fleet_study.py --file vmtable.csv.gz   # use a local copy
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import random
import urllib.request
from pathlib import Path

URL = ("https://github.com/Azure/AzurePublicDataset/releases/download/"
       "dataset-v2/trace_data_vmtable_vmtable.csv.gz")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fleet" / "azure_study.json"

MIN_LIFETIME_S = 7 * 24 * 3600          # same 7-day minimum the app uses
CORES = {"2": 2, "4": 4, "8": 8, "24": 24, ">24": 32}   # >24 assumed 32 (stated)


def _open(path: str | None):
    if path:
        return gzip.open(path, "rt", newline="")
    raw = urllib.request.urlopen(URL, timeout=300)
    return io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8", newline="")


def run(path: str | None, price_per_vcpu_hour: float, sample_size: int = 1500) -> dict:
    rng = random.Random(42)
    total = long_lived = 0
    naive = naive_harm = peak = 0
    naive_cores = peak_cores = 0
    avg_hist = [0] * 10          # avg CPU in 10% buckets (long-lived VMs)
    harm_by_bucket: dict[str, list[int]] = {}   # avg-CPU bucket -> [flagged, harmful]
    sample: list[list[float]] = []
    seen_flag = 0

    for row in csv.reader(_open(path)):
        total += 1
        created, deleted = float(row[3]), float(row[4])
        if deleted - created < MIN_LIFETIME_S:
            continue
        long_lived += 1
        avg, p95 = float(row[6]), float(row[7])
        cores = CORES.get(row[9], 2)
        avg_hist[min(int(avg // 10), 9)] += 1

        if avg < 10:
            naive += 1
            naive_cores += cores
            harmful = 2 * p95 > 100
            naive_harm += harmful
            b = f"{int(avg)}-{int(avg) + 1}%"
            harm_by_bucket.setdefault(b, [0, 0])
            harm_by_bucket[b][0] += 1
            harm_by_bucket[b][1] += harmful
            if p95 < 40:
                peak += 1
                peak_cores += cores
            # reservoir sample of naive-flagged VMs for the scatter chart
            seen_flag += 1
            point = [round(avg, 2), round(p95, 2)]
            if len(sample) < sample_size:
                sample.append(point)
            elif (j := rng.randrange(seen_flag)) < sample_size:
                sample[j] = point
        if total % 250_000 == 0:
            print(f"  {total:,} rows read...")

    def monthly(vcpus_removed: float) -> float:
        return round(vcpus_removed * price_per_vcpu_hour * 730, 2)

    return {
        "dataset": "Azure Public Dataset V2 (2019), vmtable",
        "source_url": URL,
        "vms_total": total,
        "vms_long_lived": long_lived,
        "min_lifetime_days": 7,
        "harm_definition": "after halving vCPUs, 2 x p95(max CPU) > 100%",
        "naive": {
            "rule": "avg CPU < 10%",
            "flagged": naive,
            "harmful": naive_harm,
            "harm_rate": round(naive_harm / naive, 4) if naive else 0,
            "monthly_savings_usd_if_all_applied": monthly(naive_cores / 2),
        },
        "peak_aware": {
            "rule": "avg CPU < 10% AND p95(max CPU) < 40%",
            "flagged": peak,
            "harmful": 0,
            "harm_rate": 0.0,
            "note": "0 harmful by construction: the rule itself uses p95(max). The honest "
                    "question is what the safety check COSTS - see savings_retained. "
                    "Out-of-sample validation of the rule is done by the backtest on "
                    "hourly CloudWatch data (this table has no time series).",
            "monthly_savings_usd_if_all_applied": monthly(peak_cores / 2),
            "savings_retained": round(peak_cores / naive_cores, 4) if naive_cores else 0,
        },
        "price_per_vcpu_hour_usd": price_per_vcpu_hour,
        "price_note": "m5 family On-Demand Linux, ap-south-1, from data/prices",
        "avg_cpu_histogram": [{"bucket": f"{i * 10}-{i * 10 + 10}%", "vms": n}
                              for i, n in enumerate(avg_hist)],
        "harm_by_avg_cpu": [{"bucket": k, "flagged": v[0], "harmful": v[1]}
                            for k, v in sorted(harm_by_bucket.items(),
                                               key=lambda kv: int(kv[0].split("-")[0]))],
        "scatter_sample": {"columns": ["avg_cpu", "p95_max_cpu"], "points": sample},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="local vmtable.csv.gz instead of downloading")
    args = ap.parse_args()
    prices = json.loads((ROOT / "data" / "prices" / "ap-south-1.json").read_text())
    m5 = prices["instances"]["m5.large"]
    per_vcpu = m5["usd_per_hour"] / m5["vcpu"]
    print("Streaming Azure vmtable (this takes a few minutes)...")
    result = run(args.file, per_vcpu)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    n = result["naive"]
    print(f"Done. {result['vms_long_lived']:,} long-lived VMs. Naive rule flagged "
          f"{n['flagged']:,}, of which {n['harmful']:,} ({n['harm_rate']:.1%}) would be harmed.")


if __name__ == "__main__":
    main()
