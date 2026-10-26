"""Deterministic Scenarios for AWS Cloud Cost Optimiser.

All scenarios are strictly deterministic, reproducible, and clearly labeled as simulated.
Each scenario models a coherent cloud infrastructure state:
- A: High Cost & Resource Waste (low CPU EC2, idle instance, unattached EBS, rapid S3 growth)
- B: Healthy Cloud Environment (appropriate utilisation, attached volumes, steady storage)
- C: Mixed Environment (differentiated findings, 1 high, 1 medium, plus healthy services)
- D: Insufficient Data (observation windows < 7 days, missing metrics, data-quality warnings)

Pricing and Telemetry Specifications:
- EC2 On-Demand us-east-1:
  * c5.xlarge (4 vCPU, 8 GiB): $0.17/hr -> $122.40/mo (720 hrs)
  * c5.large (2 vCPU, 4 GiB): $0.085/hr -> $61.20/mo (720 hrs)
  * m5.2xlarge (8 vCPU, 32 GiB): $0.40/hr -> $288.00/mo (720 hrs)
  * m5.large (2 vCPU, 8 GiB): $0.108/hr -> $78.00/mo (720 hrs)
  * t3.xlarge (4 vCPU, 16 GiB): $0.1667/hr -> $120.00/mo (720 hrs)
- EBS gp3 us-east-1:
  * Base Storage: $0.08 / GB-month
  * Baseline Included Free: 3,000 IOPS and 125 MB/s throughput
  * Additional IOPS: $0.005 / provisioned IOPS-month (above 3,000)
  * Additional Throughput: $0.04 / provisioned MB/s-month (above 125 MB/s)
- S3 Standard us-west-2 / us-east-1:
  * S3 Standard Storage: $0.023 / GB-month
  * Glacier Instant Retrieval: $0.004 / GB-month (delta: $0.019 / GB-month)
"""

from typing import Dict, List
from app.models import (
    CostTrendPoint,
    Resource,
    ResourceMetrics,
    ResourceType,
    ScenarioMetadata,
)


class ScenarioDefinition:
    def __init__(
        self,
        metadata: ScenarioMetadata,
        resources: List[Resource],
        metrics: Dict[str, ResourceMetrics],
        cost_trend: List[CostTrendPoint],
        month: str = "September 2026",
    ):
        self.metadata = metadata
        self.resources = resources
        self.metrics = metrics
        self.cost_trend = cost_trend
        self.month = month


# ---------------------------------------------------------------------------
# Scenario A: High Cost & Resource Waste
# ---------------------------------------------------------------------------
SCENARIO_A_METADATA = ScenarioMetadata(
    id="high-cost-waste",
    name="High Cost & Resource Waste",
    description=(
        "Simulates an inefficient cloud deployment with an oversized EC2 instance, "
        "an idle compute instance, an unattached provisioned EBS volume, and rapid S3 growth."
    ),
    simulated=True,
    expected_findings_summary="4 prioritised findings across EC2, EBS, and S3 totaling $335.00/mo savings.",
    resource_count=9,
)

