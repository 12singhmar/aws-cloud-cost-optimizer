"""Deterministic Cost Optimization Rules for AWS Infrastructure Telemetry.

Rules implement explicit, auditable logic with clear formulas and evidence:
1. EC2RightsizingRule: Detects low CPU utilization on oversized compute instances.
2. EC2IdleRule: Detects completely idle instances with zero workload.
3. EBSUnattachedRule: Detects orphaned EBS volumes with provisioned capacity.
4. S3LifecycleRule: Detects unmanaged historical storage suitable for tiering.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.models import EvidenceItem, Recommendation, Resource, ResourceMetrics


class BaseRule(ABC):
    """Abstract base class for all optimization rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for the rule."""
        pass

    @property
    @abstractmethod
    def service(self) -> str:
        """Target AWS service (e.g. 'EC2', 'EBS', 'S3')."""
        pass

    @abstractmethod
    def evaluate(self, resource: Resource, metrics: Optional[ResourceMetrics]) -> Optional[Recommendation]:
        """Evaluate resource against the rule criteria."""
        pass


class EC2IdleRule(BaseRule):
    """Detects running EC2 instances with negligible CPU and network activity."""

    @property
    def rule_id(self) -> str:
        return "ec2-idle"

    @property
    def service(self) -> str:
        return "EC2"

    def evaluate(self, resource: Resource, metrics: Optional[ResourceMetrics]) -> Optional[Recommendation]:
        if resource.resource_type.value != "EC2" or resource.status != "running":
            return None

        if not metrics or not metrics.has_sufficient_data:
            return None

        if metrics.observation_days < 7:
            return None

        if metrics.avg_cpu_percent is None or metrics.peak_cpu_percent is None:
            return None

        # Idle thresholds: avg CPU < 2.0%, peak CPU < 5.0%, network in < 5,000 bytes/sec
        is_cpu_idle = metrics.avg_cpu_percent < 2.0 and metrics.peak_cpu_percent < 5.0
        net_in = metrics.network_in_bytes_sec if metrics.network_in_bytes_sec is not None else 0.0
        is_net_idle = net_in < 5000.0

        if not (is_cpu_idle and is_net_idle):
            return None

        avoidable_savings = resource.monthly_cost
        priority = "HIGH" if avoidable_savings >= 50.0 else "MEDIUM"

        return Recommendation(
            id=f"rec-idle-{resource.id}",
            resource_id=resource.id,
            resource_name=resource.name,
            service="EC2",
            rule_id=self.rule_id,
            title=f"Stop or terminate idle EC2 instance ({resource.name or resource.id})",
            description=(
                f"Instance {resource.id} has shown less than 2.0% average CPU utilisation and "
                f"negligible network traffic over {metrics.observation_days} consecutive days."
            ),
            priority=priority,
            estimated_savings=round(avoidable_savings, 2),
            estimated_savings_formatted=f"${avoidable_savings:.2f}/mo",
            confidence=90,
            risk="Medium",
            reasoning=(
                f"Compute resources are fully provisioned ({resource.details.get('instance_type', 'unknown')}) "
                f"costing ${resource.monthly_cost:.2f}/mo, but average CPU is {metrics.avg_cpu_percent:.1f}% "
                f"with peak CPU of {metrics.peak_cpu_percent:.1f}%. The instance appears to be an abandoned or orphaned workload."
            ),
            evidence=[
                EvidenceItem(label="Resource ID", value=resource.id),
                EvidenceItem(label="Instance Type", value=str(resource.details.get("instance_type", "EC2"))),
                EvidenceItem(label="Average CPU", value=f"{metrics.avg_cpu_percent:.1f}%"),
                EvidenceItem(label="Peak CPU", value=f"{metrics.peak_cpu_percent:.1f}%"),
                EvidenceItem(label="Network In", value=f"{net_in / 1024:.2f} KB/s"),
                EvidenceItem(label="Observation Window", value=f"{metrics.observation_days} days"),
            ],
            verification_guidance=(
                "Verify whether this instance is part of an active service, scheduled cron, or disaster recovery cluster. "
                "Confirm owner with tags, create a pre-stop AMI backup, and stop the instance in AWS Console."
            ),
            savings_assumptions=(
                f"Assumes stopping instance eliminates 100% of On-Demand compute charge (${resource.monthly_cost:.2f}/mo). "
                "Attached EBS root volume storage charges will continue until volume is deleted."
            ),
            confidence_rationale="High confidence: Consistent near-zero utilization sustained across > 7 days.",
            risk_rationale="Medium risk: Stopping an instance disrupts any unrecorded background cron processes.",
            observation_window=f"{metrics.observation_days} days continuous CloudWatch telemetry",
            suggested_action="Stop instance and monitor for 14 days before termination",
            aws_console_url=f"https://console.aws.amazon.com/ec2/v2/home?region={resource.region}#InstanceDetails:instanceId={resource.id}",
        )


class EC2RightsizingRule(BaseRule):
    """Detects underutilized running EC2 instances suitable for downsizing."""

    @property
    def rule_id(self) -> str:
        return "ec2-rightsizing"

    @property
    def service(self) -> str:
        return "EC2"

    def evaluate(self, resource: Resource, metrics: Optional[ResourceMetrics]) -> Optional[Recommendation]:
        if resource.resource_type.value != "EC2" or resource.status != "running":
            return None

        if not metrics or not metrics.has_sufficient_data:
            return None

        if metrics.observation_days < 7:
            return None

        if metrics.avg_cpu_percent is None or metrics.peak_cpu_percent is None:
            return None

        # Exclude completely idle instances — those belong to EC2IdleRule
        net_in = metrics.network_in_bytes_sec if metrics.network_in_bytes_sec is not None else 0.0
        if metrics.avg_cpu_percent < 2.0 and metrics.peak_cpu_percent < 5.0 and net_in < 5000.0:
            return None

        # Rightsizing threshold: avg CPU < 10.0% and peak CPU < 30.0%
        if metrics.avg_cpu_percent >= 10.0 or metrics.peak_cpu_percent >= 30.0:
            return None

        current_cost = resource.monthly_cost
        recommended_type = resource.details.get("recommended_type")
        recommended_cost = resource.details.get("recommended_cost")

        if recommended_cost is not None:
            savings = current_cost - float(recommended_cost)
        else:
            savings = current_cost * 0.50
            recommended_type = "Next smaller instance tier"

        if savings <= 0:
            return None

        priority = "HIGH" if savings >= 50.0 else "MEDIUM"
        confidence = 90 if metrics.observation_days >= 14 else 80

        return Recommendation(
            id=f"rec-rightsize-{resource.id}",
            resource_id=resource.id,
            resource_name=resource.name,
            service="EC2",
            rule_id=self.rule_id,
            title=f"Rightsize underutilized EC2 instance ({resource.name or resource.id})",
            description=(
                f"Instance {resource.id} ({resource.details.get('instance_type', 'EC2')}) averaged "
                f"{metrics.avg_cpu_percent:.1f}% CPU with peaks of only {metrics.peak_cpu_percent:.1f}% "
                f"over {metrics.observation_days} days. Downsize to {recommended_type}."
            ),
            priority=priority,
            estimated_savings=round(savings, 2),
            estimated_savings_formatted=f"${savings:.2f}/mo",
            confidence=confidence,
            risk="Medium",
            reasoning=(
                f"Current instance type {resource.details.get('instance_type')} costs ${current_cost:.2f}/mo. "
                f"Observed peak workload ({metrics.peak_cpu_percent:.1f}%) fits comfortably within the capacity "
                f"of {recommended_type} (projected cost: ${recommended_cost:.2f}/mo)."
            ),
            evidence=[
                EvidenceItem(label="Resource ID", value=resource.id),
                EvidenceItem(label="Current Type", value=str(resource.details.get("instance_type", "EC2"))),
                EvidenceItem(label="Proposed Type", value=str(recommended_type)),
                EvidenceItem(label="Average CPU", value=f"{metrics.avg_cpu_percent:.1f}%"),
                EvidenceItem(label="Peak CPU", value=f"{metrics.peak_cpu_percent:.1f}%"),
                EvidenceItem(label="Current Spend", value=f"${current_cost:.2f}/mo"),
                EvidenceItem(label="Observation Window", value=f"{metrics.observation_days} days"),
            ],
            verification_guidance=(
                "Inspect memory utilization (CloudWatch Agent), network bursts, and local disk space. "
                "Test application in staging under simulated peak load before modifying production instance type."
            ),
            savings_assumptions=(
                f"Based on AWS On-Demand list prices in {resource.region}. Current: ${current_cost:.2f}/mo, "
                f"Target ({recommended_type}): ${recommended_cost:.2f}/mo. Net monthly delta = ${savings:.2f}/mo."
            ),
            confidence_rationale="High confidence: Consistent low utilization across 14-day observation window.",
            risk_rationale="Medium risk: Requires instance restart and verification of memory headroom.",
            observation_window=f"{metrics.observation_days} days continuous CloudWatch telemetry",
            suggested_action=f"Modify instance type from {resource.details.get('instance_type')} to {recommended_type}",
            aws_console_url=f"https://console.aws.amazon.com/ec2/v2/home?region={resource.region}#InstanceDetails:instanceId={resource.id}",
        )


class EBSUnattachedRule(BaseRule):
    """Detects unattached EBS volumes incurring unnecessary storage and provisioned IOPS costs."""

    @property
    def rule_id(self) -> str:
        return "ebs-unattached"

    @property
    def service(self) -> str:
        return "EBS"

    def evaluate(self, resource: Resource, metrics: Optional[ResourceMetrics]) -> Optional[Recommendation]:
        if resource.resource_type.value != "EBS":
            return None

        if resource.status != "available":
            return None

        if metrics and not metrics.has_sufficient_data:
            return None

        days_unattached = resource.details.get("days_unattached", 0)
        observation_days = metrics.observation_days if metrics else days_unattached

        if max(days_unattached, observation_days) < 7:
            return None

        size_gb = float(resource.details.get("size_gb", 0))
        vol_type = str(resource.details.get("volume_type", "gp3"))
        
        storage_cost = float(resource.details.get("storage_cost", size_gb * 0.08))
        iops_cost = float(resource.details.get("provisioned_iops_cost", 0.0))
        tp_cost = float(resource.details.get("provisioned_throughput_cost", 0.0))
        total_cost = storage_cost + iops_cost + tp_cost
        
        avoidable_cost = resource.monthly_cost if resource.monthly_cost > 0 else total_cost
        
        priority = "HIGH" if avoidable_cost >= 30.0 else "MEDIUM"
        confidence = 95 if max(days_unattached, observation_days) >= 14 else 85

        return Recommendation(
            id=f"rec-ebs-{resource.id}",
            resource_id=resource.id,
            resource_name=resource.name,
            service="EBS",
            rule_id=self.rule_id,
            title=f"Delete unattached EBS volume ({resource.name or resource.id})",
            description=(
                f"EBS volume {resource.id} ({vol_type}, {size_gb:.0f} GB) has been unattached "
                f"for {days_unattached} days with zero disk operations, incurring ${avoidable_cost:.2f}/mo."
            ),
            priority=priority,
            estimated_savings=round(avoidable_cost, 2),
            estimated_savings_formatted=f"${avoidable_cost:.2f}/mo",
            confidence=confidence,
            risk="Low",
            reasoning=(
                f"Volume {resource.id} is in 'available' (unattached) status. "
                f"Charges comprise ${storage_cost:.2f}/mo base storage plus provisioned performance "
                f"(${iops_cost + tp_cost:.2f}/mo) that is completely unused."
            ),
            evidence=[
                EvidenceItem(label="Resource ID", value=resource.id),
                EvidenceItem(label="Volume Type", value=vol_type),
                EvidenceItem(label="Size", value=f"{size_gb:.0f} GB"),
                EvidenceItem(label="Status", value="available (unattached)"),
                EvidenceItem(label="Days Unattached", value=f"{days_unattached} days"),
                EvidenceItem(label="Monthly Cost", value=f"${avoidable_cost:.2f}/mo"),
                EvidenceItem(label="Provisioned IOPS", value=str(resource.details.get("provisioned_iops", "3000 baseline"))),
                EvidenceItem(label="Provisioned Throughput", value=f"{resource.details.get('provisioned_throughput_mbps', 125)} MB/s"),
            ],
            verification_guidance=(
                "Query CloudTrail for detachment history, confirm data ownership with the Analytics team, "
                "and take an EBS snapshot before deletion to ensure zero data loss."
            ),
            savings_assumptions=(
                f"Decommissioning volume eliminates 100% of volume charge (${avoidable_cost:.2f}/mo). "
                "If a safety snapshot (250 GB @ $0.05/GB-mo = $12.50/mo) is created and retained, "
                "the net monthly savings will be $27.50/mo ($330.00/yr)."
            ),
            confidence_rationale="Very high confidence: Deterministic AWS volume attachment state and 0 disk I/O.",
            risk_rationale="Low risk: Volume can be fully restored from an EBS snapshot if needed.",
            observation_window=f"{days_unattached} days unattached telemetry",
            suggested_action="Create snapshot backup and delete unattached EBS volume",
            aws_console_url=f"https://console.aws.amazon.com/ec2/v2/home?region={resource.region}#VolumeDetails:volumeId={resource.id}",
        )


class S3LifecycleRule(BaseRule):
    """Detects S3 buckets with rapid historical growth and no lifecycle tiering policy."""

    @property
    def rule_id(self) -> str:
        return "s3-lifecycle"

    @property
    def service(self) -> str:
        return "S3"

    def evaluate(self, resource: Resource, metrics: Optional[ResourceMetrics]) -> Optional[Recommendation]:
        if resource.resource_type.value != "S3":
            return None

        lifecycle = resource.details.get("lifecycle_policy")
        if lifecycle == "Enabled":
            return None

        if metrics and not metrics.has_sufficient_data:
            return None

        stale_storage_gb = resource.details.get("stale_storage_gb_over_90d")
        current_storage_gb = resource.details.get("current_storage_gb", 0.0)

        if stale_storage_gb is not None and stale_storage_gb > 0:
            savings = round(stale_storage_gb * 0.019, 2)
            priority = "HIGH" if savings >= 100.0 else "MEDIUM"
            confidence = 80
            reasoning = (
                f"Bucket {resource.name} stores {current_storage_gb:,.0f} GB in S3 Standard without a lifecycle policy. "
                f"An estimated {stale_storage_gb:,.0f} GB of objects have not been accessed in over 90 days. "
                f"Transitioning aged objects to Glacier Instant Retrieval saves $0.019/GB-month."
            )
        else:
            return None

        return Recommendation(
            id=f"rec-s3-{resource.id}",
            resource_id=resource.id,
            resource_name=resource.name,
            service="S3",
            rule_id=self.rule_id,
            title=f"Implement S3 Lifecycle transitions ({resource.name or resource.id})",
            description=(
                f"Bucket {resource.id} contains {stale_storage_gb:,.0f} GB of data older than 90 days "
                f"in S3 Standard tier with no automated transition rules."
            ),
            priority=priority,
            estimated_savings=savings,
            estimated_savings_formatted=f"${savings:.2f}/mo",
            confidence=confidence,
            risk="Low",
            reasoning=reasoning,
            evidence=[
                EvidenceItem(label="Resource ID", value=resource.id),
                EvidenceItem(label="Current Storage", value=f"{current_storage_gb:,.0f} GB"),
                EvidenceItem(label="Stale Storage (>90d)", value=f"{stale_storage_gb:,.0f} GB"),
                EvidenceItem(label="Current Storage Class", value=str(resource.details.get("storage_class", "Standard"))),
                EvidenceItem(label="Lifecycle Policy", value="None configured"),
                EvidenceItem(label="Current Monthly Cost", value=f"${resource.monthly_cost:.2f}/mo"),
            ],
            verification_guidance=(
                "Analyze bucket access patterns using S3 Storage Lens or CloudWatch access metrics. "
                "Define lifecycle rule: transition objects to Glacier Instant Retrieval after 90 days."
            ),
            savings_assumptions=(
                f"Transitioning {stale_storage_gb:,.0f} GB from S3 Standard ($0.023/GB) to Glacier Instant Retrieval "
                f"($0.004/GB) produces a net reduction of $0.019/GB-month (${savings:.2f}/mo). "
                "Excludes one-time PUT transition request charges."
            ),
            confidence_rationale="Moderate confidence: Assumes objects older than 90 days can tolerate Glacier tier access latency.",
            risk_rationale="Low risk: Objects remain immediately accessible with millisecond retrieval.",
            observation_window="30 days telemetry baseline",
            suggested_action="Configure S3 Lifecycle Rule to transition objects >90 days to Glacier Instant Retrieval",
            aws_console_url=f"https://s3.console.aws.amazon.com/s3/buckets/{resource.id}",
        )
