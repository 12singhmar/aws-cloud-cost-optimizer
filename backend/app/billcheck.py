"""Bill check: compare our cost estimates with what AWS actually billed.

Most cost tools show an estimate and stop there. We close the loop using the
CUR 2.0 billing export (see scripts/load_bill.py), which lists real charges
per resource, per hour.

For a fair comparison we compare *rates*, not totals:
    estimated = (our monthly estimate / 730) x hours the bill shows it was used
    actual    = sum of the bill's charges for that resource
    error %   = (estimated - actual) / actual

Only matching charge types are compared (e.g. for an instance, compute hours
only - not its disks, which are separate resources in the bill).
"""

from __future__ import annotations

from app.config import HOURS_PER_MONTH
from app.costs import address_cost, bucket_cost, instance_cost, snapshot_cost, volume_cost
from app.models import Snapshot
from app.pricing import PriceBook, PriceNotFound

# usage-type fragments that belong to each kind of resource
USAGE_MATCH = {
    "EC2 instance": ("BoxUsage",),
    "EBS volume": ("EBS:VolumeUsage", "EBS:VolumeP-IOPS", "EBS:VolumeP-Throughput"),
    "EBS snapshot": ("EBS:SnapshotUsage",),
    "Elastic IP": ("PublicIPv4",),
    "S3 bucket": ("TimedStorage",),
}


def _our_resources(s: Snapshot, pb: PriceBook):
    for i in s.instances:
        try:
            yield i.id, i.name, "EC2 instance", pb.instance_monthly(i.type), [i.id]
        except PriceNotFound:
            continue
    for v in s.volumes:
        yield v.id, v.tags.get("Name", ""), "EBS volume", volume_cost(v, pb)[0], [v.id]
    for sn in s.snapshots:
        yield sn.id, sn.tags.get("Name", ""), "EBS snapshot", snapshot_cost(sn, pb)[0], [sn.id]
    for a in s.addresses:
        # The bill may label an IPv4 charge by allocation id or by the address itself.
        yield a.allocation_id, a.public_ip, "Elastic IP", address_cost(a, pb)[0], \
            [a.allocation_id, a.public_ip]
    for b in s.buckets:
        yield b.name, b.name, "S3 bucket", bucket_cost(b, pb)[0], [b.name]


def compare(s: Snapshot, bill: dict, pb: PriceBook) -> dict:
    billed = bill["resources"]
    rows = []
    for rid, name, kind, monthly, keys in _our_resources(s, pb):
        entry = next((billed[k] for k in keys if k in billed), None)
        if entry is None:
            continue
        frags = USAGE_MATCH[kind]
        actual = sum(c for ut, c in entry["usage_types"].items() if any(f in ut for f in frags))
        hours = entry["usage_hours"]
        estimated = monthly / HOURS_PER_MONTH * hours
        if actual > 0:
            err = (estimated - actual) / actual
        else:
            err = None
        rows.append({
            "resource_id": rid, "name": name, "kind": kind, "hours": hours,
            "estimated_usd": round(estimated, 4), "actual_usd": round(actual, 4),
            "error_pct": None if err is None else round(err * 100, 1),
            "note": _explain(kind, err),
        })
    rows.sort(key=lambda r: -r["actual_usd"])
    errs = [abs(r["error_pct"]) for r in rows if r["error_pct"] is not None]
    return {
        "source": bill.get("source"),
        "synthetic": bill.get("synthetic", False),
        "period_start": bill.get("period_start"),
        "period_end": bill.get("period_end"),
        "matched": len(rows),
        "mean_abs_error_pct": round(sum(errs) / len(errs), 1) if errs else None,
        "total_estimated": round(sum(r["estimated_usd"] for r in rows), 4),
        "total_actual": round(sum(r["actual_usd"] for r in rows), 4),
        "rows": rows,
        "unmatched_bill_resources": sorted(set(billed) - {k for _, _, _, _, ks in
                                                          _our_resources(s, pb) for k in ks})[:50],
    }


def _explain(kind: str, err: float | None) -> str:
    if err is None:
        return "Billed $0 (free tier or credits applied before this line)."
    if abs(err) <= 0.02:
        return "Matches the bill."
    if kind == "EBS snapshot" and err > 0:
        return "Expected: we price the full volume size; AWS bills only the blocks stored."
    if kind == "S3 bucket":
        return "S3 size is measured once a day; the bill averages every hour."
    return "Investigate: price or usage hours differ."
