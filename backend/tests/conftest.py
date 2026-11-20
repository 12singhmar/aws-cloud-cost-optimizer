"""Shared test helpers: build tiny snapshots by hand, so each test is readable."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.models import InstanceMetrics, Snapshot, SnapshotMeta  # noqa: E402
from app.pricing import load_pricebook  # noqa: E402

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def flat_metrics(cpu: float, hours: int = 14 * 24, peak: float | None = None,
                 net_kbps: float = 0.0, spikes: dict | None = None) -> InstanceMetrics:
    avg = [cpu] * hours
    mx = [peak if peak is not None else cpu] * hours
    for h, v in (spikes or {}).items():
        avg[h] = v
        mx[h] = v
    return InstanceMetrics(start=NOW - timedelta(hours=hours), cpu_avg=avg, cpu_max=mx,
                           net_in_bytes=[net_kbps * 1024 * 3600] * hours)


def make_snapshot(**parts) -> Snapshot:
    return Snapshot(meta=SnapshotMeta(id="test", source="demo", region="ap-south-1",
                                      collected_at=NOW), **parts)


@pytest.fixture
def pb():
    return load_pricebook("ap-south-1")
