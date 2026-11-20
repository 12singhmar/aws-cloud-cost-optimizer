"""Data classes for a scan (what we read from AWS) and a finding (what we report)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Instance(BaseModel):
    id: str
    name: str = ""
    type: str
    state: str                          # running, stopped, ...
    launch_time: datetime
    stopped_since: Optional[datetime] = None
    volume_ids: list[str] = Field(default_factory=list)


class Volume(BaseModel):
    id: str
    name: str = ""
    type: str                           # gp3, gp2, ...
    size_gb: int
    iops: Optional[int] = None
    throughput: Optional[int] = None    # MiB/s, gp3 only
    state: str                          # in-use or available
    created: datetime
    attached_to: Optional[str] = None


class ElasticIp(BaseModel):
    allocation_id: str
    public_ip: str
    attached_to: Optional[str] = None


class EbsSnapshot(BaseModel):
    id: str
    volume_id: Optional[str] = None
    volume_exists: bool = True
    used_by_ami: bool = False
    size_gb: int
    created: datetime


class Metrics(BaseModel):
    """Hourly CloudWatch values, oldest first. None = no data for that hour."""
    start: Optional[datetime] = None                  # time of the first hour (UTC)
    cpu: list[Optional[float]]                        # hourly average CPU %
    cpu_max: list[Optional[float]] = Field(default_factory=list)   # hourly maximum CPU %
    network_in: list[Optional[float]] = Field(default_factory=list)   # bytes per hour; empty = not recorded


class Scan(BaseModel):
    id: str
    source: str                         # "aws" (live scan) or "public" (public dataset)
    account: str                        # masked, e.g. ********1234
    region: str
    scanned_at: datetime
    description: str = ""               # where the data came from, and any assumptions
    instances: list[Instance] = Field(default_factory=list)
    volumes: list[Volume] = Field(default_factory=list)
    elastic_ips: list[ElasticIp] = Field(default_factory=list)
    snapshots: list[EbsSnapshot] = Field(default_factory=list)
    metrics: dict[str, Metrics] = Field(default_factory=dict)


class Finding(BaseModel):
    rule: str
    resource_id: str
    resource_type: str
    title: str
    why: str
    monthly_cost: float                 # what this waste costs per month
    evidence: dict[str, str]
    calculation: list[str]
    prices_used: list[str]              # AWS price SKUs
    fix: list[str]
