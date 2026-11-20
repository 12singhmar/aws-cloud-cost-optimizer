"""Build a scan from real, public AWS CloudWatch data.

Source: Numenta Anomaly Benchmark (NAB), folder data/realAWSCloudwatch
https://github.com/numenta/NAB  (MIT licence)

It contains CPU utilisation of 8 real EC2 instances, recorded by CloudWatch
every 5 minutes for 14 days (2014). We turn each series into hourly values,
the same format our live scanner produces, and save it as a normal scan.

What the dataset does NOT include (so we state it in the scan):
  - instance types  -> we price them as m5.large (an assumption)
  - network traffic -> the idle rule judges these on CPU only
  - disks, IPs, snapshots -> those rules need a live account

Run:  python scripts/import_public_data.py
"""

import csv
import io
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Instance, Metrics, Scan  # noqa: E402

BASE = "https://raw.githubusercontent.com/numenta/NAB/master/data/realAWSCloudwatch/"
FILES = ["24ae8d", "53ea38", "5f5533", "77c1ca", "825cc2", "ac20cd", "c6585a", "fe7f93"]
ASSUMED_TYPE = "m5.large"
OUT = Path(__file__).resolve().parents[1] / "data" / "scans" / "public-nab-ec2.json"


def download(name: str) -> list[tuple[datetime, float]]:
    url = f"{BASE}ec2_cpu_utilization_{name}.csv"
    text = urllib.request.urlopen(url, timeout=60).read().decode()
    return [(datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
             float(r["value"])) for r in csv.DictReader(io.StringIO(text))]


def to_hourly(points: list[tuple[datetime, float]]) -> tuple[datetime, list[float], list[float]]:
    """Group the 5-minute readings by hour: (first hour, hourly averages, hourly maximums).
    This is what CloudWatch returns for Statistics=Average / Maximum with Period=3600."""
    hours: dict[datetime, list[float]] = {}
    for t, v in points:
        hours.setdefault(t.replace(minute=0, second=0), []).append(v)
    ordered = sorted(hours.items())
    return (ordered[0][0], [round(sum(v) / len(v), 3) for _, v in ordered],
            [round(max(v), 3) for _, v in ordered])


def main() -> None:
    instances, metrics, ends = [], {}, []
    for name in FILES:
        points = download(name)
        iid = f"nab-{name}"
        instances.append(Instance(id=iid, name=f"ec2_cpu_utilization_{name}", type=ASSUMED_TYPE,
                                  state="running", launch_time=points[0][0]))
        start, avg, mx = to_hourly(points)
        metrics[iid] = Metrics(start=start, cpu=avg, cpu_max=mx)
        ends.append(points[-1][0])
        print(f"{iid}: {len(points)} readings -> {len(metrics[iid].cpu)} hours")

    scan = Scan(
        id="public-nab-ec2", source="public", account="NAB public dataset", region="us-east-1",
        scanned_at=max(ends),
        description=("Real CPU data of 8 EC2 instances from AWS CloudWatch (14 days, 2014), published in the "
                     "Numenta Anomaly Benchmark (MIT licence). Not our account. The dataset does not include "
                     f"instance types or network traffic, so instances are priced as {ASSUMED_TYPE} and judged "
                     "on CPU only."),
        instances=instances, metrics=metrics)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(scan.model_dump_json(indent=1))
    print("Saved", OUT)


if __name__ == "__main__":
    main()
