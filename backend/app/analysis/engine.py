"""Analysis Engine for AWS Cloud Cost Optimiser.

Orchestrates rule evaluations, dashboard summaries, service spend distributions,
and generates explainable Change Passports with What-If change simulations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.analysis.rules import (
    BaseRule,
    EBSUnattachedRule,
    EC2IdleRule,
    EC2RightsizingRule,
    S3LifecycleRule,
)
from app.models import (
    ActivityItem,
    ChangePassport,
    CostTrendPoint,
    DashboardMetadata,
    DashboardResponse,
    DashboardSummary,
    DecisionStatus,
    DepartmentReview,
    EvidenceItem,
    FinancialImpact,
    FindingsCountKPI,
    MonthlyCostKPI,
    PotentialSavingsKPI,
    ProposedAction,
    Recommendation,
    ReviewCheckItem,
    ReviewCheckStatus,
    ServiceSpendItem,
    SimulationResult,
    ValidationCheckItem,
)
from app.providers.base import CloudProvider


class AnalysisEngine:
    """Core analysis engine orchestrating rules, metrics, and Change Passports."""

    def __init__(self, provider: CloudProvider, rules: Optional[List[BaseRule]] = None):
        self.provider = provider
        self.rules: List[BaseRule] = rules or [
            EC2IdleRule(),
            EC2RightsizingRule(),
            EBSUnattachedRule(),
            S3LifecycleRule(),
        ]
        self._simulations: Dict[str, SimulationResult] = {}
        self._attestations: Dict[str, bool] = {}

    def get_recommendations_for_scenario(self, scenario_id: str) -> List[Recommendation]:
        """Evaluate all rules against all resources in the scenario."""
        resources = self.provider.get_resources(scenario_id)
        findings: List[Recommendation] = []

        for resource in resources:
            metrics = self.provider.get_metrics(resource.id, scenario_id)
            for rule in self.rules:
                rec = rule.evaluate(resource, metrics)
                if rec:
                    findings.append(rec)

        priority_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        findings.sort(
            key=lambda r: (priority_order.get(r.priority, 0), r.estimated_savings or 0.0),
            reverse=True,
        )
        return findings

    def analyze_scenario(self, scenario_id: str) -> Optional[DashboardResponse]:
        """Generate complete dashboard data and analytics for a scenario."""
        meta = self.provider.get_scenario_metadata(scenario_id)
        if not meta:
            return None

        resources = self.provider.get_resources(scenario_id)
        findings = self.get_recommendations_for_scenario(scenario_id)
        cost_trend = self.provider.get_historical_cost_trend(scenario_id)

        base_monthly_cost = sum(r.monthly_cost for r in resources)

        active_sim_savings = 0.0
        for key, sim in self._simulations.items():
            if key.startswith(f"{scenario_id}:") and sim.is_simulated:
                active_sim_savings += sim.monthly_savings_delta

        current_monthly_cost = max(0.0, base_monthly_cost - active_sim_savings)

        change_pct = 0.0
        change_type = "neutral"
        if len(cost_trend) >= 2:
            prev_cost = cost_trend[-2].cost
            if prev_cost > 0:
                change_pct = round(((base_monthly_cost - prev_cost) / prev_cost) * 100, 1)
                change_type = "increase" if change_pct > 0 else ("decrease" if change_pct < 0 else "neutral")

        total_potential_savings = sum(f.estimated_savings or 0.0 for f in findings)
        savings_pct = round((total_potential_savings / base_monthly_cost * 100), 1) if base_monthly_cost > 0 else 0.0

        high_cnt = sum(1 for f in findings if f.priority == "HIGH")
        med_cnt = sum(1 for f in findings if f.priority == "MEDIUM")
        low_cnt = sum(1 for f in findings if f.priority == "LOW")

        summary = DashboardSummary(
            monthly_cost=MonthlyCostKPI(
                value=round(current_monthly_cost, 2),
                formatted=f"${current_monthly_cost:,.2f}",
                change_percentage=abs(change_pct),
                change_type=change_type,
                label="Monthly cost",
                supporting_text=(
                    f"Reflects active simulated savings (-${active_sim_savings:.2f}/mo)"
                    if active_sim_savings > 0
                    else ("+15.2% vs last month" if change_type == "increase" else "On track with baseline")
                ),
            ),
            potential_savings=PotentialSavingsKPI(
                value=round(total_potential_savings, 2),
                formatted=f"${total_potential_savings:,.2f}",
                percentage_of_spend=savings_pct,
                label="Potential monthly savings",
                supporting_text=f"{savings_pct:.0f}% of total spend identified as optimizable",
            ),
            findings_count=FindingsCountKPI(
                value=len(findings),
                high_priority_count=high_cnt,
                medium_priority_count=med_cnt,
                low_priority_count=low_cnt,
                label="Findings to review",
                supporting_text=f"{high_cnt} high priority requiring engineering attention",
            ),
        )

        service_spend_map: Dict[str, float] = {}
        for r in resources:
            svc = r.resource_type.value
            service_spend_map[svc] = service_spend_map.get(svc, 0.0) + r.monthly_cost

        color_palette = {
            "EC2": "#3b82f6",
            "RDS": "#10b981",
            "S3": "#f59e0b",
            "EBS": "#8b5cf6",
        }

        service_spend_items: List[ServiceSpendItem] = []
        for svc, spend in sorted(service_spend_map.items(), key=lambda x: x[1], reverse=True):
            pct = round((spend / base_monthly_cost * 100), 1) if base_monthly_cost > 0 else 0.0
            service_spend_items.append(
                ServiceSpendItem(
                    id=svc.lower(),
                    name=f"Amazon {svc}",
                    category="Infrastructure",
                    spend=round(spend, 2),
                    formatted_spend=f"${spend:,.2f}",
                    percentage=pct,
                    color=color_palette.get(svc, "#6b7280"),
                )
            )

        activity_items: List[ActivityItem] = [
            ActivityItem(
                id="act-1",
                title="Telemetry scan completed",
                detail=f"Analyzed {len(resources)} resources across {scenario_id}.",
                time_ago="10m ago",
                type="complete",
            ),
        ]

        if active_sim_savings > 0:
            activity_items.insert(
                0,
                ActivityItem(
                    id="act-sim",
                    title="What-If Simulation Active",
                    detail=f"Projecting -${active_sim_savings:.2f}/mo reduction in monthly infrastructure billing.",
                    time_ago="Just now",
                    type="simulation",
                ),
            )
        elif findings:
            activity_items.append(
                ActivityItem(
                    id="act-2",
                    title="Optimization findings flagged",
                    detail=f"Identified {len(findings)} explainable recommendations (${total_potential_savings:,.2f}/mo potential savings).",
                    time_ago="25m ago",
                    type="warning",
                )
            )

        dashboard_meta = DashboardMetadata(
            scenario_id=scenario_id,
            scenario_name=meta.name,
            month="September 2026",
            last_analysis="Today, 14:32 UTC",
            status_text="Analysis complete",
            is_read_only=True,
            is_simulated=True,
            total_resources_scanned=len(resources),
            data_limitations_active=(scenario_id == "insufficient-data"),
            data_limitations_notice=(
                "Some resources have observation windows < 7 days or missing CloudWatch metrics. "
                "Optimization rules require sufficient baseline data before generating savings estimates."
                if scenario_id == "insufficient-data"
                else None
            ),
        )

        return DashboardResponse(
            metadata=dashboard_meta,
            summary=summary,
            cost_trend=cost_trend,
            service_spend=service_spend_items,
            priority_findings=findings,
            recent_activity=activity_items,
        )

    # -----------------------------------------------------------------------
    # Change Passport Generation & What-If Simulation
    # -----------------------------------------------------------------------

    def generate_change_passport(self, recommendation_id: str, scenario_id: str) -> Optional[ChangePassport]:
        """Generate a complete, explainable Change Passport for a recommendation."""
        findings = self.get_recommendations_for_scenario(scenario_id)
        target_rec = next((r for r in findings if r.id == recommendation_id), None)

        if not target_rec:
            return None

        sim_key = f"{scenario_id}:{recommendation_id}"
        existing_sim = self._simulations.get(sim_key)

        if target_rec.service == "EBS" or "vol-0a7f82c9" in target_rec.resource_id:
            return self._build_ebs_change_passport(target_rec, scenario_id, existing_sim)

        return self._build_generic_change_passport(target_rec, scenario_id, existing_sim)

    def _build_ebs_change_passport(
        self, rec: Recommendation, scenario_id: str, sim: Optional[SimulationResult]
    ) -> ChangePassport:
        """Construct the comprehensive EBS Unattached Volume Change Passport."""
        avoidable_monthly = 40.00
        annualized_avoidable = 480.00
        snapshot_cost = 12.50
        net_monthly_with_snapshot = 27.50
        net_annual_with_snapshot = 330.00

        eng_attested = self._attestations.get(f"{scenario_id}:eng-1", False)
        sec_attested = self._attestations.get(f"{scenario_id}:sec-1", False)

        reviews: Dict[str, DepartmentReview] = {
            "Finance": DepartmentReview(
                department="Finance / FinOps",
                status=ReviewCheckStatus.PASSED,
                summary="Cost center confirmed; ROI is overwhelmingly positive with zero capital expenditure.",
                checks=[
                    ReviewCheckItem(
                        id="fin-1",
                        title="Cost Allocation & Ownership",
                        description="Verify tag ownership aligns with responsible engineering budget.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="Tag 'CreatedBy: migration-job' maps to Analytics Data Platform budget.",
                        user_attested=True,
                    ),
                    ReviewCheckItem(
                        id="fin-2",
                        title="Financial Impact & Materiality",
                        description="Annualized savings justify administrative change review.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="Decommissioning yields $330.00/yr net savings (with safety snapshot) or $480.00/yr (immediate delete).",
                        user_attested=True,
                    ),
                ],
            ),
            "Engineering": DepartmentReview(
                department="Engineering",
                status=ReviewCheckStatus.PASSED if eng_attested else ReviewCheckStatus.REQUIRES_VERIFICATION,
                summary="Owner confirmation required to ensure migration backfill data has been persisted to warehouse.",
                checks=[
                    ReviewCheckItem(
                        id="eng-1",
                        title="Migration Job Completion Verification",
                        description="Confirm that the data migration batch pipeline finalized successfully in August.",
                        status=ReviewCheckStatus.PASSED if eng_attested else ReviewCheckStatus.REQUIRES_VERIFICATION,
                        evidence_or_requirement="Migration team must verify target PostgreSQL warehouse tables are fully populated.",
                        user_attested=eng_attested,
                    ),
                    ReviewCheckItem(
                        id="eng-2",
                        title="Mount Point & Script Dependencies",
                        description="Ensure no running EC2 instance has hardcoded dependencies on this volume ID.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="Volume has been unattached for 31 days with 0 CloudTrail attachment attempts.",
                        user_attested=True,
                    ),
                ],
            ),
            "Security": DepartmentReview(
                department="Security / Compliance",
                status=ReviewCheckStatus.PASSED if sec_attested else ReviewCheckStatus.REQUIRES_VERIFICATION,
                summary="Ensure regulatory data retention policies do not mandate keeping raw EBS block storage.",
                checks=[
                    ReviewCheckItem(
                        id="sec-1",
                        title="Data Classification & Retention Policy",
                        description="Verify volume contains no unencrypted customer PII or compliance-mandated audit logs.",
                        status=ReviewCheckStatus.PASSED if sec_attested else ReviewCheckStatus.REQUIRES_VERIFICATION,
                        evidence_or_requirement="Check data classification policy: temporary staging volumes are eligible for snapshot + purge.",
                        user_attested=sec_attested,
                    ),
                    ReviewCheckItem(
                        id="sec-2",
                        title="Encryption Key Availability",
                        description="Confirm AWS KMS CMK will remain accessible if snapshot restoration is needed.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="Volume encrypted with standard default aws/ebs key. No key deprecation risks.",
                        user_attested=True,
                    ),
                ],
            ),
            "Operations": DepartmentReview(
                department="SRE / Operations",
                status=ReviewCheckStatus.PASSED,
                summary="Pre-deletion snapshot hook and rollback runbook are validated.",
                checks=[
                    ReviewCheckItem(
                        id="ops-1",
                        title="Safety Snapshot Enforcement",
                        description="A point-in-time snapshot must be created prior to calling ec2:DeleteVolume.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="Simulated snapshot 'snap-sim-0a7f82c9' verified. Restore capability tested.",
                        user_attested=True,
                    ),
                    ReviewCheckItem(
                        id="ops-2",
                        title="CloudTrail Detach Verification",
                        description="Confirm no concurrent I/O or detachment errors occurred.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="CloudTrail confirms clean detach on August 26, 2026. Zero I/O recorded.",
                        user_attested=True,
                    ),
                ],
            ),
        }

        proposed_actions: List[ProposedAction] = [
            ProposedAction(
                id="snapshot_and_delete",
                title="Create Safety Snapshot, then Delete Volume (Recommended)",
                description=(
                    "Creates an immutable EBS snapshot ('snap-sim-0a7f82c9') before deleting the volume. "
                    "Eliminates $40.00/mo volume charge while adding $12.50/mo snapshot storage. Net savings: $27.50/mo."
                ),
                is_recommended=True,
                projected_monthly_savings=avoidable_monthly,
                projected_annual_savings=annualized_avoidable,
                net_monthly_savings=net_monthly_with_snapshot,
                risk_level="Low",
                reversibility="High (Full snapshot restore available in < 15 mins)",
                action_type="snapshot_and_delete",
            ),
            ProposedAction(
                id="immediate_delete",
                title="Delete Volume Immediately Without Snapshot",
                description=(
                    "Deletes the EBS volume immediately. Maximizes cost reduction by avoiding snapshot storage charges ($12.50/mo), "
                    "but creates permanent data loss risk if uncommitted files were stored."
                ),
                is_recommended=False,
                projected_monthly_savings=avoidable_monthly,
                projected_annual_savings=annualized_avoidable,
                net_monthly_savings=avoidable_monthly,
                risk_level="High",
                reversibility="None (Permanent deletion)",
                action_type="immediate_delete",
            ),
            ProposedAction(
                id="retain_and_tag",
                title="Retain Volume and Apply Acknowledged Tag",
                description=(
                    "Keeps the volume in 'available' status and tags it with 'Status: IntentionallyUnattached'. "
                    "Zero cost reduction, but documents intentionality."
                ),
                is_recommended=False,
                projected_monthly_savings=0.0,
                projected_annual_savings=0.0,
                net_monthly_savings=0.0,
                risk_level="Low",
                reversibility="N/A",
                action_type="retain_and_tag",
            ),
        ]

        checklist: List[ValidationCheckItem] = [
            ValidationCheckItem(
                id="val-1",
                step_number=1,
                title="Verify CloudTrail Detachment Timestamp",
                guidance="Execute `aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=vol-0a7f82c9e4b1a3d5e` to confirm no recent attachment requests.",
                is_mandatory=True,
            ),
            ValidationCheckItem(
                id="val-2",
                step_number=2,
                title="Verify Analytics Owner Sign-off",
                guidance="Obtain sign-off from the Analytics data engineering lead that the August migration job has completed without outstanding data backfills.",
                is_mandatory=True,
            ),
            ValidationCheckItem(
                id="val-3",
                step_number=3,
                title="Execute Pre-Deletion EBS Snapshot",
                guidance="Execute `aws ec2 create-snapshot --volume-id vol-0a7f82c9e4b1a3d5e --description 'pre-decommission backup' --tag-specifications 'ResourceType=snapshot,Tags=[{Key=RetentionDays,Value=30}]'`.",
                is_mandatory=True,
            ),
            ValidationCheckItem(
                id="val-4",
                step_number=4,
                title="Execute Volume Deletion",
                guidance="Execute `aws ec2 delete-volume --volume-id vol-0a7f82c9e4b1a3d5e` only after the snapshot state reaches 'completed'.",
                is_mandatory=True,
            ),
            ValidationCheckItem(
                id="val-5",
                step_number=5,
                title="Set Snapshot Expiration Lifecycle",
                guidance="Ensure AWS Backup or an AWS DLM lifecycle policy is configured to purge the pre-deletion snapshot after 30 days to avoid perpetual snapshot cost.",
                is_mandatory=False,
            ),
        ]

        financial_impact = FinancialImpact(
            estimated_avoidable_monthly_cost=avoidable_monthly,
            annualized_avoidable_cost=annualized_avoidable,
            projected_monthly_savings=avoidable_monthly,
            projected_annual_savings=annualized_avoidable,
            snapshot_cost_monthly=snapshot_cost,
            net_projected_savings_monthly=net_monthly_with_snapshot,
            net_projected_savings_annual=net_annual_with_snapshot,
            realized_savings_status="Unavailable — requires post-change billing telemetry",
            calculation_breakdown=[
                "Base Storage: 250 GB × $0.080/GB-month = $20.00/mo",
                "Provisioned IOPS: (6,000 IOPS - 3,000 baseline) × $0.005/IOPS-month = $15.00/mo",
                "Provisioned Throughput: (250 MB/s - 125 MB/s baseline) × $0.040/MB/s-month = $5.00/mo",
                "Total Avoidable Monthly Waste: $20.00 + $15.00 + $5.00 = $40.00/mo ($480.00/yr)",
                "Safety Snapshot Storage Overhead: 250 GB × $0.050/GB-month = $12.50/mo",
                "Net Projected Monthly Savings (with Snapshot): $40.00 - $12.50 = $27.50/mo ($330.00/yr)",
            ],
            pricing_assumptions=[
                "AWS us-east-1 On-Demand public list pricing as of September 2026",
                "gp3 includes 3,000 IOPS and 125 MB/s baseline at zero additional cost",
                "EBS standard snapshot storage charged at $0.050 per GB-month",
                "Assumes snapshot retains initial block allocations without data deduplication drift",
            ],
            exclusions_and_limitations=[
                "Excludes AWS Enterprise Discount Program (EDP) discounts or custom private pricing",
                "Excludes regional data transfer costs or KMS encryption key API request fees",
                "Excludes prospective AWS price adjustments or tax liabilities",
            ],
        )

        decision_status = DecisionStatus.SIMULATED if (sim and sim.is_simulated) else (
            DecisionStatus.READY_FOR_SIMULATION if (eng_attested and sec_attested) else DecisionStatus.NEEDS_REVIEW
        )

        explanation = (
            "What-If simulation is active. Review projected billing reduction and simulated resource state."
            if decision_status == DecisionStatus.SIMULATED
            else (
                "All departmental review items have been verified. The change is approved for hypothetical simulation."
                if decision_status == DecisionStatus.READY_FOR_SIMULATION
                else "Pending Engineering and Security attestation on migration completion and data classification."
            )
        )

        return ChangePassport(
            passport_id=f"passport-{rec.id}",
            scenario_id=scenario_id,
            scenario_name="High Cost & Resource Waste",
            recommendation_id=rec.id,
            resource_id=rec.resource_id,
            resource_name=rec.resource_name,
            resource_type="EBS",
            region="us-east-1",
            title=f"Decommission Orphaned EBS gp3 Volume ({rec.resource_name or rec.resource_id})",
            summary="Pre-change verification and risk-governed decommissioning proposal for 250 GB unattached gp3 volume with provisioned performance.",
            rationale=(
                f"Volume {rec.resource_id} has been in unattached 'available' state for 31 days with zero recorded I/O operations. "
                "Retaining this volume incurs $40.00/mo ($480.00/yr) in avoidable infrastructure costs. Decommissioning with a pre-deletion "
                "snapshot completely mitigates data loss risk while securing $27.50/mo ($330.00/yr) net savings."
            ),
            decision_status=decision_status,
            decision_status_explanation=explanation,
            financial_impact=financial_impact,
            evidence=rec.evidence,
            data_limitations=[
                "EBS volume metrics show 0 disk I/O over past 14 days; pre-detachment file system contents are not inspectable without attaching.",
                "Realized savings can only be verified after next monthly AWS billing cycle invoice generation.",
            ],
            departmental_reviews=reviews,
            validation_checklist=checklist,
            rollback_recovery_plan=(
                "If data on the volume is subsequently determined to be required, restore an identical EBS gp3 volume "
                "from the pre-deletion snapshot 'snap-sim-0a7f82c9' using: `aws ec2 create-volume --snapshot-id snap-sim-0a7f82c9 "
                "--volume-type gp3 --availability-zone us-east-1a`. Recovery time objective (RTO) is < 15 minutes; "
                "recovery point objective (RPO) is the snapshot timestamp."
            ),
            proposed_actions=proposed_actions,
            selected_action_id="snapshot_and_delete",
            simulation_result=sim,
        )

    def _build_generic_change_passport(
        self, rec: Recommendation, scenario_id: str, sim: Optional[SimulationResult]
    ) -> ChangePassport:
        """Construct a structured fallback Change Passport for other recommendations."""
        savings = rec.estimated_savings or 0.0
        annual_savings = round(savings * 12, 2)

        financial_impact = FinancialImpact(
            estimated_avoidable_monthly_cost=savings,
            annualized_avoidable_cost=annual_savings,
            projected_monthly_savings=savings,
            projected_annual_savings=annual_savings,
            snapshot_cost_monthly=0.0,
            net_projected_savings_monthly=savings,
            net_projected_savings_annual=annual_savings,
            realized_savings_status="Unavailable — requires post-change billing telemetry",
            calculation_breakdown=[
                f"Direct monthly reduction: ${savings:.2f}/mo",
                f"Annualized projection: ${annual_savings:.2f}/yr",
            ],
            pricing_assumptions=[
                "AWS us-east-1 On-Demand public list pricing as of September 2026",
            ],
            exclusions_and_limitations=[
                "Excludes AWS EDP discounts and taxes",
            ],
        )

        actions = [
            ProposedAction(
                id=f"act-{rec.id}",
                title=f"Execute: {rec.title}",
                description=rec.description,
                is_recommended=True,
                projected_monthly_savings=savings,
                projected_annual_savings=annual_savings,
                net_monthly_savings=savings,
                risk_level=rec.risk,
                reversibility="High",
                action_type="optimize",
            )
        ]

        reviews = {
            "Engineering": DepartmentReview(
                department="Engineering",
                status=ReviewCheckStatus.PASSED,
                summary="Workload requirements evaluated.",
                checks=[
                    ReviewCheckItem(
                        id="gen-eng-1",
                        title="Workload Compatibility",
                        description="Ensure change meets application SLO requirements.",
                        status=ReviewCheckStatus.PASSED,
                        evidence_or_requirement="Sufficient metric headroom confirmed.",
                        user_attested=True,
                    )
                ],
            )
        }

        checklist = [
            ValidationCheckItem(
                id="chk-1",
                step_number=1,
                title="Review CloudWatch Metrics",
                guidance=f"Inspect telemetry for {rec.resource_id} over past 14 days.",
                is_mandatory=True,
            ),
            ValidationCheckItem(
                id="chk-2",
                step_number=2,
                title="Apply Configuration Change in Staging",
                guidance="Verify application stability before modifying production environment.",
                is_mandatory=True,
            ),
        ]

        return ChangePassport(
            passport_id=f"passport-{rec.id}",
            scenario_id=scenario_id,
            scenario_name=scenario_id,
            recommendation_id=rec.id,
            resource_id=rec.resource_id,
            resource_name=rec.resource_name,
            resource_type=rec.service,
            region="us-east-1",
            title=rec.title,
            summary=rec.description,
            rationale=rec.reasoning,
            decision_status=DecisionStatus.SIMULATED if (sim and sim.is_simulated) else DecisionStatus.READY_FOR_SIMULATION,
            decision_status_explanation="Ready for hypothetical simulation.",
            financial_impact=financial_impact,
            evidence=rec.evidence,
            data_limitations=rec.data_quality_warnings,
            departmental_reviews=reviews,
            validation_checklist=checklist,
            rollback_recovery_plan="Revert configuration changes in AWS Console or Terraform if error rates elevate.",
            proposed_actions=actions,
            selected_action_id=actions[0].id,
            simulation_result=sim,
        )

    def simulate_change(
        self, scenario_id: str, recommendation_id: str, action_id: str
    ) -> SimulationResult:
        """Simulate the financial and operational impact of an optimization action."""
        resources = self.provider.get_resources(scenario_id)
        findings = self.get_recommendations_for_scenario(scenario_id)
        target_rec = next((r for r in findings if r.id == recommendation_id), None)

        original_monthly_cost = sum(r.monthly_cost for r in resources)

        if not target_rec:
            sim = SimulationResult(
                is_simulated=True,
                action_id=action_id,
                action_title="Simulated Change",
                original_monthly_cost=original_monthly_cost,
                projected_monthly_cost=original_monthly_cost,
                monthly_savings_delta=0.0,
                annual_savings_delta=0.0,
                simulated_resource_state="Unchanged",
                simulation_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            )
            return sim

        if action_id == "snapshot_and_delete":
            savings_delta = 27.50
            res_state = "Decommissioned (Snapshot created: snap-sim-0a7f82c9)"
            action_title = "Snapshot and Delete EBS Volume"
        elif action_id == "immediate_delete":
            savings_delta = 40.00
            res_state = "Permanently Deleted (No backup created)"
            action_title = "Immediate Delete EBS Volume"
        elif action_id == "retain_and_tag":
            savings_delta = 0.00
            res_state = "Retained with tag: Status=IntentionallyUnattached"
            action_title = "Retain Volume with Governance Tag"
        else:
            savings_delta = target_rec.estimated_savings or 0.0
            res_state = f"Optimized via {action_id}"
            action_title = target_rec.title

        projected_cost = max(0.0, round(original_monthly_cost - savings_delta, 2))
        annual_delta = round(savings_delta * 12, 2)

        sim_result = SimulationResult(
            is_simulated=True,
            action_id=action_id,
            action_title=action_title,
            original_monthly_cost=original_monthly_cost,
            projected_monthly_cost=projected_cost,
            monthly_savings_delta=savings_delta,
            annual_savings_delta=annual_delta,
            simulated_resource_state=res_state,
            simulation_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            assumptions_applied=[
                f"Simulated reduction of ${savings_delta:.2f}/mo applied against base spend of ${original_monthly_cost:.2f}/mo.",
                "EBS snapshot storage ($12.50/mo) factored into net savings calculation if snapshot action was chosen.",
                "No live AWS API calls executed; provider inventory remains read-only.",
            ],
            remaining_risks=[
                "Production backfills could still fail if unexpected scripts depend on this volume.",
                "Snapshot lifecycle rule must be verified to prevent long-term snapshot cost creep.",
            ],
            disclaimer=(
                "Hypothetical simulation only. No live AWS resources were stopped, deleted, or altered. "
                "Projected savings are illustrative and not verified realized savings."
            ),
        )

        sim_key = f"{scenario_id}:{recommendation_id}"
        self._simulations[sim_key] = sim_result
        return sim_result

    def undo_simulation(self, scenario_id: str, recommendation_id: str) -> bool:
        """Revert a simulated change back to original state."""
        sim_key = f"{scenario_id}:{recommendation_id}"
        if sim_key in self._simulations:
            del self._simulations[sim_key]
            return True
        return False

    def toggle_attestation(self, scenario_id: str, check_id: str, attested: bool) -> bool:
        """Toggle user attestation for a departmental review item."""
        self._attestations[f"{scenario_id}:{check_id}"] = attested
        return True
