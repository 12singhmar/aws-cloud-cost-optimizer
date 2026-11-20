"""Data shapes used across the app.

Two groups:
1. Snapshot*  - what we collected from an AWS account (the input).
2. Finding... - what the analyser concludes (the output).

A *snapshot* is a frozen copy of an account at one moment. We analyse snapshots,
not the live account, so every result can be reproduced later (and the demo
works in a viva with no internet or AWS keys).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Input: account snapshot
# --------------------------------------------------------------------------


class SnapshotMeta(BaseModel):
    id: str
    source: Literal["demo", "aws"]
    region: str
    account: str = "unknown"          # masked, e.g. "********1234"
    collected_at: datetime            # analysis treats this moment as "now"
    metric_days: int = 14
    notes: str = ""


class Instance(BaseModel):
    id: str
    name: str = ""
    type: str
    state: str                        # running | stopped | ...
    launch_time: datetime
    state_since: Optional[datetime] = None   # when it entered the current state
    volume_ids: list[str] = Field(default_factory=list)
    public_ip: Optional[str] = None
    tags: dict[str, str] = Field(default_factory=dict)


class Volume(BaseModel):
    id: str
    name: str = ""
    type: str                         # gp3 | gp2 | st1 | sc1 | standard
    size_gb: int
    iops: Optional[int] = None
    throughput: Optional[int] = None  # MiB/s (gp3 only)
    state: str                        # in-use | available
    create_time: datetime
    attached_to: Optional[str] = None
    tags: dict[str, str] = Field(default_factory=dict)


class Address(BaseModel):
    allocation_id: str
    public_ip: str
    associated_with: Optional[str] = None   # instance / network interface id
    tags: dict[str, str] = Field(default_factory=dict)


class EbsSnapshot(BaseModel):
    id: str
    volume_id: Optional[str] = None
    volume_exists: bool = True
    used_by_ami: bool = False         # deleting it would break that machine image
    size_gb: int
    start_time: datetime
    description: str = ""
    tags: dict[str, str] = Field(default_factory=dict)


class IncompleteUpload(BaseModel):
    key: str
    initiated: datetime
    size_bytes: int


class Bucket(BaseModel):
    name: str
    size_gb: float = 0.0
    has_lifecycle: bool = False
    incomplete_uploads: list[IncompleteUpload] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)


class InstanceMetrics(BaseModel):
    """Hourly CloudWatch data. Index 0 = oldest hour. None = no datapoint."""
    start: datetime
    cpu_avg: list[Optional[float]]
    cpu_max: list[Optional[float]]
    net_in_bytes: list[Optional[float]] = Field(default_factory=list)  # Sum per hour


class Snapshot(BaseModel):
    meta: SnapshotMeta
    instances: list[Instance] = Field(default_factory=list)
    volumes: list[Volume] = Field(default_factory=list)
    addresses: list[Address] = Field(default_factory=list)
    snapshots: list[EbsSnapshot] = Field(default_factory=list)
    buckets: list[Bucket] = Field(default_factory=list)
    metrics: dict[str, InstanceMetrics] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Output: findings
# --------------------------------------------------------------------------


class Evidence(BaseModel):
    label: str
    value: str


class CalcStep(BaseModel):
    """One line of the savings calculation, shown to the user as-is."""
    text: str
    usd: Optional[float] = None


class PriceRef(BaseModel):
    key: str
    usd: float
    unit: str
    sku: str
    description: str


class Finding(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    resource_id: str
    resource_name: str = ""
    resource_type: str
    title: str
    summary: str                       # one plain-English sentence
    monthly_savings: Optional[float]   # None = we cannot estimate honestly
    priority: Literal["High", "Medium", "Low"]
    confidence: Literal["High", "Medium", "Low"]
    confidence_reason: str
    risk: Literal["Low", "Medium", "High"]
    risk_reason: str
    evidence: list[Evidence]
    calculation: list[CalcStep]
    prices_used: list[PriceRef]
    check_commands: list[str]          # read-only commands to confirm
    fix_steps: list[str]
    backtest: Optional[dict] = None
    # "blocked" = the rule fired, but replaying history showed the advice
    # would have hurt. Shown separately, never counted as savings.
    status: Literal["active", "blocked"] = "active"
    blocked_reason: Optional[str] = None


class Notice(BaseModel):
    level: Literal["info", "warning"]
    resource_id: Optional[str] = None
    text: str