SCENARIO_A_RESOURCES: List[Resource] = [
    Resource(
        id="i-08a1b2c3d4e5f",
        name="api-worker-prod-01",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=122.40,
        tags={"Environment": "Production", "Service": "API", "Team": "Core-Backend"},
        details={
            "instance_type": "c5.xlarge",
            "vcpus": 4,
            "memory_gib": 8,
            "recommended_type": "c5.large",
            "recommended_cost": 61.20,
        },
    ),
    Resource(
        id="i-09b2c3d4e5f6a",
        name="batch-processor-node",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=78.00,
        tags={"Environment": "Production", "Service": "Batch", "Team": "Data-Eng"},
        details={
            "instance_type": "m5.large",
            "vcpus": 2,
            "memory_gib": 8,
            "is_idle": True,
        },
    ),
    # 250 GB gp3: $20.00 storage (250 * $0.08) + $15.00 IOPS (3,000 addl @ $0.005) + $5.00 throughput (125 MB/s addl @ $0.04) = $40.00/mo
    Resource(
        id="vol-0a7f82c9e4b1a3d5e",
        name="data-analytics-temp-backup",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="available",  # unattached
        monthly_cost=40.00,
        tags={"Environment": "Analytics", "CreatedBy": "migration-job"},
        details={
            "volume_type": "gp3",
            "size_gb": 250,
            "provisioned_iops": 6000,
            "provisioned_throughput_mbps": 250,
            "days_unattached": 31,
            "storage_cost": 20.00,
            "provisioned_iops_cost": 15.00,
            "provisioned_throughput_cost": 5.00,
        },
    ),
    # 14.8 TB S3 Standard @ $0.023/GB = $340.40/mo. 8.2 TB stale > 90d.
    Resource(
        id="production-app-telemetry-logs",
        name="production-app-telemetry-logs",
        resource_type=ResourceType.S3,
        region="us-west-2",
        status="active",
        monthly_cost=340.40,
        tags={"DataClassification": "Internal", "BucketType": "Telemetry"},
        details={
            "storage_class": "Standard",
            "lifecycle_policy": None,
            "current_storage_gb": 14800.0,
            "stale_storage_gb_over_90d": 8200.0,
            "growth_period_days": 30,
        },
    ),
    Resource(
        id="i-05e4d3c2b1a09",
        name="core-web-frontend",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=61.20,
        tags={"Environment": "Production", "Service": "Web"},
        details={"instance_type": "c5.large", "vcpus": 2, "memory_gib": 4},
    ),
    Resource(
        id="vol-01283c8475a839b2e",
        name="root-vol-web-frontend",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="in-use",
        monthly_cost=8.00,
        tags={"Environment": "Production"},
        details={"volume_type": "gp3", "size_gb": 100, "attached_instance_id": "i-05e4d3c2b1a09"},
    ),
    Resource(
        id="company-static-web-assets",
        name="company-static-web-assets",
        resource_type=ResourceType.S3,
        region="us-east-1",
        status="active",
        monthly_cost=10.35,
        tags={"Environment": "Production"},
        details={"storage_class": "Standard", "lifecycle_policy": "Enabled"},
    ),
    Resource(
        id="analytics-primary-cluster",
        name="analytics-primary-cluster",
        resource_type=ResourceType.RDS,
        region="us-east-1",
        status="available",
        monthly_cost=130.00,
        tags={"Environment": "Production"},
        details={"instance_class": "db.m5.large", "engine": "postgres"},
    ),
    Resource(
        id="reporting-cache-replica",
        name="reporting-cache-replica",
        resource_type=ResourceType.RDS,
        region="us-east-1",
        status="available",
        monthly_cost=120.00,
        tags={"Environment": "Production"},
        details={"instance_class": "db.m5.large", "engine": "postgres"},
    ),
]

SCENARIO_A_METRICS: Dict[str, ResourceMetrics] = {
    "i-08a1b2c3d4e5f": ResourceMetrics(
        resource_id="i-08a1b2c3d4e5f",
        observation_days=14,
        avg_cpu_percent=5.8,
        peak_cpu_percent=19.2,
        network_in_bytes_sec=142000.0,
        has_sufficient_data=True,
    ),
    "i-09b2c3d4e5f6a": ResourceMetrics(
        resource_id="i-09b2c3d4e5f6a",
        observation_days=14,
        avg_cpu_percent=0.8,
        peak_cpu_percent=2.1,
        network_in_bytes_sec=1200.0,
        disk_iops=0.2,
        has_sufficient_data=True,
    ),
    "vol-0a7f82c9e4b1a3d5e": ResourceMetrics(
        resource_id="vol-0a7f82c9e4b1a3d5e",
        observation_days=14,
        disk_iops=0.0,
        has_sufficient_data=True,
    ),
    "production-app-telemetry-logs": ResourceMetrics(
        resource_id="production-app-telemetry-logs",
        observation_days=30,
        current_storage_gb=14800.0,
        storage_growth_gb=4500.0,
        storage_growth_percent=43.7,
        has_sufficient_data=True,
    ),
    "i-05e4d3c2b1a09": ResourceMetrics(
        resource_id="i-05e4d3c2b1a09",
        observation_days=14,
        avg_cpu_percent=64.2,
        peak_cpu_percent=82.1,
        network_in_bytes_sec=580000.0,
        has_sufficient_data=True,
    ),
    "vol-01283c8475a839b2e": ResourceMetrics(
        resource_id="vol-01283c8475a839b2e",
        observation_days=14,
        disk_iops=340.0,
        has_sufficient_data=True,
    ),
    "company-static-web-assets": ResourceMetrics(
        resource_id="company-static-web-assets",
        observation_days=30,
        current_storage_gb=450.0,
        storage_growth_gb=15.0,
        storage_growth_percent=3.4,
        has_sufficient_data=True,
    ),
}

