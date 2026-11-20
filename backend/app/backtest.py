"""Backtest: "If we had run this tool one week ago, would its advice have held?"

Same idea as testing a weather forecast on past days. We split each
instance's hourly history in two:

    |---- week 1: decide ----|---- the rest: check ----|

1. Run the idle / rightsizing logic using ONLY week 1.
2. Replay the remaining hours and see what would have happened.

Rightsizing check: on the smaller type, CPU % ~ old CPU % x (old vCPU / new vCPU).
Count hours where that projected *max* CPU goes above 90% (the server would
have been struggling).
Idle check: did the instance stay idle, or did real work show up later?
"""

from __future__ import annotations

from app.config import MIN_METRIC_HOURS
from app.models import Snapshot
from app.pricing import PriceBook
from app.rules import is_idle, rightsize_decision, trimmed
from app.stats import percentile, present

TRAIN_HOURS = MIN_METRIC_HOURS     # 7 days to decide
MIN_TEST_HOURS = 72                # at least 3 days to check
STRAIN_CPU = 90.0                  # above this the server is struggling


def _downsample(values: list[float], points: int = 84) -> list[float]:
    """Max over buckets: keeps the spikes visible on a small chart."""
    if len(values) <= points:
        return [round(v, 1) for v in values]
    step = len(values) / points
    return [round(max(values[int(k * step): int((k + 1) * step)] or [0]), 1) for k in range(points)]


def backtest_instance(itype: str, cpu_avg: list, cpu_max: list, net: list,
                      pb: PriceBook) -> dict | None:
    if len(cpu_avg) < TRAIN_HOURS + MIN_TEST_HOURS:
        return None
    tr_avg, te_avg = present(cpu_avg[:TRAIN_HOURS]), present(cpu_avg[TRAIN_HOURS:])
    tr_max, te_max = present(cpu_max[:TRAIN_HOURS]), present(cpu_max[TRAIN_HOURS:])
    tr_net, te_net = present(net[:TRAIN_HOURS]), present(net[TRAIN_HOURS:])
    base = {"train_hours": len(tr_avg), "test_hours": len(te_avg)}

    idle_then = is_idle(tr_avg, tr_net)[0]
    if idle_then:
        still, p95, kbps = is_idle(te_avg, te_net)
        return {**base, "rule_id": "ec2-idle", "advice_week1": "Stop (idle)",
                "verdict": "Held up" if still else "Would have hurt",
                "detail": (f"Stayed idle: CPU p95 {p95:.1f}%, network {kbps:.2f} KB/s."
                           if still else
                           f"Work appeared later (CPU p95 {p95:.1f}%, network {kbps:.2f} KB/s). "
                           "Stopping it would have broken something."),
                "series": {"label": "Actual CPU % (hourly max)", "limit": None,
                           "train": _downsample(tr_max), "test": _downsample(te_max)}}

    d = rightsize_decision(itype, tr_avg, tr_max, pb)
    if not d:
        return {**base, "rule_id": None, "advice_week1": "No change",
                "verdict": "No advice", "detail": "Week 1 gave no reason to change this instance.",
                "series": None}
    projected = [v * d["factor"] for v in te_max]
    strained = sum(1 for v in projected if v > STRAIN_CPU)
    p95 = percentile(projected, 95)
    share = strained / len(projected) if projected else 0
    if strained == 0 and p95 < 80:
        verdict, detail = "Held up", f"On a {d['target']} the busiest hours would reach " \
                                     f"{p95:.0f}% (p95). No hour above {STRAIN_CPU:.0f}%."
    elif share <= 0.01:
        verdict, detail = "Borderline", f"{strained} hour(s) above {STRAIN_CPU:.0f}% on a " \
                                        f"{d['target']}. Probably fine, watch it."
    else:
        verdict, detail = "Would have hurt", f"{strained} of {len(projected)} hours " \
                                             f"({share:.0%}) above {STRAIN_CPU:.0f}% on a {d['target']}."
    return {**base, "rule_id": "ec2-rightsize",
            "advice_week1": f"Downsize {itype} → {d['target']}",
            "verdict": verdict, "detail": detail, "strained_hours": strained,
            "series": {"label": f"Projected CPU % on {d['target']} (hourly max)",
                       "limit": STRAIN_CPU,
                       "train": _downsample([v * d["factor"] for v in tr_max]),
                       "test": _downsample(projected)}}


def backtest_snapshot(s: Snapshot, pb: PriceBook) -> dict[str, dict]:
    out = {}
    for i in s.instances:
        m = s.metrics.get(i.id)
        if i.state != "running" or m is None or not pb.has_instance(i.type):
            continue
        avg, mx, net = trimmed(m)
        r = backtest_instance(i.type, avg, mx, net, pb)
        if r:
            out[i.id] = {"instance": i.id, "name": i.name, "type": i.type, **r}
    return out
