"""Cost model: "how much does this one resource cost per month?"

Used in three places, so the numbers always agree:
  - rules (how much would we save?)
  - the overview (monthly run-rate of everything scanned)
  - the bill check (our estimate vs what AWS actually charged)

Every function returns (usd_per_month, calculation_steps, prices_used).
These are list prices before free-tier credits.
"""

from __future__ import annotations

from app.config import HOURS_PER_MONTH
from app.models import Address, Bucket, CalcStep, EbsSnapshot, Instance, PriceRef, Volume
from app.pricing import PriceBook

Cost = tuple[float, list[CalcStep], list[PriceRef]]

GP3_FREE_IOPS = 3000      # gp3 includes 3,000 IOPS and 125 MiB/s at no extra cost
GP3_FREE_MBPS = 125


def volume_cost(v: Volume, pb: PriceBook) -> Cost:
    key = f"ebs_{v.type}_gb_month"
    storage = v.size_gb * pb.get(key)
    steps = [CalcStep(text=f"Storage: {v.size_gb} GB x ${pb.get(key)}/GB-month", usd=storage)]
    refs = [pb.ref(key)]
    total = storage
    if v.type == "gp3":
        extra_iops = max(0, (v.iops or GP3_FREE_IOPS) - GP3_FREE_IOPS)
        extra_mbps = max(0, (v.throughput or GP3_FREE_MBPS) - GP3_FREE_MBPS)
        if extra_iops:
            c = extra_iops * pb.get("ebs_gp3_iops_month")
            steps.append(CalcStep(text=f"Extra IOPS: {extra_iops} above the free 3,000 "
                                       f"x ${pb.get('ebs_gp3_iops_month')}", usd=c))
            refs.append(pb.ref("ebs_gp3_iops_month"))
            total += c
        if extra_mbps:
            c = extra_mbps * pb.get("ebs_gp3_mbps_month")
            steps.append(CalcStep(text=f"Extra throughput: {extra_mbps} MiB/s above the free 125 "
                                       f"x ${pb.get('ebs_gp3_mbps_month')}", usd=c))
            refs.append(pb.ref("ebs_gp3_mbps_month"))
            total += c
    return round(total, 4), steps, refs


def instance_cost(i: Instance, pb: PriceBook) -> Cost:
    """Compute charge only (its volumes are counted separately)."""
    if i.state != "running":
        return 0.0, [CalcStep(text="Not running: no compute charge", usd=0.0)], []
    hourly = pb.instance_hourly(i.type)
    total = hourly * HOURS_PER_MONTH
    return round(total, 4), [CalcStep(text=f"{i.type}: ${hourly}/hour x {HOURS_PER_MONTH} hours",
                                      usd=total)], [pb.instance_ref(i.type)]


def public_ip_cost(pb: PriceBook, idle: bool) -> Cost:
    key = "public_ipv4_idle_hour" if idle else "public_ipv4_inuse_hour"
    hourly = pb.get(key)
    total = hourly * HOURS_PER_MONTH
    label = "Idle" if idle else "In-use"
    return round(total, 4), [CalcStep(text=f"{label} public IPv4: ${hourly}/hour x "
                                           f"{HOURS_PER_MONTH} hours", usd=total)], [pb.ref(key)]


def address_cost(a: Address, pb: PriceBook) -> Cost:
    return public_ip_cost(pb, idle=a.associated_with is None)


def snapshot_cost(s: EbsSnapshot, pb: PriceBook) -> Cost:
    """Upper bound: a snapshot stores at most the volume size (usually less)."""
    price = pb.get("ebs_snapshot_gb_month")
    total = s.size_gb * price
    return round(total, 4), [CalcStep(text=f"At most {s.size_gb} GB x ${price}/GB-month "
                                           "(snapshots store only used blocks, so real cost "
                                           "is usually lower)", usd=total)], \
        [pb.ref("ebs_snapshot_gb_month")]


def bucket_cost(b: Bucket, pb: PriceBook) -> Cost:
    price = pb.get("s3_standard_gb_month")
    pending_gb = sum(u.size_bytes for u in b.incomplete_uploads) / 2**30
    gb = b.size_gb + pending_gb
    total = gb * price
    return round(total, 4), [CalcStep(text=f"{gb:.3f} GB x ${price}/GB-month (S3 Standard)",
                                      usd=total)], [pb.ref("s3_standard_gb_month")]
