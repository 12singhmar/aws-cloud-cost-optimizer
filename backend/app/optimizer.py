"""The optimization engine.

Input: one workload (a server type, how long it runs, how busy it is, what it
needs). Output: the cheapest plan that still meets those needs, built from
real AWS prices, with every step explained.

The levers are applied one after another, each starting from the result of the
previous one, so a saving is never counted twice:

  1. Rightsize      cheapest x86 type that still fits peak CPU and memory
  2. ARM            same check, but allowing Graviton (ARM) types
  3. Pricing        on-demand with a schedule  vs  reserved for 1 or 3 years
  4. Storage        gp2 disk -> gp3 disk with the same performance
  5. Region         same plan in the cheapest other region
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.prices import HOURS_PER_MONTH, available_regions, load_prices

WEEKS_PER_MONTH = HOURS_PER_MONTH / 168     # 4.345
TARGET_PEAK_CPU = 70.0                      # after resizing, busy-time CPU should stay under 70%
BURST_MARGIN = 0.8                          # use at most 80% of a burstable type's CPU-credit baseline

# CPU-credit baseline per vCPU for t3 / t3a / t4g (AWS burstable instance docs)
BURST_BASELINE = {"nano": 5, "micro": 10, "small": 20, "medium": 20, "large": 30, "xlarge": 40, "2xlarge": 40}
BURSTABLE = ("t3", "t3a", "t4g")
RESERVED_YEARS = {"1yr_no_upfront": 1, "1yr_all_upfront": 1, "3yr_all_upfront": 3}
RESERVED_LABEL = {"1yr_no_upfront": "1-year reservation, no upfront",
                  "1yr_all_upfront": "1-year reservation, paid upfront",
                  "3yr_all_upfront": "3-year reservation, paid upfront"}


class Workload(BaseModel):
    name: str = "My server"
    region: str = "ap-south-1"
    instance_type: str = "m5.xlarge"
    count: int = Field(1, ge=1, le=1000)
    running_hours_per_week: float = Field(168, gt=0, le=168)   # how long it runs today
    needed_hours_per_week: float = Field(168, gt=0, le=168)    # how long it really has to run
    peak_cpu: Optional[float] = Field(None, ge=0, le=100)      # busy-time CPU %, e.g. p95 of hourly max
    avg_cpu: Optional[float] = Field(None, ge=0, le=100)
    memory_needed_gb: Optional[float] = Field(None, gt=0)      # None = keep the current memory
    storage_gb: int = Field(0, ge=0)
    storage_type: str = "gp2"
    arm_ok: bool = False
    commit_years: int = Field(0, ge=0, le=3)                   # 0 = no commitment
    region_flexible: bool = False


# ---------------------------------------------------------------- helpers

def family_size(itype: str) -> tuple[str, str]:
    family, _, size = itype.partition(".")
    return family, size


def storage_cost(prices, gb: int, vtype: str, extra_iops: int = 0, extra_mbps: int = 0) -> float:
    key = f"ebs_{vtype}_gb_month"
    if gb == 0 or key not in prices.other:
        return 0.0
    cost = gb * prices.get(key)
    if vtype == "gp3":
        cost += extra_iops * prices.get("ebs_gp3_iops_month") + extra_mbps * prices.get("ebs_gp3_mbps_month")
    return cost


def fits(info: dict, itype: str, need_vcpu: float, need_mem: float, avg_cpu: Optional[float],
         cur_vcpu: int, arm_ok: bool) -> tuple[bool, str]:
    """Can this instance type run the workload? Returns (ok, reason if not)."""
    if info["arm"] and not arm_ok:
        return False, "ARM not allowed"
    if info["vcpu"] < need_vcpu:
        return False, f"needs {need_vcpu:.1f} vCPU"
    if info["memory_gib"] < need_mem:
        return False, f"needs {need_mem:g} GiB memory"
    family, size = family_size(itype)
    if family in BURSTABLE:
        if avg_cpu is None:
            return False, "burstable needs average CPU to check credits"
        baseline = BURST_BASELINE.get(size)
        projected_avg = avg_cpu * cur_vcpu / info["vcpu"]
        if baseline is None or projected_avg > baseline * BURST_MARGIN:
            return False, f"average CPU {projected_avg:.0f}% too high for its {baseline}% credit baseline"
    return True, ""


def monthly_on_demand(prices, itype: str, hours_per_week: float, count: int) -> float:
    return prices.instance_hourly(itype) * hours_per_week * WEEKS_PER_MONTH * count


def reserved_monthly(info: dict, term: str, count: int) -> Optional[float]:
    """A reservation is paid for every hour of the month, whether the server runs or not."""
    t = info.get("reserved", {}).get(term)
    if not t:
        return None
    years = RESERVED_YEARS[term]
    return (t["upfront"] / (years * 12) + t["hourly"] * HOURS_PER_MONTH) * count


def money(v: float) -> str:
    return f"${v:,.2f}"


# ---------------------------------------------------------------- engine

def optimize(w: Workload) -> dict:
    p = load_prices(w.region)
    if not p.has_instance(w.instance_type):
        raise ValueError(f"{w.instance_type} is not in the price list for {w.region}")
    needed = min(w.needed_hours_per_week, w.running_hours_per_week)
    cur = p.instances[w.instance_type]
    steps, warnings = [], []

    # Baseline: what it costs today
    base_compute = monthly_on_demand(p, w.instance_type, w.running_hours_per_week, w.count)
    base_storage = storage_cost(p, w.storage_gb, w.storage_type) * w.count
    baseline = base_compute + base_storage

    state = {"type": w.instance_type, "compute": base_compute, "storage": base_storage,
             "pricing": "On-demand", "hours": w.running_hours_per_week, "region": w.region}

    # ---- 1 + 2. Rightsize (x86 only), then allow ARM ----
    need_mem = w.memory_needed_gb or cur["memory_gib"]
    candidates = []
    if w.peak_cpu is None:
        steps.append(skip("rightsize", "Rightsize",
                          "No CPU data, so we cannot tell if a smaller server would cope. "
                          "Use Usage Analysis or enter the busy-time CPU."))
    else:
        need_vcpu = cur["vcpu"] * w.peak_cpu / TARGET_PEAK_CPU
        for itype, info in p.instances.items():
            ok, why = fits(info, itype, need_vcpu, need_mem, w.avg_cpu, cur["vcpu"], arm_ok=True)
            candidates.append({"type": itype, "vcpu": info["vcpu"], "memory_gib": info["memory_gib"],
                               "arm": info["arm"], "category": info["category"],
                               "hourly": info["usd_per_hour"], "fits": ok, "reason": why})
        candidates.sort(key=lambda c: c["hourly"])
        details = [
            f"Busy-time CPU is {w.peak_cpu:.0f}% of {cur['vcpu']} vCPU, so the work needs about "
            f"{cur['vcpu'] * w.peak_cpu / 100:.2f} vCPU.",
            f"To keep busy-time CPU under {TARGET_PEAK_CPU:.0f}%, the server needs at least {need_vcpu:.2f} vCPU "
            f"and {need_mem:g} GiB memory.",
        ]
        if need_vcpu > cur["vcpu"]:
            warnings.append(f"{w.instance_type} looks too small: busy-time CPU {w.peak_cpu:.0f}% is above "
                            f"{TARGET_PEAK_CPU:.0f}%. Consider a bigger server.")
        steps.append(choose_type(p, w, state, candidates, arm=False, details=details))
        steps.append(choose_type(p, w, state, candidates, arm=True, details=[]))

    # ---- 3. Pricing model: schedule on-demand vs reserve ----
    steps.append(choose_pricing(p, w, state, needed))

    # ---- 4. Storage: gp2 -> gp3 ----
    steps.append(choose_storage(p, w, state))

    # ---- 5. Region ----
    steps.append(choose_region(w, state))

    final = state["compute"] + state["storage"]
    return {
        "workload": w.model_dump(),
        "baseline_monthly": round(baseline, 2),
        "optimized_monthly": round(final, 2),
        "saving_monthly": round(baseline - final, 2),
        "saving_percent": round((baseline - final) / baseline * 100, 1) if baseline else 0,
        "plan": {"instance_type": state["type"], "pricing": state["pricing"],
                 "hours_per_week": state["hours"], "region": state["region"],
                 "storage_type": "gp3" if w.storage_type in ("gp2", "gp3") and w.storage_gb else w.storage_type},
        "steps": steps,
        "candidates": [c for c in candidates if c["fits"]][:8],
        "warnings": warnings,
        "price_list_version": p.version,
    }


def skip(lever: str, title: str, reason: str) -> dict:
    return {"lever": lever, "title": title, "applied": False, "saving": 0.0, "details": [reason]}


def choose_type(p, w: Workload, state: dict, candidates: list, arm: bool, details: list) -> dict:
    lever, title = ("arm", "Switch to ARM (Graviton)") if arm else ("rightsize", "Rightsize")
    if arm and not w.arm_ok:
        return skip(lever, title, "ARM not allowed. Graviton types are often ~20% cheaper but the software "
                                  "must run on ARM (most Linux software, Python, Node and Java do).")
    pool = [c for c in candidates if c["fits"] and (arm or not c["arm"])]
    if not pool:
        return skip(lever, title, "No instance type in this region meets the CPU and memory needs.")
    best = pool[0]
    now_hourly = p.instance_hourly(state["type"])
    if best["hourly"] >= now_hourly:
        return {"lever": lever, "title": title, "applied": False, "saving": 0.0,
                "details": details + [f"{state['type']} is already the cheapest type that fits."]}
    before, old_type = state["compute"], state["type"]
    state["type"] = best["type"]
    state["compute"] = monthly_on_demand(p, best["type"], state["hours"], w.count)
    scaled_peak = w.peak_cpu * p.instances[w.instance_type]["vcpu"] / best["vcpu"]
    return {"lever": lever, "title": title, "applied": True, "saving": round(before - state["compute"], 2),
            "from": old_type, "to": best["type"],
            "details": details + [
                f"Cheapest type that fits: {best['type']} ({best['vcpu']} vCPU, {best['memory_gib']:g} GiB, "
                f"{best['category'].lower()}) at {money(best['hourly'])}/hour vs {money(now_hourly)}/hour.",
                f"Expected busy-time CPU on {best['type']}: about {scaled_peak:.0f}%.",
                f"Monthly compute: {money(before)} -> {money(state['compute'])}.",
            ]}


def choose_pricing(p, w: Workload, state: dict, needed: float) -> dict:
    info = p.instances[state["type"]]
    hourly = info["usd_per_hour"]
    before = state["compute"]
    options = [{"name": f"On-demand, running {needed:g} h/week",
                "monthly": monthly_on_demand(p, state["type"], needed, w.count), "kind": "schedule"}]
    for term, years in RESERVED_YEARS.items():
        if w.commit_years >= years:
            m = reserved_monthly(info, term, w.count)
            if m is not None:
                options.append({"name": RESERVED_LABEL[term], "monthly": m, "kind": term})
    best = min(options, key=lambda o: o["monthly"])

    details = []
    if needed < state["hours"]:
        details.append(f"It runs {state['hours']:g} h/week but is only needed {needed:g} h/week. "
                       f"Stopping it the rest of the time removes {state['hours'] - needed:g} paid hours a week.")
    full_month = hourly * HOURS_PER_MONTH * w.count
    for o in options[1:]:
        breakeven = o["monthly"] / full_month * 168
        details.append(f"{o['name']}: {money(o['monthly'])}/month whether it runs or not. "
                       f"Worth it only if the server runs more than {breakeven:.0f} h/week "
                       f"({breakeven / 168:.0%} of the time).")
    if w.commit_years == 0:
        details.append("No commitment allowed, so reservations were not considered.")
    details.append(f"Cheapest option: {best['name']} at {money(best['monthly'])}/month.")

    if best["kind"] == "schedule":
        state["hours"] = needed
        state["pricing"] = "On-demand" + (" with a schedule" if needed < 168 else "")
    else:
        state["hours"] = 168
        state["pricing"] = RESERVED_LABEL[best["kind"]]
        if needed < 168:
            details.append("With a reservation the hours are already paid for, so there is no point "
                           "stopping it on a schedule.")
    state["compute"] = best["monthly"]
    saving = before - best["monthly"]
    return {"lever": "pricing", "title": "Schedule or reserve", "applied": saving > 0.005,
            "saving": round(max(saving, 0), 2), "details": details, "options":
            [{"name": o["name"], "monthly": round(o["monthly"], 2), "chosen": o is best} for o in options]}


def choose_storage(p, w: Workload, state: dict) -> dict:
    if not w.storage_gb:
        return skip("storage", "Disk type", "No disk entered.")
    if w.storage_type != "gp2":
        return skip("storage", "Disk type", f"Disk is already {w.storage_type}.")
    # Keep the same performance: gp2 gives 3 IOPS per GB (min 100, max 16,000) and its
    # throughput is IOPS x 256 KiB (max 250 MiB/s). gp3 includes 3,000 IOPS and 125 MiB/s,
    # anything above that is paid separately.
    gp2_iops = min(16000, max(100, 3 * w.storage_gb))
    gp2_mbps = min(250, round(gp2_iops * 256 / 1024))
    extra_iops = max(0, gp2_iops - 3000)
    extra_mbps = max(0, gp2_mbps - 125)
    before = state["storage"]
    after = storage_cost(p, w.storage_gb, "gp3", extra_iops, extra_mbps) * w.count
    if after >= before:
        return skip("storage", "Disk type", "gp3 would not be cheaper for this disk.")
    state["storage"] = after
    return {"lever": "storage", "title": "Disk type gp2 to gp3", "applied": True,
            "saving": round(before - after, 2), "details": [
                f"gp2 {w.storage_gb} GB gives {gp2_iops:,} IOPS and up to {gp2_mbps} MiB/s.",
                f"gp3 includes 3,000 IOPS and 125 MiB/s; to match we add {extra_iops:,} IOPS and "
                f"{extra_mbps} MiB/s.",
                f"Disk cost: {money(before)} -> {money(after)} per month. The change can be done live "
                "with no downtime (Elastic Volumes).",
            ]}


def choose_region(w: Workload, state: dict) -> dict:
    comparison = []
    for region in available_regions():
        rp = load_prices(region)
        if not rp.has_instance(state["type"]):
            continue
        info = rp.instances[state["type"]]
        if state["pricing"].startswith("On-demand"):
            compute = monthly_on_demand(rp, state["type"], state["hours"], w.count)
        else:
            term = next(k for k, v in RESERVED_LABEL.items() if v == state["pricing"])
            compute = reserved_monthly(info, term, w.count)
            if compute is None:
                continue
        disk = "gp3" if w.storage_type == "gp2" else w.storage_type
        storage = state["storage"] if region == state["region"] else storage_cost(rp, w.storage_gb, disk) * w.count
        comparison.append({"region": region, "monthly": round(compute + storage, 2)})
    comparison.sort(key=lambda r: r["monthly"])
    current = next((r for r in comparison if r["region"] == state["region"]), None)
    result = {"lever": "region", "title": "Region", "applied": False, "saving": 0.0,
              "comparison": comparison, "details": []}
    if not w.region_flexible:
        result["details"].append("Region change not allowed (data location, latency for your users). "
                                 "The comparison below is for information only.")
        return result
    best = comparison[0]
    if current is None or best["monthly"] >= current["monthly"]:
        result["details"].append(f"{state['region']} is already the cheapest region for this plan.")
        return result
    saving = current["monthly"] - best["monthly"]
    result.update(applied=True, saving=round(saving, 2))
    result["details"].append(f"The same plan costs {money(best['monthly'])} in {best['region']} vs "
                             f"{money(current['monthly'])} in {state['region']}. Check latency for your users "
                             "and data rules before moving.")
    state["region"] = best["region"]
    state["compute"] -= saving   # keep totals consistent: attribute the difference to compute+storage
    return result
