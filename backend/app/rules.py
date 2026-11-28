"""Waste rules. Each rule looks at the scan and returns findings: things that cost money for nothing.

 1. Unattached disk          a disk not connected to any server
 2. Unused Elastic IP        a public IP not attached to anything
 3. Stopped server           off, but its disks are still billed
 4. Old snapshot             a backup whose original disk was deleted
 5. Idle NAT gateway         sent no data in 7 days
 6. Empty load balancer      no servers behind it
 7. Idle server              CPU under 3% for 7 days
 8. Oversized server         CPU never busy for 7 days, a smaller size would do
"""

import math

from app.costs import disk_cost, monthly_cost
from app.models import Finding
from app.prices import HOURS_PER_MONTH, load_prices

MIN_HOURS = 7 * 24          # the CPU rules need one full week of data
IDLE_CPU = 3.0              # idle: 95% of hours under 3% CPU
OVERSIZED_CPU = 35.0        # oversized: 95% of hourly peaks under 35% CPU
SIZES = ["nano", "micro", "small", "medium", "large", "xlarge", "2xlarge", "4xlarge", "8xlarge"]


def p95(values):
    """95th percentile: the value that 95% of the numbers are below."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def days_ago(scan, when):
    return (scan.scanned_at - when).days if when else None


def one_size_smaller(itype, p):
    family, _, size = itype.partition(".")
    if size not in SIZES or SIZES.index(size) == 0:
        return None
    smaller = f"{family}.{SIZES[SIZES.index(size) - 1]}"
    return smaller if p.instance_hourly(smaller) else None


def find_waste(scan):
    findings, notes = [], []
    by_id = {r.id: r for r in scan.resources}
    eips = {r.info["public_ip"] for r in scan.resources if r.kind == "elastic_ip"}

    def add(rule, r, title, why, evidence, fix_action=None, fix_label="", fix_warning="", cost=None, calc=None):
        if cost is None:
            cost, calc = monthly_cost(r, load_prices(r.region), eips)
        findings.append(Finding(rule=rule, kind=r.kind, region=r.region, resource_id=r.id, title=title,
                                why=why, monthly_cost=round(cost, 2), evidence=evidence, calculation=calc,
                                fix_action=fix_action, fix_label=fix_label, fix_warning=fix_warning))

    for r in scan.resources:
        i = r.info
        if r.kind == "volume" and r.state == "available":
            add("Unattached disk", r, f"Spare disk {r.name or r.id} ({i['size_gb']} GB)",
                "This disk is not connected to any server but is billed every month.",
                {"Size": f"{i['size_gb']} GB {i['type']}", "Created": f"{days_ago(scan, r.created)} days ago"},
                "delete_volume", "Back up and delete",
                "A snapshot is taken first, then the disk is deleted.")

        elif r.kind == "elastic_ip" and not i["attached_to"]:
            add("Unused Elastic IP", r, f"Unused IP address {i['public_ip']}",
                "AWS charges for every public IPv4 address, even when it is not used.",
                {"IP address": i["public_ip"], "Attached to": "nothing"},
                "release_ip", "Release IP", "The address goes back to AWS and cannot be recovered.")

        elif r.kind == "instance" and r.state == "stopped":
            disks = [by_id[v] for v in i["volume_ids"] if v in by_id]
            p = load_prices(r.region)
            cost, calc = 0.0, []
            for d in disks:
                c, lines = disk_cost(d.info["size_gb"], d.info["type"], d.info.get("iops"),
                                     d.info.get("throughput"), p)
                cost += c
                calc += [f"{d.id}: {line}" for line in lines]
            if cost > 0:
                add("Stopped server", r, f"Stopped server {r.name or r.id} still paying for its disks",
                    "A stopped server costs nothing itself, but its disks are still billed.",
                    {"Type": i["type"], "Stopped since": i.get("stopped_since") or "unknown",
                     "Disks": ", ".join(i["volume_ids"])},
                    "terminate", "Delete server",
                    "The server and its disks are deleted. This cannot be undone.", cost, calc)

        elif r.kind == "snapshot" and not i["volume_exists"] and not i["used_by_ami"]:
            ours = i.get("made_by_us")
            add("Old snapshot", r,
                f"Backup we made before deleting {i['volume_id']}" if ours else f"Backup {r.id} of a deleted disk",
                "This app took this backup before deleting the disk. Keep it until you are sure, then delete it."
                if ours else "The disk this backup came from no longer exists. Delete it if you don't need it.",
                {"Original disk": f"{i['volume_id']} (deleted)", "Size": f"{i['size_gb']} GB",
                 "Created": f"{days_ago(scan, r.created)} days ago"},
                "delete_snapshot", "Delete backup", "The backup is deleted. This cannot be undone.")

        elif r.kind == "nat_gateway" and i["bytes_sent_7d"] == 0:
            add("Idle NAT gateway", r, f"NAT gateway {r.name or r.id} sent no data in 7 days",
                "NAT gateways cost money every hour, even when nothing uses them.",
                {"Data sent (7 days)": "0 bytes", "Created": f"{days_ago(scan, r.created)} days ago"},
                "delete_nat", "Delete NAT gateway",
                "Servers in private subnets lose internet access. Its IP stays and can be released after.")

        elif r.kind == "load_balancer" and i["targets"] == 0:
            add("Empty load balancer", r, f"Load balancer {r.name} has no servers behind it",
                "A load balancer costs money every hour even with nothing to send traffic to.",
                {"Type": i["lb_type"], "Servers behind it": "0"},
                "delete_lb", "Delete load balancer", "The load balancer is deleted.")

        elif r.kind == "instance" and r.state == "running":
            m = scan.metrics.get(r.id)
            avg = [x for x in (m.cpu_avg if m else []) if x is not None]
            peaks = [x for x in (m.cpu_max if m else []) if x is not None]
            if len(avg) < MIN_HOURS:
                notes.append(f"{r.name or r.id} ({r.region}): {len(avg)} hours of CPU data so far. "
                             f"Idle and oversized checks need {MIN_HOURS} hours (7 days).")
                continue
            if p95(avg) < IDLE_CPU:
                add("Idle server", r, f"Idle server {r.name or r.id} ({i['type']})",
                    f"CPU stayed under {IDLE_CPU:g}% in 95% of the last {len(avg)} hours.",
                    {"CPU (95% of hours under)": f"{p95(avg):.1f}%", "Hours checked": str(len(avg))},
                    "stop", "Stop server", "The server stops. Its disks are kept and it can be started again.")
            elif peaks and p95(peaks) < OVERSIZED_CPU:
                p = load_prices(r.region)
                smaller = one_size_smaller(i["type"], p)
                if smaller:
                    now, after = p.instance_hourly(i["type"]), p.instance_hourly(smaller)
                    saving = (now - after) * HOURS_PER_MONTH
                    add("Oversized server", r, f"{r.name or r.id}: {i['type']} could be {smaller}",
                        f"Even at its busiest, CPU stayed under {OVERSIZED_CPU:g}%. Half the size would still cope.",
                        {"Busiest hours CPU": f"{p95(peaks):.1f}%", "Hours checked": str(len(peaks))},
                        cost=saving, calc=[f"{i['type']} ${now}/h - {smaller} ${after}/h = "
                                           f"${now - after:.4f}/h x {HOURS_PER_MONTH} h = ${saving:.2f}"],
                        fix_label="Change type in the AWS console (needs a restart)")

    findings.sort(key=lambda f: -f.monthly_cost)
    return findings, notes


def report(scan):
    """Everything the account page shows for one scan."""
    eips = {r.info["public_ip"] for r in scan.resources if r.kind == "elastic_ip"}
    inventory, total = [], 0.0
    for r in scan.resources:
        cost, calc = monthly_cost(r, load_prices(r.region), eips)
        total += cost
        inventory.append({"kind": r.kind, "region": r.region, "id": r.id, "name": r.name,
                          "state": r.state, "monthly_cost": round(cost, 2), "calculation": calc,
                          "detail": describe(r)})
    inventory.sort(key=lambda x: -x["monthly_cost"])
    findings, notes = find_waste(scan)
    by_region = {}
    for item in inventory:
        by_region[item["region"]] = by_region.get(item["region"], 0) + item["monthly_cost"]
    return {
        "scan": {"id": scan.id, "account": scan.account, "fake_aws": scan.fake_aws,
                 "scanned_at": scan.scanned_at, "regions": len(scan.regions), "errors": scan.errors},
        "monthly_total": round(total, 2),
        "monthly_waste": round(sum(f.monthly_cost for f in findings), 2),
        "by_region": {k: round(v, 2) for k, v in sorted(by_region.items(), key=lambda kv: -kv[1])},
        "inventory": inventory,
        "findings": [f.model_dump() for f in findings],
        "notes": notes,
        "buckets_without_lifecycle": scan.buckets_without_lifecycle,
    }


def describe(r):
    i = r.info
    return {
        "instance": lambda: f"{i['type']}, {r.state}",
        "volume": lambda: f"{i['size_gb']} GB {i['type']}, {'attached' if i['attached_to'] else 'not attached'}",
        "elastic_ip": lambda: f"{i['public_ip']}, {'in use' if i['attached_to'] else 'not used'}",
        "snapshot": lambda: f"{i['size_gb']} GB backup",
        "nat_gateway": lambda: f"{i['bytes_sent_7d'] / 1e9:.2f} GB sent in 7 days",
        "load_balancer": lambda: f"{i['lb_type']}, {i['targets']} servers behind it",
    }.get(r.kind, lambda: "")()
