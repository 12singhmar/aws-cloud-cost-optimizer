"""All thresholds in one place, so they are easy to explain and to change.

Each number has a short reason. If an examiner asks "why 7 days?", the answer
is written right here.
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
LAB_DIR = DATA_DIR / "labs"
BILL_DIR = DATA_DIR / "bills"
PRICE_DIR = DATA_DIR / "prices"
FLEET_FILE = DATA_DIR / "fleet" / "azure_study.json"

# Tags starting with this prefix are used only by the Waste Lab scripts.
# The analyser deletes them before looking at a resource, so the detector
# can never "peek" at the answer.
LAB_TAG_PREFIX = "ccx-"

HOURS_PER_MONTH = 730       # AWS's own convention (365 * 24 / 12)

# Need at least a full week of hourly data: covers weekday + weekend patterns.
MIN_METRIC_HOURS = 7 * 24
# A metric-based rule also needs most hours present (gaps = agent/instance off).
MIN_METRIC_COVERAGE = 0.8

# Idle instance: practically nothing happening, CPU *and* network.
IDLE_CPU_P95 = 3.0          # % - 95% of hours below 3% CPU
IDLE_NET_AVG_KBPS = 5.0     # KB/s average inbound traffic

# Rightsizing (non-burstable families): halving vCPUs ~doubles CPU %.
# Our rule: 95th percentile of the hourly MAX CPU < 40%, so after halving
# the busy-time CPU should stay under 80% (20% safety margin).
RIGHTSIZE_P95_MAX = 40.0
RIGHTSIZE_SAFE_AFTER = 80.0

# Burstable (t3/t3a/t4g) instances earn CPU credits at a "baseline" rate.
# Downsizing is safe only if average CPU stays below the smaller size's
# baseline (with margin). Source: AWS burstable performance instance docs.
BURSTABLE_BASELINE = {
    "nano": 5.0, "micro": 10.0, "small": 20.0, "medium": 20.0,
    "large": 30.0, "xlarge": 40.0, "2xlarge": 40.0,
}
BURSTABLE_MARGIN = 0.8      # use only 80% of the baseline

# Age-based rules (days). 7 days = long enough to not be "work in progress".
UNATTACHED_VOLUME_DAYS = 7
STOPPED_INSTANCE_DAYS = 7
ORPHAN_SNAPSHOT_DAYS = 7
ABANDONED_UPLOAD_DAYS = 7
LARGE_BUCKET_GB = 50        # only nag about lifecycle rules for big buckets

# Priority bands by monthly savings (USD). Small on purpose: student accounts.
PRIORITY_HIGH_USD = 20.0
PRIORITY_MEDIUM_USD = 2.0