# Total monthly cost = $910.35:
SCENARIO_A_TREND: List[CostTrendPoint] = [
    CostTrendPoint(month="April", cost=720.0, label="$720"),
    CostTrendPoint(month="May", cost=755.0, label="$755"),
    CostTrendPoint(month="June", cost=790.0, label="$790"),
    CostTrendPoint(month="July", cost=825.0, label="$825"),
    CostTrendPoint(month="August", cost=860.0, label="$860"),
    CostTrendPoint(month="September", cost=910.35, label="$910"),
]


# ---------------------------------------------------------------------------
# Scenario B: Healthy Cloud Environment
# ---------------------------------------------------------------------------
SCENARIO_B_METADATA = ScenarioMetadata(
    id="healthy-environment",
    name="Healthy Cloud Environment",
    description="Simulates a fully tuned cloud environment with high compute utilisation, attached storage, and automated lifecycle rules.",
    simulated=True,
    expected_findings_summary="0 findings. Workloads operate within efficiency baselines.",
    resource_count=6,
)

SCENARIO_B_RESOURCES: List[Resource] = [
    Resource(
        id="i-011a22b33c44d",
        name="prod-api-cluster-01",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=122.40,
        tags={"Environment": "Production", "Service": "API"},
        details={"instance_type": "c5.xlarge"},
    ),
    Resource(
        id="i-022b33c44d55e",
        name="prod-api-cluster-02",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=122.40,
        tags={"Environment": "Production", "Service": "API"},
        details={"instance_type": "c5.xlarge"},
    ),
    Resource(
        id="vol-033c44d55e66f",
        name="vol-prod-api-01",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="in-use",
        monthly_cost=8.00,
        tags={"Environment": "Production"},
        details={"volume_type": "gp3", "size_gb": 100, "attached_instance_id": "i-011a22b33c44d"},
    ),
    Resource(
        id="vol-044d55e66f77a",
        name="vol-prod-api-02",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="in-use",
        monthly_cost=8.00,
        tags={"Environment": "Production"},
        details={"volume_type": "gp3", "size_gb": 100, "attached_instance_id": "i-022b33c44d55e"},
    ),
    Resource(
        id="prod-assets-optimized",
        name="prod-assets-optimized",
        resource_type=ResourceType.S3,
        region="us-east-1",
        status="active",
        monthly_cost=23.00,
        tags={"Environment": "Production"},
        details={"storage_class": "Standard", "lifecycle_policy": "Enabled"},
    ),
    Resource(
        id="prod-db-primary",
        name="prod-db-primary",
        resource_type=ResourceType.RDS,
        region="us-east-1",
        status="available",
        monthly_cost=215.35,
        tags={"Environment": "Production"},
        details={"instance_class": "db.r5.large"},
    ),
]

SCENARIO_B_METRICS: Dict[str, ResourceMetrics] = {
    "i-011a22b33c44d": ResourceMetrics(
        resource_id="i-011a22b33c44d",
        observation_days=14,
        avg_cpu_percent=68.5,
        peak_cpu_percent=86.2,
        network_in_bytes_sec=420000.0,
        has_sufficient_data=True,
    ),
    "i-022b33c44d55e": ResourceMetrics(
        resource_id="i-022b33c44d55e",
        observation_days=14,
        avg_cpu_percent=71.2,
        peak_cpu_percent=89.0,
        network_in_bytes_sec=450000.0,
        has_sufficient_data=True,
    ),
    "vol-033c44d55e66f": ResourceMetrics(
        resource_id="vol-033c44d55e66f",
        observation_days=14,
        disk_iops=280.0,
        has_sufficient_data=True,
    ),
    "vol-044d55e66f77a": ResourceMetrics(
        resource_id="vol-044d55e66f77a",
        observation_days=14,
        disk_iops=310.0,
        has_sufficient_data=True,
    ),
}

# Total monthly cost = $499.15:
SCENARIO_B_TREND: List[CostTrendPoint] = [
    CostTrendPoint(month="April", cost=490.0, label="$490"),
    CostTrendPoint(month="May", cost=492.0, label="$492"),
    CostTrendPoint(month="June", cost=495.0, label="$495"),
    CostTrendPoint(month="July", cost=496.0, label="$496"),
    CostTrendPoint(month="August", cost=498.0, label="$498"),
    CostTrendPoint(month="September", cost=499.15, label="$499"),
]


