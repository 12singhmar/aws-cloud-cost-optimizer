"""Cost checker: what will a setup cost per month, and how long will free credits last?

Works without an AWS account: it only uses the saved AWS prices.
"""

from pydantic import BaseModel, Field

from app.prices import HOURS_PER_MONTH, available_regions, load_prices

WEEKS_PER_MONTH = HOURS_PER_MONTH / 168      # 4.345
DAYS_PER_MONTH = HOURS_PER_MONTH / 24        # 30.4


class Server(BaseModel):
    instance_type: str = "t3.micro"
    count: int = Field(1, ge=1, le=100)
    hours_per_day: float = Field(24, gt=0, le=24)
    days_per_week: int = Field(7, ge=1, le=7)
    disk_gb: int = Field(8, ge=0, le=16000)
    disk_type: str = "gp3"
    public_ip: bool = True


class Setup(BaseModel):
    region: str = "ap-south-1"
    servers: list[Server] = Field(default_factory=lambda: [Server()])
    nat_gateways: int = Field(0, ge=0, le=20)
    load_balancers: int = Field(0, ge=0, le=20)
    credits_usd: float = Field(100, ge=0)


def price_setup(setup, p):
    """Cost lines for a setup in the region of prices p. Returns (lines, total) or None if a price is missing."""
    lines = []
    for s in setup.servers:
        hourly = p.instance_hourly(s.instance_type)
        disk_price = p.get(f"ebs_{s.disk_type}_gb_month")
        if hourly is None or disk_price is None:
            return None
        hours = s.hours_per_day * s.days_per_week * WEEKS_PER_MONTH
        lines.append({"item": f"{s.count} x {s.instance_type}, {s.hours_per_day:g} h/day, {s.days_per_week} days/week",
                      "monthly": hourly * hours * s.count,
                      "math": f"${hourly}/h x {hours:.0f} h x {s.count}"})
        if s.disk_gb:
            lines.append({"item": f"{s.count} x {s.disk_gb} GB {s.disk_type} disk",
                          "monthly": s.disk_gb * disk_price * s.count,
                          "math": f"{s.disk_gb} GB x ${disk_price} x {s.count} (billed even when the server is off)"})
        if s.public_ip:
            ip = p.get("public_ipv4_inuse_hour")
            lines.append({"item": f"{s.count} x public IPv4 address",
                          "monthly": ip * HOURS_PER_MONTH * s.count,
                          "math": f"${ip}/h x {HOURS_PER_MONTH} h x {s.count}"})
    if setup.nat_gateways:
        nat = p.get("nat_gateway_hour")
        lines.append({"item": f"{setup.nat_gateways} x NAT gateway", "monthly": nat * HOURS_PER_MONTH * setup.nat_gateways,
                      "math": f"${nat}/h x {HOURS_PER_MONTH} h (plus data charges)"})
    if setup.load_balancers:
        lb = p.get("alb_hour")
        lines.append({"item": f"{setup.load_balancers} x load balancer",
                      "monthly": lb * HOURS_PER_MONTH * setup.load_balancers,
                      "math": f"${lb}/h x {HOURS_PER_MONTH} h (plus usage charges)"})
    for line in lines:
        line["monthly"] = round(line["monthly"], 2)
    return lines, round(sum(line["monthly"] for line in lines), 2)


def check(setup):
    p = load_prices(setup.region)
    if p is None:
        raise ValueError(f"No prices for {setup.region}")
    try:
        priced = price_setup(setup, p)
    except TypeError:
        priced = None
    if priced is None:
        raise ValueError("Unknown instance type or disk type for this region")
    lines, total = priced

    # same setup in every region we have prices for
    regions = []
    for r in available_regions():
        try:
            other = price_setup(setup, load_prices(r))
        except TypeError:          # this region's price file is missing a price we need
            other = None
        if other:
            regions.append({"region": r, "monthly": other[1]})
    regions.sort(key=lambda x: x["monthly"])

    # simple ways to pay less, each worked out with the same prices
    tips = []
    gp2 = [s for s in setup.servers if s.disk_type == "gp2" and s.disk_gb]
    if gp2:
        saving = sum(s.disk_gb * (p.get("ebs_gp2_gb_month") - p.get("ebs_gp3_gb_month")) * s.count for s in gp2)
        tips.append({"tip": "Use gp3 disks instead of gp2: same or better speed, cheaper per GB.",
                     "saving": round(saving, 2)})
    always_on = [s for s in setup.servers if s.hours_per_day * s.days_per_week == 168]
    if always_on:
        # switched off at night and at weekends: 12 hours a day, 5 days a week = 60 of 168 hours
        saving = sum(p.instance_hourly(s.instance_type) * (168 - 60) * WEEKS_PER_MONTH * s.count for s in always_on)
        tips.append({"tip": "If the servers are only needed in the day on weekdays, stopping them at night "
                            "and at weekends (12 h x 5 days) cuts their hours from 168 to 60 a week.",
                     "saving": round(saving, 2)})
    if setup.nat_gateways:
        tips.append({"tip": "A NAT gateway is often not needed for a small project: servers in a public "
                            "subnet can reach the internet directly.",
                     "saving": round(p.get("nat_gateway_hour") * HOURS_PER_MONTH * setup.nat_gateways, 2)})

    per_day = total / DAYS_PER_MONTH
    return {
        "region": setup.region,
        "lines": lines,
        "monthly_total": total,
        "per_day": round(per_day, 2),
        "credits_usd": setup.credits_usd,
        "credits_last_days": round(setup.credits_usd / per_day) if per_day else None,
        "regions": regions,
        "tips": tips,
        "price_list_version": p.version,
    }
