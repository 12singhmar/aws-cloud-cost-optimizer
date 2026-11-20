"""The five waste rules and the cost formulas they use.

1. Unattached EBS volume      - a disk not connected to any server
2. Unused Elastic IP          - a reserved public IP attached to nothing
3. Stopped instance           - no compute charge, but its disks are still billed
4. Orphaned snapshot          - a backup whose original disk was deleted
5. Idle instance              - running for 7+ days with almost no CPU or network
"""

from __future__ import annotations

import math

from app.models import Finding, Instance, Scan, Volume
from app.prices import HOURS_PER_MONTH, Prices

# Idle instance thresholds
MIN_HOURS_OF_DATA = 7 * 24      # one full week, so weekends are included
IDLE_CPU_P95 = 3.0              # 95% of hours below 3% CPU
IDLE_NETWORK_KBPS = 5.0         # average inbound traffic below 5 KB/s

GP3_FREE_IOPS = 3000            # gp3 includes 3,000 IOPS and 125 MiB/s for free
GP3_FREE_MBPS = 125


# ---------- cost formulas ----------

def volume_cost(v: Volume, p: Prices) -> tuple[float, list[str], list[str]]:
    key = f"ebs_{v.type}_gb_month"
    if key not in p.other:
        return 0.0, [f"No price for volume type {v.type}"], []
    cost = v.size_gb * p.get(key)
    calc = [f"{v.size_gb} GB x ${p.get(key)} per GB-month = ${cost:.2f}"]
    skus = [p.sku(key)]
    if v.type == "gp3":
        extra_iops = max(0, (v.iops or 0) - GP3_FREE_IOPS)
        extra_mbps = max(0, (v.throughput or 0) - GP3_FREE_MBPS)
        if extra_iops:
            c = extra_iops * p.get("ebs_gp3_iops_month")
            calc.append(f"{extra_iops} extra IOPS x ${p.get('ebs_gp3_iops_month')} = ${c:.2f}")
            skus.append(p.sku("ebs_gp3_iops_month"))
            cost += c
        if extra_mbps:
            c = extra_mbps * p.get("ebs_gp3_mbps_month")
            calc.append(f"{extra_mbps} extra MiB/s x ${p.get('ebs_gp3_mbps_month')} = ${c:.2f}")
            skus.append(p.sku("ebs_gp3_mbps_month"))
            cost += c
    return cost, calc, skus


def instance_cost(i: Instance, p: Prices) -> float:
    if i.state != "running" or not p.has_instance(i.type):
        return 0.0
    return p.instance_hourly(i.type) * HOURS_PER_MONTH


def ip_cost(p: Prices) -> float:
    return p.get("public_ipv4_idle_hour") * HOURS_PER_MONTH


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else 0.0


def days_ago(scan: Scan, when) -> int:
    return (scan.scanned_at - when).days


# ---------- rules ----------

def unattached_volumes(scan: Scan, p: Prices) -> list[Finding]:
    out = []
    for v in scan.volumes:
        if v.state != "available":
            continue
        cost, calc, skus = volume_cost(v, p)
        out.append(Finding(
            rule="Unattached EBS volume", resource_id=v.id, resource_type="EBS volume",
            title=f"Unattached disk {v.name or v.id} ({v.size_gb} GB {v.type})",
            why="This disk is not connected to any server but is billed every month.",
            monthly_cost=round(cost, 2),
            evidence={"State": v.state, "Size": f"{v.size_gb} GB {v.type}",
                      "Created": f"{days_ago(scan, v.created)} days ago"},
            calculation=calc, prices_used=skus,
            fix=[f"aws ec2 create-snapshot --volume-id {v.id} --description \"backup before delete\"",
                 f"aws ec2 delete-volume --volume-id {v.id}"]))
    return out


def unused_elastic_ips(scan: Scan, p: Prices) -> list[Finding]:
    out = []
    for ip in scan.elastic_ips:
        if ip.attached_to:
            continue
        cost = ip_cost(p)
        out.append(Finding(
            rule="Unused Elastic IP", resource_id=ip.allocation_id, resource_type="Elastic IP",
            title=f"Unused Elastic IP {ip.public_ip}",
            why="AWS charges for every public IPv4 address, even when it is not attached to anything.",
            monthly_cost=round(cost, 2),
            evidence={"IP address": ip.public_ip, "Attached to": "nothing"},
            calculation=[f"${p.get('public_ipv4_idle_hour')} per hour x {HOURS_PER_MONTH} hours = ${cost:.2f}"],
            prices_used=[p.sku("public_ipv4_idle_hour")],
            fix=[f"aws ec2 release-address --allocation-id {ip.allocation_id}"]))
    return out