# ---------------------------------------------------------------------------
# Scenario C: Mixed Environment
# ---------------------------------------------------------------------------
SCENARIO_C_METADATA = ScenarioMetadata(
    id="mixed-environment",
    name="Mixed Environment",
    description="Simulates an enterprise infrastructure with a single oversized EC2 host and an unattached volume alongside healthy workloads.",
    simulated=True,
    expected_findings_summary="2 differentiated findings across EC2 and EBS.",
    resource_count=7,
)

SCENARIO_C_RESOURCES: List[Resource] = [
    Resource(
        id="i-033f44e55d66c",
        name="staging-monolith",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=288.00,
        tags={"Environment": "Staging", "Service": "Monolith"},
        details={
            "instance_type": "m5.2xlarge",
            "vcpus": 8,
            "memory_gib": 32,
            "recommended_type": "m5.large",
            "recommended_cost": 78.00,
        },
    ),
    Resource(
        id="vol-055a66b77c88d",
        name="unattached-scratch-disk",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="available",
        monthly_cost=16.00,
        tags={"Environment": "Staging"},
        details={"volume_type": "gp3", "size_gb": 200, "days_unattached": 18},
    ),
    Resource(
        id="i-044e55d66c77b",
        name="prod-auth-service",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=61.20,
        tags={"Environment": "Production", "Service": "Auth"},
        details={"instance_type": "c5.large"},
    ),
    Resource(
        id="vol-066b77c88d99e",
        name="vol-prod-auth",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="in-use",
        monthly_cost=8.00,
        tags={"Environment": "Production"},
        details={"volume_type": "gp3", "size_gb": 100},
    ),
    Resource(
        id="app-assets-bucket",
        name="app-assets-bucket",
        resource_type=ResourceType.S3,
        region="us-east-1",
        status="active",
        monthly_cost=18.40,
        tags={"Environment": "Production"},
        details={"storage_class": "Standard", "lifecycle_policy": "Enabled"},
    ),
    Resource(
        id="rds-postgres-primary",
        name="rds-postgres-primary",
        resource_type=ResourceType.RDS,
        region="us-east-1",
        status="available",
        monthly_cost=130.00,
        tags={"Environment": "Production"},
        details={"instance_class": "db.m5.large"},
    ),
    Resource(
        id="rds-postgres-replica",
        name="rds-postgres-replica",
        resource_type=ResourceType.RDS,
        region="us-east-1",
        status="available",
        monthly_cost=130.00,
        tags={"Environment": "Production"},
        details={"instance_class": "db.m5.large"},
    ),
]

SCENARIO_C_METRICS: Dict[str, ResourceMetrics] = {
    "i-033f44e55d66c": ResourceMetrics(
        resource_id="i-033f44e55d66c",
        observation_days=14,
        avg_cpu_percent=4.2,
        peak_cpu_percent=14.8,
        network_in_bytes_sec=85000.0,
        has_sufficient_data=True,
    ),
    "vol-055a66b77c88d": ResourceMetrics(
        resource_id="vol-055a66b77c88d",
        observation_days=18,
        disk_iops=0.0,
        has_sufficient_data=True,
    ),
    "i-044e55d66c77b": ResourceMetrics(
        resource_id="i-044e55d66c77b",
        observation_days=14,
        avg_cpu_percent=58.0,
        peak_cpu_percent=74.5,
        network_in_bytes_sec=210000.0,
        has_sufficient_data=True,
    ),
}

# Total monthly cost = $651.60:
SCENARIO_C_TREND: List[CostTrendPoint] = [
    CostTrendPoint(month="April", cost=580.0, label="$580"),
    CostTrendPoint(month="May", cost=605.0, label="$605"),
    CostTrendPoint(month="June", cost=620.0, label="$620"),
    CostTrendPoint(month="July", cost=635.0, label="$635"),
    CostTrendPoint(month="August", cost=645.0, label="$645"),
    CostTrendPoint(month="September", cost=651.60, label="$652"),
]


# ---------------------------------------------------------------------------
# Scenario D: Insufficient Data & Observability Gaps
# ---------------------------------------------------------------------------
SCENARIO_D_METADATA = ScenarioMetadata(
    id="insufficient-data",
    name="Insufficient Data",
    description="Simulates an environment with recent launches (< 7 days) and missing CloudWatch metrics to verify false-positive suppression.",
    simulated=True,
    expected_findings_summary="0 false findings. Transparent data limitation notices displayed.",
    resource_count=5,
)

