"""How much does one resource cost per month? Returns (dollars, list of calculation lines).

Prices are the region's real AWS prices. These are list prices before any free credits.
"""

from app.prices import HOURS_PER_MONTH

GP3_FREE_IOPS = 3000     # gp3 includes 3,000 IOPS and 125 MiB/s
GP3_FREE_MBPS = 125


def per_month(hourly):
    return hourly * HOURS_PER_MONTH


def disk_cost(size_gb, vtype, iops, throughput, p):
    price = p.get(f"ebs_{vtype}_gb_month")
    if price is None:
        return 0.0, [f"No price for disk type {vtype}"]
    cost = size_gb * price
    lines = [f"{size_gb} GB x ${price} per GB-month = ${cost:.2f}"]
    if vtype == "gp3":
        extra_iops = max(0, (iops or 0) - GP3_FREE_IOPS)
        extra_mbps = max(0, (throughput or 0) - GP3_FREE_MBPS)
        if extra_iops:
            c = extra_iops * p.get("ebs_gp3_iops_month")
            lines.append(f"{extra_iops} extra IOPS = ${c:.2f}")
            cost += c
        if extra_mbps:
            c = extra_mbps * p.get("ebs_gp3_mbps_month")
            lines.append(f"{extra_mbps} extra MiB/s = ${c:.2f}")
            cost += c
    return cost, lines


def monthly_cost(r, p, eip_addresses=()):
    """Cost of one resource. eip_addresses: Elastic IPs (counted on their own, not on the server)."""
    if p is None:
        return 0.0, [f"No prices saved for {r.region}"]
    try:
        return _monthly_cost(r, p, eip_addresses)
    except TypeError:          # a price we need is missing from this region's price file
        return 0.0, [f"Price not available for this {r.kind} in {r.region}"]


def _monthly_cost(r, p, eip_addresses):
    i = r.info

    if r.kind == "instance":
        if r.state != "running":
            return 0.0, ["Stopped: no charge for the server itself (its disks are counted separately)"]
        hourly = p.instance_hourly(i["type"])
        if hourly is None:
            return 0.0, [f"No price for {i['type']}"]
        cost = per_month(hourly)
        lines = [f"{i['type']}: ${hourly} per hour x {HOURS_PER_MONTH} hours = ${cost:.2f}"]
        if i.get("public_ip") and i["public_ip"] not in eip_addresses:
            ip = per_month(p.get("public_ipv4_inuse_hour"))
            lines.append(f"Public IPv4 address: ${ip:.2f}")
            cost += ip
        return cost, lines

    if r.kind == "volume":
        return disk_cost(i["size_gb"], i["type"], i.get("iops"), i.get("throughput"), p)

    if r.kind == "elastic_ip":
        key = "public_ipv4_inuse_hour" if i["attached_to"] else "public_ipv4_idle_hour"
        cost = per_month(p.get(key))
        return cost, [f"${p.get(key)} per hour x {HOURS_PER_MONTH} hours = ${cost:.2f}"]

    if r.kind == "snapshot":
        price = p.get("ebs_snapshot_gb_month")
        cost = i["size_gb"] * price
        return cost, [f"up to {i['size_gb']} GB x ${price} per GB-month = ${cost:.2f} "
                      "(AWS bills only the data stored, so it may be less)"]

    if r.kind == "nat_gateway":
        cost = per_month(p.get("nat_gateway_hour"))
        return cost, [f"${p.get('nat_gateway_hour')} per hour x {HOURS_PER_MONTH} hours = ${cost:.2f} "
                      "(plus a charge per GB of data, not counted here)"]

    if r.kind == "load_balancer":
        key = "nlb_hour" if i["lb_type"] == "network" else "alb_hour"
        cost = per_month(p.get(key))
        return cost, [f"${p.get(key)} per hour x {HOURS_PER_MONTH} hours = ${cost:.2f} "
                      "(plus a usage charge, not counted here)"]

    return 0.0, []
