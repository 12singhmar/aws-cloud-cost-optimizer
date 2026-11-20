"""Usage analysis: what does a server's CPU history tell us?

For each server with hourly CloudWatch data we work out:
  - busy-time CPU (95th percentile of the hourly maximum) and average CPU
  - average CPU for each day of the week
  - quiet windows: hours of the week that were quiet in EVERY week we saw,
    long enough to switch the server off (a schedule)
  - a verdict: Idle / Can follow a schedule / Oversized / Well used
The result can be sent straight to the optimizer as a workload.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from app.models import Instance, Metrics
from app.rules import IDLE_CPU_P95, MIN_HOURS_OF_DATA, p95

QUIET_CPU = 5.0          # an hour is quiet if its maximum CPU stayed under 5%
MIN_WINDOW_HOURS = 4     # shorter gaps are not worth stopping and starting for
MIN_SCHEDULE_HOURS = 20  # suggest a schedule only if it saves at least 20 hours a week
OVERSIZED_PEAK = 35.0    # busy-time CPU under 35%: a smaller type would likely do

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def hour_of_week(m: Metrics, k: int) -> int:
    t = m.start + timedelta(hours=k)
    return t.weekday() * 24 + t.hour


def label(how: int) -> str:
    return f"{DAYS[how // 24]} {how % 24:02d}:00"


def quiet_windows(quiet: list[bool]) -> list[dict]:
    """Group quiet hours of the week into runs. The week wraps around (Sun night -> Mon morning)."""
    if all(quiet):
        return [{"from": "Mon 00:00", "to": "Mon 00:00", "hours": 168}]
    start = next(h for h in range(168) if not quiet[h])        # begin scanning at a busy hour
    windows, run = [], []
    for i in range(1, 169):
        h = (start + i) % 168
        if quiet[h]:
            run.append(h)
        elif run:
            windows.append(run)
            run = []
    if run:
        windows.append(run)
    return [{"from": label(r[0]), "to": label((r[-1] + 1) % 168), "hours": len(r)}
            for r in windows if len(r) >= MIN_WINDOW_HOURS]


def analyze(instance: Instance, m: Optional[Metrics]) -> dict:
    out = {"id": instance.id, "name": instance.name, "type": instance.type, "state": instance.state}
    if m is None or m.start is None:
        return {**out, "verdict": "No data", "reasons": ["No CloudWatch data for this server."]}

    avg = [x for x in m.cpu if x is not None]
    mx_series = m.cpu_max if m.cpu_max else m.cpu
    mx = [x for x in mx_series if x is not None]
    if len(avg) < MIN_HOURS_OF_DATA:
        return {**out, "verdict": "Not enough data",
                "reasons": [f"Only {len(avg)} hours of data; we need 7 days to see a full week."]}

    # Group every hour by its hour of the week (0 = Monday 00:00 ... 167 = Sunday 23:00)
    buckets_avg = [[] for _ in range(168)]
    buckets_max = [[] for _ in range(168)]
    for k in range(len(m.cpu)):
        if m.cpu[k] is None:
            continue
        h = hour_of_week(m, k)
        buckets_avg[h].append(m.cpu[k])
        buckets_max[h].append(mx_series[k] if mx_series[k] is not None else m.cpu[k])
    by_day = []
    for d in range(7):
        vals = [v for h in range(24) for v in buckets_avg[d * 24 + h]]
        by_day.append({"day": DAYS[d], "avg_cpu": round(sum(vals) / len(vals), 1) if vals else None})
    weeks_seen = len(avg) // 168
    # quiet = seen in every week, and never above QUIET_CPU
    quiet = [len(b) >= max(1, weeks_seen) and max(b) < QUIET_CPU for b in buckets_max]
    windows = quiet_windows(quiet)
    quiet_hours = sum(w["hours"] for w in windows)

    busy = p95(mx)
    average = sum(avg) / len(avg)
    reasons, verdict = [], "Well used"
    if p95(avg) < IDLE_CPU_P95:
        verdict = "Idle"
        reasons.append(f"CPU stayed under {IDLE_CPU_P95:g}% in 95% of hours. Nothing seems to run on it.")
    else:
        if quiet_hours >= MIN_SCHEDULE_HOURS:
            verdict = "Can follow a schedule"
            reasons.append(f"{quiet_hours} hours every week were quiet (max CPU under {QUIET_CPU:g}%) in every "
                           "week we saw. It could be stopped then.")
        if busy < OVERSIZED_PEAK:
            if verdict == "Well used":
                verdict = "Oversized"
            reasons.append(f"Even at busy times CPU reached only {busy:.0f}% (95th percentile of hourly max). "
                           "A smaller type would likely cope.")
        if not reasons:
            reasons.append(f"Busy-time CPU is {busy:.0f}% and there are no long quiet periods.")

    return {**out,
            "verdict": verdict, "reasons": reasons,
            "hours": len(avg), "weeks": weeks_seen,
            "from": m.start.isoformat(), "to": (m.start + timedelta(hours=len(m.cpu))).isoformat(),
            "avg_cpu": round(average, 2), "busy_cpu": round(busy, 2), "max_cpu": round(max(mx), 2),
            "by_day": by_day, "quiet_windows": windows, "quiet_hours_per_week": quiet_hours,
            # ready-made input for the optimizer
            "workload": {"name": instance.name or instance.id, "instance_type": instance.type,
                         "peak_cpu": round(busy, 1), "avg_cpu": round(average, 1),
                         "running_hours_per_week": 168,
                         "needed_hours_per_week": 1 if verdict == "Idle" else 168 - quiet_hours}}