SCENARIO_D_RESOURCES: List[Resource] = [
    Resource(
        id="i-066e55d44c33b",
        name="newly-launched-worker",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=122.40,
        tags={"Environment": "Staging"},
        details={"instance_type": "c5.xlarge"},
    ),
    Resource(
        id="i-099d88c77b66a",
        name="uninstrumented-legacy-node",
        resource_type=ResourceType.EC2,
        region="us-east-1",
        status="running",
        monthly_cost=120.00,
        tags={"Environment": "Legacy"},
        details={"instance_type": "t3.xlarge"},
    ),
    Resource(
        id="vol-077c66d55e44f",
        name="newly-created-volume",
        resource_type=ResourceType.EBS,
        region="us-east-1",
        status="available",
        monthly_cost=8.00,
        tags={"Environment": "Development"},
        details={"volume_type": "gp3", "size_gb": 100, "days_unattached": 0},
    ),
    Resource(
        id="experiment-raw-datasets",
        name="experiment-raw-datasets",
        resource_type=ResourceType.S3,
        region="us-west-2",
        status="active",
        monthly_cost=18.40,
        tags={"Environment": "Research"},
        details={"storage_class": "Standard", "lifecycle_policy": None},
    ),
    Resource(
        id="dev-rds-sandbox",
        name="dev-rds-sandbox",
        resource_type=ResourceType.RDS,
        region="us-east-1",
        status="available",
        monthly_cost=130.00,
        tags={"Environment": "Development"},
        details={"instance_class": "db.m5.large"},
    ),
]

SCENARIO_D_METRICS: Dict[str, ResourceMetrics] = {
    "i-066e55d44c33b": ResourceMetrics(
        resource_id="i-066e55d44c33b",
        observation_days=2,  # < 7 days threshold
        avg_cpu_percent=4.8,
        peak_cpu_percent=12.0,
        has_sufficient_data=False,
        data_quality_warning="Telemetry window (2 days) is insufficient. Minimum 7-day observation required.",
    ),
    "i-099d88c77b66a": ResourceMetrics(
        resource_id="i-099d88c77b66a",
        observation_days=14,
        avg_cpu_percent=None,  # Missing CloudWatch metric!
        peak_cpu_percent=None,
        has_sufficient_data=False,
        data_quality_warning="Missing CloudWatch CPUUtilization telemetry. Check CloudWatch agent.",
    ),
    "vol-077c66d55e44f": ResourceMetrics(
        resource_id="vol-077c66d55e44f",
        observation_days=0,
        disk_iops=None,
        has_sufficient_data=False,
        data_quality_warning="Volume created less than 24 hours ago. Attachment telemetry requires stabilization period.",
    ),
    "experiment-raw-datasets": ResourceMetrics(
        resource_id="experiment-raw-datasets",
        observation_days=3,
        current_storage_gb=800.0,
        storage_growth_gb=None,
        storage_growth_percent=None,
        has_sufficient_data=False,
        data_quality_warning="Bucket age (3 days) is insufficient for 30-day growth rate calculation.",
    ),
}

# Total monthly cost = $398.80:
SCENARIO_D_TREND: List[CostTrendPoint] = [
    CostTrendPoint(month="July", cost=120.0, label="$120"),
    CostTrendPoint(month="August", cost=260.0, label="$260"),
    CostTrendPoint(month="September", cost=398.80, label="$399"),
]

SCENARIO_REGISTRY: Dict[str, ScenarioDefinition] = {
    "high-cost-waste": ScenarioDefinition(
        metadata=SCENARIO_A_METADATA,
        resources=SCENARIO_A_RESOURCES,
        metrics=SCENARIO_A_METRICS,
        cost_trend=SCENARIO_A_TREND,
    ),
    "healthy-environment": ScenarioDefinition(
        metadata=SCENARIO_B_METADATA,
        resources=SCENARIO_B_RESOURCES,
        metrics=SCENARIO_B_METRICS,
        cost_trend=SCENARIO_B_TREND,
    ),
    "mixed-environment": ScenarioDefinition(
        metadata=SCENARIO_C_METADATA,
        resources=SCENARIO_C_RESOURCES,
        metrics=SCENARIO_C_METRICS,
        cost_trend=SCENARIO_C_TREND,
    ),
    "insufficient-data": ScenarioDefinition(
        metadata=SCENARIO_D_METADATA,
        resources=SCENARIO_D_RESOURCES,
        metrics=SCENARIO_D_METRICS,
        cost_trend=SCENARIO_D_TREND,
    ),
}
