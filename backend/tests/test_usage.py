import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Instance, Metrics  # noqa: E402
from app.usage import analyze, quiet_windows  # noqa: E402

MONDAY = datetime(2026, 11, 2, tzinfo=timezone.utc)     # a Monday, 00:00
SERVER = Instance(id="i-1", type="m5.large", state="running", launch_time=MONDAY)


def two_weeks(cpu_for_hour):
    """Build 14 days of hourly CPU from a function of (day 0-6, hour 0-23)."""
    cpu = [cpu_for_hour((k // 24) % 7, k % 24) for k in range(14 * 24)]
    return Metrics(start=MONDAY, cpu=cpu, cpu_max=cpu)


def test_office_hours_server_gets_a_schedule():
    m = two_weeks(lambda d, h: 40.0 if d < 5 and 9 <= h < 18 else 1.0)
    r = analyze(SERVER, m)
    assert r["verdict"] == "Can follow a schedule"
    assert r["quiet_hours_per_week"] == 168 - 5 * 9          # everything except weekdays 9-18
    assert r["workload"]["needed_hours_per_week"] == 45


def test_weekend_window_wraps_around_the_week():
    m = two_weeks(lambda d, h: 1.0 if d >= 5 else 30.0)
    windows = analyze(SERVER, m)["quiet_windows"]
    assert windows == [{"from": "Sat 00:00", "to": "Mon 00:00", "hours": 48}]


def test_short_quiet_gaps_are_ignored():
    quiet = [False] * 168
    for h in range(10, 13):          # only 3 hours
        quiet[h] = True
    assert quiet_windows(quiet) == []


def test_one_busy_week_cancels_a_quiet_hour():
    # Saturday quiet in week 1 but busy in week 2 -> not reliably quiet
    cpu = [1.0 if (k // 24) % 7 == 5 and k < 168 else 30.0 for k in range(14 * 24)]
    r = analyze(SERVER, Metrics(start=MONDAY, cpu=cpu, cpu_max=cpu))
    assert r["quiet_hours_per_week"] == 0


def test_idle_and_oversized():
    assert analyze(SERVER, two_weeks(lambda d, h: 0.5))["verdict"] == "Idle"
    assert analyze(SERVER, two_weeks(lambda d, h: 20.0))["verdict"] == "Oversized"
    assert analyze(SERVER, two_weeks(lambda d, h: 60.0))["verdict"] == "Well used"


def test_needs_a_full_week():
    m = Metrics(start=MONDAY, cpu=[5.0] * 100, cpu_max=[5.0] * 100)
    assert analyze(SERVER, m)["verdict"] == "Not enough data"
