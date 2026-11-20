"""Runs every rule over a snapshot and builds the overview numbers.

Steps:
1. Remove Waste-Lab tags (so the detector cannot see the answer key).
2. Run each rule.
3. Attach backtest results to instance findings.
4. Add notices for things we could NOT judge (e.g. not enough data).
5. Total up the monthly run-rate and potential savings.
"""

from __future__ import annotations

from app import config as C
from app.backtest import backtest_snapshot
from app.costs import (address_cost, bucket_cost, instance_cost, public_ip_cost, snapshot_cost,
                       volume_cost)
from app.models import Notice, Snapshot
from app.pricing import PriceNotFound, load_pricebook
from app.rules import RULES, Context, enough_data, metric_window

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def strip_lab_tags(s: Snapshot) -> Snapshot:
    s = s.model_copy(deep=True)
    for group in (s.instances, s.volumes, s.addresses, s.snapshots, s.buckets):
        for r in group:
            r.tags = {k: v for k, v in r.tags.items() if not k.startswith(C.LAB_TAG_PREFIX)}
    return s


def run_rate(s: Snapshot, pb) -> tuple[float, dict[str, float], dict[str, float]]:
    """Estimated monthly cost of everything scanned (list price, before credits)."""
    per_type: dict[str, float] = {}
    per_resource: dict[str, float] = {}

    def add(kind: str, rid: str, usd: float) -> None:
        per_type[kind] = per_type.get(kind, 0.0) + usd
        per_resource[rid] = per_resource.get(rid, 0.0) + usd

    for i in s.instances:
        try:
            add("EC2 compute", i.id, instance_cost(i, pb)[0])
        except PriceNotFound:
            pass
        if i.public_ip and i.state == "running" and not any(
                a.associated_with == i.id for a in s.addresses):
            add("Public IPv4", i.id, public_ip_cost(pb, idle=False)[0])
    for v in s.volumes:
        add("EBS volumes", v.id, volume_cost(v, pb)[0])
    for a in s.addresses:
        add("Public IPv4", a.allocation_id, address_cost(a, pb)[0])
    for sn in s.snapshots:
        add("EBS snapshots", sn.id, snapshot_cost(sn, pb)[0])
    for b in s.buckets:
        add("S3 storage", b.name, bucket_cost(b, pb)[0])
    return round(sum(per_type.values()), 2), per_type, per_resource


def analyze(raw: Snapshot) -> dict:
    s = strip_lab_tags(raw)
    pb = load_pricebook(s.meta.region)
    ctx = Context(pb=pb, now=s.meta.collected_at, notices=[])

    # Things we cannot judge get a notice instead of a guess.
    for i in s.instances:
        if not pb.has_instance(i.type):
            ctx.notices.append(Notice(level="warning", resource_id=i.id,
                                      text=f"No price for {i.type} in {s.meta.region}; skipped. "
                                           "Add its family to FAMILIES in fetch_prices.py."))
        if i.state == "running":
            cpu, _, _, total = metric_window(s.metrics.get(i.id))
            if not enough_data(cpu, total):
                ctx.notices.append(Notice(
                    level="info", resource_id=i.id,
                    text=f"{i.name or i.id}: only {len(cpu)} hours of CPU data "
                         f"(need {C.MIN_METRIC_HOURS}, mostly complete). Idle/rightsizing "
                         "rules skipped - we do not treat missing data as zero."))

    findings = []
    for rule in RULES:
        findings.extend(rule(s, ctx))

    # Backtest gate: advice must survive a replay of history.
    # bt["rule_id"] is what the week-1 data alone would have advised.
    backtests = backtest_snapshot(s, pb)
    for f in findings:
        bt = backtests.get(f.resource_id)
        if bt and bt["rule_id"] == f.rule_id:
            f.backtest = bt
            if bt["verdict"] == "Would have hurt":
                f.status = "blocked"
                f.blocked_reason = ("Backtest failed: advice from the first week would have "
                                    "hurt later. " + bt["detail"])

    findings.sort(key=lambda f: (f.status == "blocked", PRIORITY_ORDER[f.priority],
                                 -(f.monthly_savings or 0)))
    active = [f for f in findings if f.status == "active"]
    total, per_type, per_resource = run_rate(s, pb)
    savings = round(sum(f.monthly_savings or 0 for f in active), 2)

    return {
        "snapshot": s.meta.model_dump(mode="json"),
        "pricing": {"region": pb.region, "version": pb.version, "fetched_at": pb.fetched_at},
        "summary": {
            "resources_scanned": (len(s.instances) + len(s.volumes) + len(s.addresses)
                                  + len(s.snapshots) + len(s.buckets)),
            "monthly_run_rate": total,
            "potential_savings": savings,
            "savings_share": round(savings / total, 4) if total else 0,
            "findings": len(active),
            "blocked": len(findings) - len(active),
            "by_priority": {p: sum(1 for f in active if f.priority == p)
                            for p in ("High", "Medium", "Low")},
        },
        "spend_by_type": [{"type": k, "usd": round(v, 2)}
                          for k, v in sorted(per_type.items(), key=lambda kv: -kv[1])],
        "resource_costs": {k: round(v, 4) for k, v in per_resource.items()},
        "findings": [f.model_dump(mode="json") for f in findings],
        "notices": [n.model_dump() for n in ctx.notices],
        "backtests": list(backtests.values()),
    }
