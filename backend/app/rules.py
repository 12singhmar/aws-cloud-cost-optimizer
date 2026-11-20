"""The 7 waste-detection rules.

Each rule is a plain function:  rule(snapshot, ctx) -> list[Finding]
and is registered in RULES at the bottom. To add a rule, write a function
and add it to the list - nothing else changes (open/closed principle).

Every finding carries: evidence (what we saw), calculation (how we got the
dollar figure, line by line), prices_used (official AWS SKUs), read-only
commands to double-check, and fix steps. Nothing is a black box.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from app import config as C
from app.costs import address_cost, bucket_cost, instance_cost, snapshot_cost, volume_cost
from app.models import (CalcStep, Evidence, Finding, Instance, InstanceMetrics, Notice,
                        Snapshot)
from app.pricing import PriceBook
from app.stats import mean, percentile, present

SIZE_LADDER = ["nano", "micro", "small", "medium", "large", "xlarge", "2xlarge",
               "4xlarge", "8xlarge", "12xlarge", "16xlarge", "24xlarge"]
BURSTABLE = ("t3", "t3a", "t4g")


@dataclass
class Context:
    pb: PriceBook
    now: datetime
    notices: list[Notice]

    def days_since(self, t: Optional[datetime]) -> float:
        return (self.now - t).total_seconds() / 86400 if t else 0.0


def priority_for(usd: Optional[float]) -> str:
    if usd is None:
        return "Low"
    if usd >= C.PRIORITY_HIGH_USD:
        return "High"
    return "Medium" if usd >= C.PRIORITY_MEDIUM_USD else "Low"


def _name(tags: dict[str, str]) -> str:
    return tags.get("Name", "")


# ---------------------------------------------------------------------------
# Metric helpers shared by the instance rules and the backtest
# ---------------------------------------------------------------------------

def trimmed(m: Optional[InstanceMetrics]) -> tuple[list, list, list]:
    """Hourly series with the empty hours *before* the instance existed removed.

    A 10-day-old instance in a 14-day window has 4 days of None at the start.
    Those are not "missing data", so they must not count against coverage.
    Gaps after the first datapoint are kept (they ARE missing data).
    """
    if m is None:
        return [], [], []
    first = next((k for k, v in enumerate(m.cpu_avg) if v is not None), len(m.cpu_avg))

    def cut(xs: list) -> list:
        xs = xs[first:]
        return xs + [None] * (len(m.cpu_avg) - first - len(xs))

    return cut(m.cpu_avg), cut(m.cpu_max), cut(m.net_in_bytes)


def metric_window(m: Optional[InstanceMetrics]) -> tuple[list[float], list[float], list[float], int]:
    """(cpu_avg, cpu_max, net_in) with gaps removed, plus hours since first datapoint."""
    avg, mx, net = trimmed(m)
    return present(avg), present(mx), present(net), len(avg)


def enough_data(cpu: list[float], total_hours: int) -> bool:
    return (len(cpu) >= C.MIN_METRIC_HOURS
            and total_hours > 0 and len(cpu) / total_hours >= C.MIN_METRIC_COVERAGE)


def is_idle(cpu_avg: list[float], net: list[float]) -> tuple[bool, float, float]:
    p95 = percentile(cpu_avg, 95)
    kbps = mean(net) / 3600 / 1024 if net else 0.0
    return p95 < C.IDLE_CPU_P95 and kbps < C.IDLE_NET_AVG_KBPS, p95, kbps


def smaller_type(itype: str, pb: PriceBook) -> Optional[str]:
    """Next smaller size in the same family that AWS actually sells here."""
    family, _, size = itype.partition(".")
    if size not in SIZE_LADDER:
        return None
    for s in reversed(SIZE_LADDER[: SIZE_LADDER.index(size)]):
        if pb.has_instance(f"{family}.{s}"):
            return f"{family}.{s}"
    return None


def rightsize_decision(itype: str, cpu_avg: list[float], cpu_max: list[float],
                       pb: PriceBook) -> Optional[dict]:
    """Would one size smaller still be comfortable? Returns details or None.

    Idea: CPU % is measured against all vCPUs. If the new type has half the
    vCPUs, the same work shows up as double the %. So we scale by
    factor = old_vcpu / new_vcpu and require the busy-time (p95 of hourly max)
    to stay under 80%. Burstable types must also stay under the smaller
    type's CPU-credit baseline.
    """
    target = smaller_type(itype, pb)
    if not target or not cpu_max:
        return None
    old, new = pb.instance(itype), pb.instance(target)
    factor = old["vcpu"] / new["vcpu"]
    p95_max = percentile(cpu_max, 95)
    projected_p95 = p95_max * factor
    avg = mean(cpu_avg)
    projected_avg = avg * factor
    ok = projected_p95 < C.RIGHTSIZE_SAFE_AFTER
    baseline = None
    if itype.split(".")[0] in BURSTABLE:
        baseline = C.BURSTABLE_BASELINE.get(target.split(".")[1])
        ok = ok and baseline is not None and projected_avg < baseline * C.BURSTABLE_MARGIN
    if not ok:
        return None
    return {"target": target, "factor": factor, "p95_max": p95_max, "avg": avg,
            "projected_p95": projected_p95, "projected_avg": projected_avg,
            "baseline": baseline}


def _instance_checks(i: Instance) -> list[str]:
    return [
        f"aws ec2 describe-instances --instance-ids {i.id}",
        f"aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization "
        f"--dimensions Name=InstanceId,Value={i.id} --statistics Average Maximum --period 3600 "
        f"--start-time <14-days-ago> --end-time <now>",
    ]


# ---------------------------------------------------------------------------
# Rule 1 - Idle EC2 instance
# ---------------------------------------------------------------------------

def rule_idle_instance(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    for i in s.instances:
        if i.state != "running":
            continue
        cpu_avg, _, net, total = metric_window(s.metrics.get(i.id))
        if not enough_data(cpu_avg, total):
            continue  # the analyser adds a "not enough data" notice
        idle, p95, kbps = is_idle(cpu_avg, net)
        if not idle:
            continue
        usd, steps, refs = instance_cost(i, ctx.pb)
        days = len(cpu_avg) // 24
        high = len(cpu_avg) >= 14 * 24
        out.append(Finding(
            id=f"idle-{i.id}", rule_id="ec2-idle", rule_name="Idle EC2 instance",
            resource_id=i.id, resource_name=i.name, resource_type="EC2 instance",
            title=f"Stop idle instance {i.name or i.id}",
            summary=f"This {i.type} has done almost nothing for {days} days "
                    f"(CPU under {C.IDLE_CPU_P95}% in 95% of hours, {kbps:.2f} KB/s network).",
            monthly_savings=round(usd, 2), priority=priority_for(usd),
            confidence="High" if high else "Medium",
            confidence_reason=f"{len(cpu_avg)} hours of CloudWatch data"
                              + (" (2+ weeks)." if high else " (1-2 weeks; more data = more sure)."),
            risk="Medium",
            risk_reason="A rarely-used job (monthly report, standby server) would also look idle.",
            evidence=[Evidence(label="Instance type", value=i.type),
                      Evidence(label="CPU p95 (hourly avg)", value=f"{p95:.2f}%"),
                      Evidence(label="Avg network in", value=f"{kbps:.2f} KB/s"),
                      Evidence(label="Hours of data", value=str(len(cpu_avg)))],
            calculation=steps + [CalcStep(text="Stopping removes the compute charge "
                                               "(its disks are still billed)", usd=usd)],
            prices_used=refs,
            check_commands=_instance_checks(i),
            fix_steps=["Ask the owner (see tags) whether it is still needed.",
                       f"Create an AMI backup: aws ec2 create-image --instance-id {i.id} --name backup-{i.id}",
                       f"Stop (not terminate) it: aws ec2 stop-instances --instance-ids {i.id}",
                       "Terminate only if nobody complains for 2 weeks."],
        ))
    return out


# ---------------------------------------------------------------------------
# Rule 2 - Oversized EC2 instance (rightsizing)
# ---------------------------------------------------------------------------

def rule_rightsize(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    for i in s.instances:
        if i.state != "running" or not ctx.pb.has_instance(i.type):
            continue
        cpu_avg, cpu_max, net, total = metric_window(s.metrics.get(i.id))
        if not enough_data(cpu_avg, total) or not cpu_max:
            continue
        if is_idle(cpu_avg, net)[0]:
            continue  # idle rule already covers it - never give two answers
        d = rightsize_decision(i.type, cpu_avg, cpu_max, ctx.pb)
        if not d:
            continue
        now_cost = ctx.pb.instance_monthly(i.type)
        new_cost = ctx.pb.instance_monthly(d["target"])
        usd = round(now_cost - new_cost, 2)
        if usd <= 0:
            continue
        evidence = [
            Evidence(label="Current → suggested", value=f"{i.type} → {d['target']}"),
            Evidence(label="CPU p95 of hourly max", value=f"{d['p95_max']:.1f}%"),
            Evidence(label="Projected p95 after change", value=f"{d['projected_p95']:.1f}% "
                                                                 f"(limit {C.RIGHTSIZE_SAFE_AFTER:.0f}%)"),
            Evidence(label="Average CPU", value=f"{d['avg']:.1f}%"),
            Evidence(label="Hours of data", value=str(len(cpu_avg))),
        ]
        if d["baseline"] is not None:
            evidence.append(Evidence(label="Projected avg vs credit baseline",
                                     value=f"{d['projected_avg']:.1f}% vs {d['baseline']:.0f}% "
                                           f"(must stay under {d['baseline'] * C.BURSTABLE_MARGIN:.0f}%)"))
        out.append(Finding(
            id=f"rightsize-{i.id}", rule_id="ec2-rightsize", rule_name="Oversized EC2 instance",
            resource_id=i.id, resource_name=i.name, resource_type="EC2 instance",
            title=f"Downsize {i.name or i.id}: {i.type} → {d['target']}",
            summary=f"Even at its busiest, this instance would stay around "
                    f"{d['projected_p95']:.0f}% CPU on a {d['target']}.",
            monthly_savings=usd, priority=priority_for(usd),
            confidence="Medium",
            confidence_reason="CPU is measured, but memory is not: CloudWatch does not record "
                              "memory unless the CloudWatch agent is installed.",
            risk="Medium",
            risk_reason="Needs a restart, and the smaller type has less memory "
                        f"({ctx.pb.instance(d['target'])['memory_gib']} GiB vs "
                        f"{ctx.pb.instance(i.type)['memory_gib']} GiB).",
            evidence=evidence,
            calculation=[
                CalcStep(text=f"Now: {i.type} ${ctx.pb.instance_hourly(i.type)}/h x {C.HOURS_PER_MONTH} h",
                         usd=now_cost),
                CalcStep(text=f"After: {d['target']} ${ctx.pb.instance_hourly(d['target'])}/h x "
                              f"{C.HOURS_PER_MONTH} h", usd=new_cost),
                CalcStep(text="Saving = now - after", usd=usd),
            ],
            prices_used=[ctx.pb.instance_ref(i.type), ctx.pb.instance_ref(d["target"])],
            check_commands=_instance_checks(i),
            fix_steps=["Check memory use on the instance first (free -m) during a busy time.",
                       f"Stop: aws ec2 stop-instances --instance-ids {i.id}",
                       f"Change type: aws ec2 modify-instance-attribute --instance-id {i.id} "
                       f"--instance-type {d['target']}",
                       f"Start: aws ec2 start-instances --instance-ids {i.id}",
                       f"Roll back the same way with --instance-type {i.type} if it struggles."],
        ))
    return out


# ---------------------------------------------------------------------------
# Rule 3 - Unattached EBS volume
# ---------------------------------------------------------------------------

def rule_unattached_volume(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    for v in s.volumes:
        age = ctx.days_since(v.create_time)
        if v.state != "available" or age < C.UNATTACHED_VOLUME_DAYS:
            continue
        usd, steps, refs = volume_cost(v, ctx.pb)
        snap_usd = v.size_gb * ctx.pb.get("ebs_snapshot_gb_month")
        out.append(Finding(
            id=f"unattached-{v.id}", rule_id="ebs-unattached", rule_name="Unattached EBS volume",
            resource_id=v.id, resource_name=_name(v.tags), resource_type="EBS volume",
            title=f"Delete unattached volume {_name(v.tags) or v.id} ({v.size_gb} GB {v.type})",
            summary=f"This disk is not connected to any server, but is billed every month. "
                    f"It was created {age:.0f} days ago.",
            monthly_savings=round(usd, 2), priority=priority_for(usd),
            confidence="High",
            confidence_reason="Attachment state comes straight from the EC2 API - no guessing.",
            risk="Low",
            risk_reason=f"Take a snapshot first (about ${snap_usd:.2f}/month at most) and the "
                        "data can be restored any time.",
            evidence=[Evidence(label="State", value=v.state),
                      Evidence(label="Size / type", value=f"{v.size_gb} GB {v.type}"),
                      Evidence(label="Age", value=f"{age:.0f} days")],
            calculation=steps + [CalcStep(text="Optional safety snapshot costs at most "
                                               f"{v.size_gb} GB x ${ctx.pb.get('ebs_snapshot_gb_month')}",
                                          usd=snap_usd)],
            prices_used=refs + [ctx.pb.ref("ebs_snapshot_gb_month")],
            check_commands=[f"aws ec2 describe-volumes --volume-ids {v.id}",
                            f"aws cloudtrail lookup-events --lookup-attributes "
                            f"AttributeKey=ResourceName,AttributeValue={v.id}"],
            fix_steps=[f"aws ec2 create-snapshot --volume-id {v.id} --description 'before delete'",
                       "Wait until the snapshot state is 'completed'.",
                       f"aws ec2 delete-volume --volume-id {v.id}"],
        ))
    return out


# ---------------------------------------------------------------------------
# Rule 4 - Idle public IPv4 address (Elastic IP not attached)
# ---------------------------------------------------------------------------

def rule_idle_ip(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    for a in s.addresses:
        if a.associated_with is not None:
            continue
        usd, steps, refs = address_cost(a, ctx.pb)
        out.append(Finding(
            id=f"ip-{a.allocation_id}", rule_id="eip-idle", rule_name="Idle Elastic IP",
            resource_id=a.allocation_id, resource_name=a.public_ip, resource_type="Elastic IP",
            title=f"Release unused Elastic IP {a.public_ip}",
            summary="Since February 2024 AWS charges for every public IPv4 address. "
                    "This one is reserved but not attached to anything.",
            monthly_savings=round(usd, 2), priority=priority_for(usd),
            confidence="High", confidence_reason="Association state comes straight from the EC2 API.",
            risk="Low", risk_reason="Only risk: if a DNS record points here, that address is lost.",
            evidence=[Evidence(label="Public IP", value=a.public_ip),
                      Evidence(label="Attached to", value="nothing")],
            calculation=steps, prices_used=refs,
            check_commands=[f"aws ec2 describe-addresses --allocation-ids {a.allocation_id}"],
            fix_steps=["Check no DNS record uses this IP.",
                       f"aws ec2 release-address --allocation-id {a.allocation_id}"],
        ))
    return out


# ---------------------------------------------------------------------------
# Rule 5 - Stopped instance still paying for disks
# ---------------------------------------------------------------------------

def rule_stopped_instance(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    vols = {v.id: v for v in s.volumes}
    for i in s.instances:
        if i.state != "stopped":
            continue
        days = ctx.days_since(i.state_since)
        if i.state_since is None or days < C.STOPPED_INSTANCE_DAYS:
            continue
        steps, refs, usd = [], [], 0.0
        for vid in i.volume_ids:
            if vid in vols:
                c, st, rf = volume_cost(vols[vid], ctx.pb)
                usd += c
                steps += [CalcStep(text=f"{vid}: {x.text}", usd=x.usd) for x in st]
                refs += rf
        if usd <= 0:
            continue
        out.append(Finding(
            id=f"stopped-{i.id}", rule_id="ec2-stopped", rule_name="Long-stopped instance",
            resource_id=i.id, resource_name=i.name, resource_type="EC2 instance",
            title=f"Clean up {i.name or i.id}, stopped for {days:.0f} days",
            summary="A stopped instance costs nothing for compute, but its disks are still billed.",
            monthly_savings=round(usd, 2), priority=priority_for(usd),
            confidence="High", confidence_reason="Stop time is recorded by AWS in the instance's state reason.",
            risk="Medium", risk_reason="Someone may plan to start it again; an AMI keeps everything.",
            evidence=[Evidence(label="State", value=f"stopped since {i.state_since:%d %b %Y}"),
                      Evidence(label="Disks", value=", ".join(i.volume_ids) or "none")],
            calculation=steps + [CalcStep(text="Total disk cost while stopped", usd=usd)],
            prices_used=refs,
            check_commands=[f"aws ec2 describe-instances --instance-ids {i.id} "
                            "--query 'Reservations[].Instances[].StateTransitionReason'"],
            fix_steps=[f"aws ec2 create-image --instance-id {i.id} --name archive-{i.id}",
                       f"aws ec2 terminate-instances --instance-ids {i.id}",
                       "The AMI's snapshots cost less than live disks and can recreate the server."],
        ))
    return out


# ---------------------------------------------------------------------------
# Rule 6 - Snapshot whose source volume is gone
# ---------------------------------------------------------------------------

def rule_orphan_snapshot(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    for snap in s.snapshots:
        age = ctx.days_since(snap.start_time)
        if snap.volume_exists or snap.used_by_ami or age < C.ORPHAN_SNAPSHOT_DAYS:
            continue
        usd, steps, refs = snapshot_cost(snap, ctx.pb)
        out.append(Finding(
            id=f"snapshot-{snap.id}", rule_id="snapshot-orphan", rule_name="Orphaned snapshot",
            resource_id=snap.id, resource_name=_name(snap.tags), resource_type="EBS snapshot",
            title=f"Review snapshot {snap.id} (its disk no longer exists)",
            summary=f"This {age:.0f}-day-old backup belongs to a disk that was deleted.",
            monthly_savings=round(usd, 2), priority=priority_for(usd),
            confidence="Medium",
            confidence_reason="The saving is an upper bound: snapshots only store used blocks.",
            risk="High", risk_reason="It may be the only remaining copy of that data - "
                                     "deleting it cannot be undone.",
            evidence=[Evidence(label="Source volume", value=f"{snap.volume_id} (deleted)"),
                      Evidence(label="Age", value=f"{age:.0f} days"),
                      Evidence(label="Description", value=snap.description or "-")],
            calculation=steps, prices_used=refs,
            check_commands=[f"aws ec2 describe-snapshots --snapshot-ids {snap.id}",
                            f"aws ec2 describe-images --filters Name=block-device-mapping.snapshot-id,"
                            f"Values={snap.id}"],
            fix_steps=["Confirm with the owner that this data is not needed.",
                       "Cheaper option: move it to the archive tier "
                       f"(aws ec2 modify-snapshot-tier --snapshot-id {snap.id} --storage-tier archive).",
                       f"Or delete: aws ec2 delete-snapshot --snapshot-id {snap.id}"],
        ))
    return out


# ---------------------------------------------------------------------------
# Rule 7 - S3: abandoned multipart uploads / no lifecycle on big buckets
# ---------------------------------------------------------------------------

def rule_s3(s: Snapshot, ctx: Context) -> list[Finding]:
    out = []
    price = ctx.pb.get("s3_standard_gb_month")
    for b in s.buckets:
        old = [u for u in b.incomplete_uploads if ctx.days_since(u.initiated) >= C.ABANDONED_UPLOAD_DAYS]
        if old:
            gb = sum(u.size_bytes for u in old) / 2**30
            usd = round(gb * price, 4)
            out.append(Finding(
                id=f"uploads-{b.name}", rule_id="s3-incomplete-uploads",
                rule_name="Abandoned S3 uploads",
                resource_id=b.name, resource_name=b.name, resource_type="S3 bucket",
                title=f"Clear {len(old)} abandoned upload(s) in {b.name}",
                summary="Unfinished multipart uploads are invisible in the console "
                        "but their parts are billed as storage.",
                monthly_savings=usd, priority=priority_for(usd),
                confidence="High", confidence_reason="Listed directly by the S3 API.",
                risk="Low", risk_reason="An upload untouched for a week is not coming back.",
                evidence=[Evidence(label="Uploads older than 7 days", value=str(len(old))),
                          Evidence(label="Hidden data", value=f"{gb * 1024:.1f} MiB")],
                calculation=[CalcStep(text=f"{gb:.4f} GB x ${price}/GB-month", usd=usd)],
                prices_used=[ctx.pb.ref("s3_standard_gb_month")],
                check_commands=[f"aws s3api list-multipart-uploads --bucket {b.name}"],
                fix_steps=["Add a lifecycle rule so this never builds up again:",
                           f"aws s3api put-bucket-lifecycle-configuration --bucket {b.name} "
                           "--lifecycle-configuration '{\"Rules\":[{\"ID\":\"abort-mpu\",\"Status\":"
                           "\"Enabled\",\"Filter\":{},\"AbortIncompleteMultipartUpload\":"
                           "{\"DaysAfterInitiation\":7}}]}'"],
            ))
        if not b.has_lifecycle and b.size_gb >= C.LARGE_BUCKET_GB:
            usd_now, steps, refs = bucket_cost(b, ctx.pb)
            out.append(Finding(
                id=f"lifecycle-{b.name}", rule_id="s3-no-lifecycle", rule_name="Big bucket, no lifecycle",
                resource_id=b.name, resource_name=b.name, resource_type="S3 bucket",
                title=f"Add a lifecycle policy to {b.name} ({b.size_gb:.0f} GB)",
                summary="Everything stays in the most expensive storage class forever.",
                monthly_savings=None, priority="Low",
                confidence="Low",
                confidence_reason="We do not know how often objects are read, so we do not "
                                  "invent a saving. S3 Storage Lens or Intelligent-Tiering can measure it.",
                risk="Low", risk_reason="Moving rarely-read data to cheaper classes is reversible.",
                evidence=[Evidence(label="Size", value=f"{b.size_gb:.1f} GB"),
                          Evidence(label="Lifecycle rules", value="none")],
                calculation=steps + [CalcStep(text="Saving not estimated (needs access pattern data)")],
                prices_used=refs,
                check_commands=[f"aws s3api get-bucket-lifecycle-configuration --bucket {b.name}"],
                fix_steps=["Consider S3 Intelligent-Tiering for data with unknown access patterns."],
            ))
    return out


RULES: list[Callable[[Snapshot, Context], list[Finding]]] = [
    rule_idle_instance,
    rule_rightsize,
    rule_unattached_volume,
    rule_idle_ip,
    rule_stopped_instance,
    rule_orphan_snapshot,
    rule_s3,
]

RULE_CATALOG = [
    {"id": "ec2-idle", "name": "Idle EC2 instance",
     "test": f"Running; >= {C.MIN_METRIC_HOURS // 24} days of data; CPU p95 < {C.IDLE_CPU_P95}% "
             f"and avg network < {C.IDLE_NET_AVG_KBPS} KB/s"},
    {"id": "ec2-rightsize", "name": "Oversized EC2 instance",
     "test": f"Not idle; one size smaller keeps p95 of hourly max CPU < {C.RIGHTSIZE_SAFE_AFTER:.0f}% "
             "after scaling by vCPU ratio; burstable types also stay under credit baseline"},
    {"id": "ebs-unattached", "name": "Unattached EBS volume",
     "test": f"State 'available' and older than {C.UNATTACHED_VOLUME_DAYS} days"},
    {"id": "eip-idle", "name": "Idle Elastic IP", "test": "Elastic IP not associated with anything"},
    {"id": "ec2-stopped", "name": "Long-stopped instance",
     "test": f"Stopped for >= {C.STOPPED_INSTANCE_DAYS} days with disks attached"},
    {"id": "snapshot-orphan", "name": "Orphaned snapshot",
     "test": f"Source volume deleted and snapshot older than {C.ORPHAN_SNAPSHOT_DAYS} days"},
    {"id": "s3-incomplete-uploads", "name": "Abandoned S3 uploads",
     "test": f"Multipart uploads not finished after {C.ABANDONED_UPLOAD_DAYS} days"},
    {"id": "s3-no-lifecycle", "name": "Big bucket, no lifecycle",
     "test": f"Bucket >= {C.LARGE_BUCKET_GB} GB with no lifecycle rule (saving not estimated)"},
]
