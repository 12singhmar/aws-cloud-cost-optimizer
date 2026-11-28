"""Data classes. A scan is a list of everything we found in the account, in every region."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Resource(BaseModel):
    kind: str            # instance, volume, elastic_ip, snapshot, nat_gateway, load_balancer
    region: str
    id: str
    name: str = ""
    state: str = ""
    created: Optional[datetime] = None
    info: dict = Field(default_factory=dict)   # details that depend on the kind (size, type, ...)


class Metrics(BaseModel):
    """Hourly CPU of one server from CloudWatch, oldest hour first. None = no data."""
    cpu_avg: list[Optional[float]]
    cpu_max: list[Optional[float]]


class Scan(BaseModel):
    id: str
    account: str                     # masked, e.g. ********1234
    scanned_at: datetime
    fake_aws: bool = False           # True when scanned in test mode (not a real account)
    regions: list[str]               # regions we looked at
    resources: list[Resource] = Field(default_factory=list)
    metrics: dict[str, Metrics] = Field(default_factory=dict)          # instance id -> CPU
    buckets_without_lifecycle: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)                    # regions we could not read


class Finding(BaseModel):
    rule: str
    kind: str
    region: str
    resource_id: str
    title: str
    why: str
    monthly_cost: float              # money lost per month if nothing is done
    evidence: dict[str, str]
    calculation: list[str]
    fix_action: Optional[str] = None # action the app can do (see fixes.py), None = manual
    fix_label: str = ""
    fix_warning: str = ""
