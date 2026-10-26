"""Domain and API schemas for AWS Cloud Cost Optimiser.

Includes resource inventory, metrics, recommendations, dashboard models,
and the Change Passport domain schemas. All financial values are represented
as numeric floats with presentation helpers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    EC2 = "EC2"
    EBS = "EBS"
    S3 = "S3"
    RDS = "RDS"


class Resource(BaseModel):
    id: str
    name: str
    resource_type: ResourceType
    region: str
    status: str
    monthly_cost: float
    tags: Dict[str, str] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)


class ResourceMetrics(BaseModel):
    resource_id: str
    observation_days: int
    avg_cpu_percent: Optional[float] = None
    peak_cpu_percent: Optional[float] = None
    network_in_bytes_sec: Optional[float] = None
    network_out_bytes_sec: Optional[float] = None
    disk_iops: Optional[float] = None
    current_storage_gb: Optional[float] = None
    storage_growth_gb: Optional[float] = None
    storage_growth_percent: Optional[float] = None
    has_sufficient_data: bool = True
    data_quality_warning: Optional[str] = None


class EvidenceItem(BaseModel):
    label: str
    value: str


class Recommendation(BaseModel):
    id: str
    resource_id: str
    resource_name: Optional[str] = None
    service: str  # e.g. "EC2", "EBS", "S3"
    rule_id: str
    title: str
    description: str
    priority: str  # "HIGH", "MEDIUM", "LOW"
    estimated_savings: Optional[float] = None
    estimated_savings_formatted: Optional[str] = None
    confidence: int  # 0 to 100
    risk: str  # "Low", "Medium", "High"
    reasoning: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    verification_guidance: str
    savings_assumptions: Optional[str] = None
    confidence_rationale: Optional[str] = None
    risk_rationale: Optional[str] = None
    observation_window: Optional[str] = None
    data_quality_warnings: List[str] = Field(default_factory=list)
    suggested_action: str = "Review in AWS Console"
    aws_console_url: str = ""


class ScenarioMetadata(BaseModel):
    id: str
    name: str
    description: str
    simulated: bool = True
    expected_findings_summary: str
    resource_count: int


class MonthlyCostKPI(BaseModel):
    value: float
    formatted: str
    change_percentage: float
    change_type: str  # "increase", "decrease", "neutral"
    label: str = "Monthly cost"
    supporting_text: str


class PotentialSavingsKPI(BaseModel):
    value: float
    formatted: str
    percentage_of_spend: float
    label: str = "Potential monthly savings"
    supporting_text: str


class FindingsCountKPI(BaseModel):
    value: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    label: str = "Findings to review"
    supporting_text: str


class DashboardSummary(BaseModel):
    monthly_cost: MonthlyCostKPI
    potential_savings: PotentialSavingsKPI
    findings_count: FindingsCountKPI


class CostTrendPoint(BaseModel):
    month: str
    cost: float
    label: str


class ServiceSpendItem(BaseModel):
    id: str
    name: str
    category: str
    spend: float
    formatted_spend: str
    percentage: float
    color: str


class ActivityItem(BaseModel):
    id: str
    title: str
    detail: str
    time_ago: str
    type: str  # "complete", "service", "warning", "simulation"


class DashboardMetadata(BaseModel):
    scenario_id: str
    scenario_name: str
    month: str
    last_analysis: str
    status_text: str
    is_read_only: bool = True
    is_simulated: bool = True
    total_resources_scanned: int
    data_limitations_active: bool = False
    data_limitations_notice: Optional[str] = None


class DashboardResponse(BaseModel):
    metadata: DashboardMetadata
    summary: DashboardSummary
    cost_trend: List[CostTrendPoint]
    service_spend: List[ServiceSpendItem]
    priority_findings: List[Recommendation]
    recent_activity: List[ActivityItem]


# ---------------------------------------------------------------------------
# Change Passport Domain Schemas
# ---------------------------------------------------------------------------

class ReviewCheckStatus(str, Enum):
    PASSED = "PASSED"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewCheckItem(BaseModel):
    id: str
    title: str
    description: str
    status: ReviewCheckStatus
    evidence_or_requirement: str
    user_attested: bool = False
    attestation_note: Optional[str] = None


class DepartmentReview(BaseModel):
    department: str  # "Finance / FinOps", "Engineering", "Security / Compliance", "SRE / Operations"
    status: ReviewCheckStatus
    summary: str
    checks: List[ReviewCheckItem] = Field(default_factory=list)


class ProposedAction(BaseModel):
    id: str
    title: str
    description: str
    is_recommended: bool = False
    projected_monthly_savings: float
    projected_annual_savings: float
    net_monthly_savings: float
    risk_level: str
    reversibility: str
    action_type: str  # "snapshot_and_delete", "immediate_delete", "retain_and_tag"


class ValidationCheckItem(BaseModel):
    id: str
    step_number: int
    title: str
    guidance: str
    is_mandatory: bool = True


class FinancialImpact(BaseModel):
    estimated_avoidable_monthly_cost: float
    annualized_avoidable_cost: float
    projected_monthly_savings: float
    projected_annual_savings: float
    snapshot_cost_monthly: float
    net_projected_savings_monthly: float
    net_projected_savings_annual: float
    realized_savings_status: str = "Unavailable — requires post-change billing telemetry"
    calculation_breakdown: List[str] = Field(default_factory=list)
    pricing_assumptions: List[str] = Field(default_factory=list)
    exclusions_and_limitations: List[str] = Field(default_factory=list)


class DecisionStatus(str, Enum):
    NEEDS_REVIEW = "Needs review"
    READY_FOR_SIMULATION = "Ready for simulation"
    BLOCKED_BY_EVIDENCE = "Blocked by missing evidence"
    SIMULATED = "Simulated"


class SimulationResult(BaseModel):
    is_simulated: bool = False
    action_id: str
    action_title: str
    original_monthly_cost: float
    projected_monthly_cost: float
    monthly_savings_delta: float
    annual_savings_delta: float
    simulated_resource_state: str
    simulation_timestamp: str
    assumptions_applied: List[str] = Field(default_factory=list)
    remaining_risks: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "Hypothetical simulation only. No live AWS resources were stopped, deleted, or altered. "
        "Projected savings are illustrative and not verified realized savings."
    )


class ChangePassport(BaseModel):
    passport_id: str
    scenario_id: str
    scenario_name: str
    recommendation_id: str
    resource_id: str
    resource_name: Optional[str] = None
    resource_type: str
    region: str
    title: str
    summary: str
    rationale: str
    decision_status: DecisionStatus
    decision_status_explanation: str
    financial_impact: FinancialImpact
    evidence: List[EvidenceItem] = Field(default_factory=list)
    data_limitations: List[str] = Field(default_factory=list)
    departmental_reviews: Dict[str, DepartmentReview] = Field(default_factory=dict)
    validation_checklist: List[ValidationCheckItem] = Field(default_factory=list)
    rollback_recovery_plan: str
    proposed_actions: List[ProposedAction] = Field(default_factory=list)
    selected_action_id: str
    simulation_result: Optional[SimulationResult] = None


class SimulateRequest(BaseModel):
    scenario_id: str
    recommendation_id: str
    action_id: str


class UndoSimulateRequest(BaseModel):
    scenario_id: str
    recommendation_id: str
