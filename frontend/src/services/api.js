/**
 * API Service for AWS Cloud Cost Optimiser
 * 
 * Communicates with the FastAPI backend.
 * Normalizes backend responses into consistent frontend data contracts.
 */

const API_BASE_URL = 'http://127.0.0.1:8000';

/**
 * Normalizes API response fields to support both camelCase and snake_case
 */
function normalizeDashboardData(data) {
  if (!data) return null;

  return {
    metadata: {
      scenarioId: data.metadata?.scenario_id || data.metadata?.scenarioId || 'high-cost-waste',
      scenarioName: data.metadata?.scenario_name || data.metadata?.scenarioName || 'High Cost & Resource Waste',
      month: data.metadata?.month || 'September 2026',
      lastAnalysis: data.metadata?.last_analysis || data.metadata?.lastAnalysis || 'Just now',
      statusText: data.metadata?.status_text || data.metadata?.statusText || 'Analysis data available',
      isReadOnly: data.metadata?.is_read_only ?? true,
      isSimulated: data.metadata?.is_simulated ?? true,
      totalResourcesScanned: data.metadata?.total_resources_scanned || data.metadata?.totalResourcesScanned || 0,
      dataLimitationsActive: data.metadata?.data_limitations_active ?? false,
      dataLimitationsNotice: data.metadata?.data_limitations_notice || null,
    },
    summary: {
      monthlyCost: {
        value: data.summary?.monthly_cost?.value ?? 0,
        formatted: data.summary?.monthly_cost?.formatted || '$0.00',
        changePercentage: data.summary?.monthly_cost?.change_percentage ?? 0,
        changeType: data.summary?.monthly_cost?.change_type || 'neutral',
        label: data.summary?.monthly_cost?.label || 'Monthly cost',
        supportingText: data.summary?.monthly_cost?.supporting_text || '',
      },
      potentialSavings: {
        value: data.summary?.potential_savings?.value ?? 0,
        formatted: data.summary?.potential_savings?.formatted || '$0.00',
        percentageOfSpend: data.summary?.potential_savings?.percentage_of_spend ?? 0,
        label: data.summary?.potential_savings?.label || 'Potential monthly savings',
        supportingText: data.summary?.potential_savings?.supporting_text || '',
      },
      findingsCount: {
        value: data.summary?.findings_count?.value ?? 0,
        highPriorityCount: data.summary?.findings_count?.high_priority_count ?? 0,
        mediumPriorityCount: data.summary?.findings_count?.medium_priority_count ?? 0,
        lowPriorityCount: data.summary?.findings_count?.low_priority_count ?? 0,
        label: data.summary?.findings_count?.label || 'Findings to review',
        supportingText: data.summary?.findings_count?.supporting_text || '',
      },
    },
    costTrend: (data.cost_trend || []).map((point) => ({
      month: point.month,
      cost: point.cost,
      label: point.label || `$${Math.round(point.cost).toLocaleString()}`,
    })),
    serviceSpend: (data.service_spend || []).map((svc) => ({
      id: svc.id,
      name: svc.name,
      category: svc.category,
      spend: svc.spend,
      formattedSpend: svc.formatted_spend || `$${Math.round(svc.spend).toLocaleString()}`,
      percentage: svc.percentage,
      color: svc.color,
    })),
    priorityFindings: (data.priority_findings || []).map((f) => ({
      id: f.id,
      resourceId: f.resource_id,
      resourceName: f.resource_name,
      service: f.service,
      ruleId: f.rule_id,
      title: f.title,
      description: f.description,
      priority: f.priority,
      estimatedSavings: f.estimated_savings,
      estimatedSavingsFormatted: f.estimated_savings_formatted || (f.estimated_savings ? `$${Math.round(f.estimated_savings)}/mo` : 'N/A'),
      confidence: f.confidence,
      risk: f.risk,
      reasoning: f.reasoning,
      evidence: f.evidence || [],
      verificationGuidance: f.verification_guidance,
      savingsAssumptions: f.savings_assumptions,
      confidenceRationale: f.confidence_rationale,
      riskRationale: f.risk_rationale,
      observationWindow: f.observation_window,
      dataQualityWarnings: f.data_quality_warnings || [],
      suggestedAction: f.suggested_action || 'Review in AWS Console',
      awsConsoleUrl: f.aws_console_url || '',
    })),
    recentActivity: (data.recent_activity || []).map((act) => ({
      id: act.id,
      title: act.title,
      detail: act.detail,
      timeAgo: act.time_ago || act.timeAgo || 'Just now',
      type: act.type,
    })),
  };
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) throw new Error(`Health check failed with status ${res.status}`);
  return res.json();
}

export async function fetchScenarios() {
  const res = await fetch(`${API_BASE_URL}/api/scenarios`);
  if (!res.ok) throw new Error(`Failed to fetch scenarios (HTTP ${res.status})`);
  return res.json();
}

export async function fetchDashboard(scenarioId = 'high-cost-waste') {
  const url = `${API_BASE_URL}/api/dashboard?scenario=${encodeURIComponent(scenarioId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to fetch dashboard (HTTP ${res.status})`);
  }
  const rawData = await res.json();
  return normalizeDashboardData(rawData);
}

export async function fetchRecommendations(scenarioId = 'high-cost-waste') {
  const url = `${API_BASE_URL}/api/recommendations?scenario=${encodeURIComponent(scenarioId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch recommendations (HTTP ${res.status})`);
  return res.json();
}

export async function fetchResources(scenarioId = 'high-cost-waste') {
  const url = `${API_BASE_URL}/api/resources?scenario=${encodeURIComponent(scenarioId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch resources (HTTP ${res.status})`);
  return res.json();
}

export async function fetchChangePassport(recommendationId, scenarioId = 'high-cost-waste') {
  const url = `${API_BASE_URL}/api/change-passport/${encodeURIComponent(recommendationId)}?scenario=${encodeURIComponent(scenarioId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to fetch Change Passport (HTTP ${res.status})`);
  }
  return res.json();
}

export async function simulateChange(scenarioId, recommendationId, actionId) {
  const res = await fetch(`${API_BASE_URL}/api/change-passport/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_id: scenarioId,
      recommendation_id: recommendationId,
      action_id: actionId,
    }),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to simulate change (HTTP ${res.status})`);
  }
  return res.json();
}

export async function undoSimulation(scenarioId, recommendationId) {
  const res = await fetch(`${API_BASE_URL}/api/change-passport/simulate/undo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_id: scenarioId,
      recommendation_id: recommendationId,
    }),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to undo simulation (HTTP ${res.status})`);
  }
  return res.json();
}

export async function toggleAttestation(scenarioId, checkId, attested) {
  const res = await fetch(`${API_BASE_URL}/api/change-passport/attest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_id: scenarioId,
      check_id: checkId,
      attested: attested,
    }),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to toggle attestation (HTTP ${res.status})`);
  }
  return res.json();
}