def stopped_instances(scan: Scan, p: Prices) -> list[Finding]:
    out = []
    volumes = {v.id: v for v in scan.volumes}
    for i in scan.instances:
        if i.state != "stopped":
            continue
        cost, calc, skus = 0.0, [], []
        for vid in i.volume_ids:
            if vid in volumes:
                c, lines, s = volume_cost(volumes[vid], p)
                cost += c
                calc += [f"{vid}: {line}" for line in lines]
                skus += s
        if cost == 0:
            continue
        since = f"{days_ago(scan, i.stopped_since)} days" if i.stopped_since else "unknown"
        out.append(Finding(
            rule="Stopped instance", resource_id=i.id, resource_type="EC2 instance",
            title=f"Stopped server {i.name or i.id} still paying for its disks",
            why="A stopped server has no compute charge, but its disks keep costing money.",
            monthly_cost=round(cost, 2),
            evidence={"State": "stopped", "Stopped for": since, "Disks": ", ".join(i.volume_ids)},
            calculation=calc, prices_used=skus,
            fix=[f"aws ec2 create-image --instance-id {i.id} --name backup-{i.id}",
                 f"aws ec2 terminate-instances --instance-ids {i.id}"]))
    return out


def orphaned_snapshots(scan: Scan, p: Prices) -> list[Finding]:
    out = []
    price = p.get("ebs_snapshot_gb_month")
    for s in scan.snapshots:
        if s.volume_exists or s.used_by_ami:
            continue
        cost = s.size_gb * price
        out.append(Finding(
            rule="Orphaned snapshot", resource_id=s.id, resource_type="EBS snapshot",
            title=f"Snapshot {s.id} of a deleted disk",
            why="The disk this backup came from no longer exists. Check if the backup is still needed.",
            monthly_cost=round(cost, 2),
            evidence={"Original disk": f"{s.volume_id} (deleted)", "Size": f"{s.size_gb} GB",
                      "Created": f"{days_ago(scan, s.created)} days ago"},
            calculation=[f"up to {s.size_gb} GB x ${price} per GB-month = ${cost:.2f} "
                         "(AWS bills only the data actually stored, so the real cost may be lower)"],
            prices_used=[p.sku("ebs_snapshot_gb_month")],
            fix=[f"aws ec2 delete-snapshot --snapshot-id {s.id}"]))
    return out


def idle_instances(scan: Scan, p: Prices, notes: list[str]) -> list[Finding]:
    out = []
    for i in scan.instances:
        if i.state != "running":
            continue
        m = scan.metrics.get(i.id)
        cpu = [x for x in (m.cpu if m else []) if x is not None]
        net = [x for x in (m.network_in if m else []) if x is not None]
        if len(cpu) < MIN_HOURS_OF_DATA:
            notes.append(f"{i.name or i.id}: only {len(cpu)} hours of CPU data, need "
                         f"{MIN_HOURS_OF_DATA} (7 days) before we can say it is idle.")
            continue
        cpu_p95 = p95(cpu)
        net_kbps = (sum(net) / len(net)) / 3600 / 1024 if net else 0.0
        if cpu_p95 >= IDLE_CPU_P95 or net_kbps >= IDLE_NETWORK_KBPS:
            continue
        if not p.has_instance(i.type):
            notes.append(f"{i.name or i.id}: no price for {i.type} in {p.region}.")
            continue
        cost = instance_cost(i, p)
        out.append(Finding(
            rule="Idle instance", resource_id=i.id, resource_type="EC2 instance",
            title=f"Idle server {i.name or i.id} ({i.type})",
            why=f"Over {len(cpu) // 24} days, CPU stayed below {IDLE_CPU_P95}% in 95% of hours "
                "and there was almost no network traffic.",
            monthly_cost=round(cost, 2),
            evidence={"CPU (95th percentile)": f"{cpu_p95:.2f}%",
                      "Average network in": f"{net_kbps:.2f} KB/s",
                      "Hours of data": str(len(cpu))},
            calculation=[f"{i.type}: ${p.instance_hourly(i.type)} per hour x {HOURS_PER_MONTH} hours = ${cost:.2f}"],
            prices_used=[p.instance_sku(i.type)],
            fix=[f"aws ec2 stop-instances --instance-ids {i.id}"]))
    return out


# ---------- report ----------

def build_report(scan: Scan, p: Prices) -> dict:
    notes: list[str] = []
    findings = (unattached_volumes(scan, p) + unused_elastic_ips(scan, p) + stopped_instances(scan, p)
                + orphaned_snapshots(scan, p) + idle_instances(scan, p, notes))
    findings.sort(key=lambda f: -f.monthly_cost)

    # what everything we scanned costs per month (list price, before free-tier credits)
    total = sum(instance_cost(i, p) for i in scan.instances)
    total += sum(volume_cost(v, p)[0] for v in scan.volumes)
    total += sum(s.size_gb * p.get("ebs_snapshot_gb_month") for s in scan.snapshots)
    total += len(scan.elastic_ips) * ip_cost(p)

    return {
        "scan": scan.model_dump(mode="json", include={"id", "source", "account", "region", "scanned_at"}),
        "counts": {"instances": len(scan.instances), "volumes": len(scan.volumes),
                   "elastic_ips": len(scan.elastic_ips), "snapshots": len(scan.snapshots)},
        "monthly_cost": round(total, 2),
        "monthly_waste": round(sum(f.monthly_cost for f in findings), 2),
        "findings": [f.model_dump() for f in findings],
        "notes": notes,
        "price_list_version": p.version,
    }
