import React, { useState, useEffect, useRef } from 'react';
import { simulateChange, undoSimulation, toggleAttestation } from '../services/api';

/**
 * ChangePassportModal Component
 * 
 * A cross-functional governance and change passport workspace for cost recommendations.
 * Transforms an isolated cost finding into an explainable, risk-managed proposal with:
 * - Evidence & financial calculation formulas
 * - 4 departmental review workflows (Finance, Engineering, Security, Operations)
 * - Interactive attestation checkboxes
 * - Pre-change validation checklist & rollback runbook
 * - What-If hypothetical simulation with before/after comparison and undo capability
 */
export default function ChangePassportModal({
  passport,
  isOpen,
  onClose,
  scenarioId,
  onSimulationUpdated,
}) {
  const [activeTab, setActiveTab] = useState('financials'); // 'financials' | 'reviews' | 'checklist' | 'simulation'
  const [selectedActionId, setSelectedActionId] = useState(passport?.selected_action_id || 'snapshot_and_delete');
  const [isSimulating, setIsSimulating] = useState(false);
  const [localPassport, setLocalPassport] = useState(passport);
  const [copyFeedback, setCopyFeedback] = useState(null);
  const modalRef = useRef(null);

  // Trap focus and close on Escape
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    }
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !localPassport) return null;

  const isSimulated = localPassport.decision_status === 'Simulated' || Boolean(localPassport.simulation_result?.is_simulated);
  const fin = localPassport.financial_impact;
  const reviews = localPassport.departmental_reviews || {};
  const checklist = localPassport.validation_checklist || [];
  const actions = localPassport.proposed_actions || [];

  let pendingChecksCount = 0;
  Object.values(reviews).forEach((dept) => {
    (dept.checks || []).forEach((c) => {
      if (!c.user_attested && c.status === 'REQUIRES_VERIFICATION') {
        pendingChecksCount += 1;
      }
    });
  });

  const handleAttestCheck = async (deptKey, checkId, currentVal) => {
    const newVal = !currentVal;
    try {
      await toggleAttestation(scenarioId, checkId, newVal);
      setLocalPassport((prev) => {
        if (!prev) return prev;
        const newReviews = { ...prev.departmental_reviews };
        const dept = { ...newReviews[deptKey] };
        dept.checks = (dept.checks || []).map((c) => {
          if (c.id === checkId) {
            return {
              ...c,
              user_attested: newVal,
              status: newVal ? 'PASSED' : 'REQUIRES_VERIFICATION',
            };
          }
          return c;
        });

        const allPassed = dept.checks.every((c) => c.status === 'PASSED' || c.user_attested);
        dept.status = allPassed ? 'PASSED' : 'REQUIRES_VERIFICATION';
        newReviews[deptKey] = dept;

        return {
          ...prev,
          departmental_reviews: newReviews,
        };
      });
    } catch (err) {
      console.error('Failed to update attestation:', err);
    }
  };

  const handleRunSimulation = async () => {
    setIsSimulating(true);
    try {
      const simResult = await simulateChange(scenarioId, localPassport.recommendation_id, selectedActionId);
      setLocalPassport((prev) => ({
        ...prev,
        decision_status: 'Simulated',
        decision_status_explanation: 'What-If simulation active. Projected billing and resource state updated.',
        simulation_result: simResult,
      }));
      onSimulationUpdated?.();
    } catch (err) {
      console.error('Simulation failed:', err);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleUndoSimulation = async () => {
    setIsSimulating(true);
    try {
      await undoSimulation(scenarioId, localPassport.recommendation_id);
      setLocalPassport((prev) => ({
        ...prev,
        decision_status: pendingChecksCount === 0 ? 'Ready for simulation' : 'Needs review',
        decision_status_explanation: 'Simulation reverted to baseline state.',
        simulation_result: null,
      }));
      onSimulationUpdated?.();
    } catch (err) {
      console.error('Undo simulation failed:', err);
    } finally {
      setIsSimulating(false);
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard?.writeText(text);
    setCopyFeedback(id);
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  return (
    <>
      <div className="passport-backdrop" onClick={onClose} aria-hidden="true" />

      <div 
        ref={modalRef}
        className="passport-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="passport-modal-title"
      >
        <div className="passport-header">
          <div className="passport-header-left">
            <div className="passport-icon-badge">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>
            <div>
              <div className="passport-meta-tags">
                <span className="passport-id-badge font-mono">{localPassport.passport_id}</span>
                <span className="passport-service-badge">{localPassport.resource_type}</span>
                <span className="passport-region-badge">{localPassport.region}</span>
                <span className={`passport-status-pill status-${localPassport.decision_status?.toLowerCase().replace(/\s+/g, '-')}`}>
                  <span className="status-indicator-dot" />
                  {localPassport.decision_status}
                </span>
              </div>
              <h2 id="passport-modal-title" className="passport-title">
                {localPassport.title}
              </h2>
            </div>
          </div>

          <button
            type="button"
            className="passport-close-btn"
            onClick={onClose}
            aria-label="Close Change Passport"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="passport-nav-tabs">
          <button
            type="button"
            className={`passport-tab-btn ${activeTab === 'financials' ? 'active' : ''}`}
            onClick={() => setActiveTab('financials')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="12" y1="1" x2="12" y2="23" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
            Financial Impact & Evidence
          </button>

          <button
            type="button"
            className={`passport-tab-btn ${activeTab === 'reviews' ? 'active' : ''}`}
            onClick={() => setActiveTab('reviews')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            Cross-Functional Reviews
            {pendingChecksCount > 0 && (
              <span className="tab-pending-badge">{pendingChecksCount} pending</span>
            )}
          </button>

          <button
            type="button"
            className={`passport-tab-btn ${activeTab === 'checklist' ? 'active' : ''}`}
            onClick={() => setActiveTab('checklist')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="9 11 12 14 22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
            Validation & Rollback
          </button>

          <button
            type="button"
            className={`passport-tab-btn ${activeTab === 'simulation' ? 'active' : ''}`}
            onClick={() => setActiveTab('simulation')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            What-If Simulation
            {isSimulated && <span className="tab-simulated-indicator" />}
          </button>
        </div>

        <div className="passport-body">
          {activeTab === 'financials' && (
            <div className="passport-tab-content">
              <div className="passport-card summary-card">
                <h3 className="passport-card-title">Executive Summary & Rationale</h3>
                <p className="passport-narrative">{localPassport.rationale}</p>
              </div>

              <div className="passport-financial-grid">
                <div className="fin-metric-card primary-waste">
                  <span className="fin-label">Avoidable Monthly Cost</span>
                  <span className="fin-value font-mono">${fin.estimated_avoidable_monthly_cost.toFixed(2)}/mo</span>
                  <span className="fin-subtext">${fin.annualized_avoidable_cost.toFixed(2)}/yr annualized</span>
                </div>

                <div className="fin-metric-card snapshot-cost">
                  <span className="fin-label">Safety Snapshot Overhead</span>
                  <span className="fin-value font-mono">-${fin.snapshot_cost_monthly.toFixed(2)}/mo</span>
                  <span className="fin-subtext">250 GB standard snapshot rate</span>
                </div>

                <div className="fin-metric-card net-savings">
                  <span className="fin-label">Net Projected Savings</span>
                  <span className="fin-value font-mono">${fin.net_projected_savings_monthly.toFixed(2)}/mo</span>
                  <span className="fin-subtext">${fin.net_projected_savings_annual.toFixed(2)}/yr net recurring</span>
                </div>

                <div className="fin-metric-card telemetry-status">
                  <span className="fin-label">Realized Savings Status</span>
                  <span className="fin-telemetry-badge">
                    <span className="telemetry-dot" />
                    Pending Billing Invoice
                  </span>
                  <span className="fin-subtext">{fin.realized_savings_status}</span>
                </div>
              </div>

              <div className="passport-card">
                <h3 className="passport-card-title">Pricing Formula & Calculation Trace</h3>
                <div className="calculation-breakdown-list">
                  {fin.calculation_breakdown.map((item, idx) => (
                    <div key={idx} className="calc-item">
                      <span className="calc-bullet">{idx + 1}</span>
                      <span className="calc-text font-mono">{item}</span>
                    </div>
                  ))}
                </div>

                <div className="pricing-assumptions-box">
                  <h4 className="assumptions-title">Documented Assumptions & Exclusions</h4>
                  <ul className="assumptions-list">
                    {fin.pricing_assumptions.map((p, idx) => (
                      <li key={idx}>{p}</li>
                    ))}
                    {fin.exclusions_and_limitations.map((ex, idx) => (
                      <li key={`ex-${idx}`} className="exclusion-item">Exclusion: {ex}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="passport-card">
                <h3 className="passport-card-title">Resource Telemetry & Metadata</h3>
                <table className="passport-table">
                  <tbody>
                    {(localPassport.evidence || []).map((row, idx) => (
                      <tr key={idx}>
                        <td className="table-label">{row.label}</td>
                        <td className="table-value font-mono">{row.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'reviews' && (
            <div className="passport-tab-content">
              <div className="reviews-intro-banner">
                <div className="intro-icon" aria-hidden="true">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                </div>
                <div>
                  <h4 className="intro-title">Cross-Functional Governance Sign-Off</h4>
                  <p className="intro-desc">
                    Cloud cost changes carry technical and business dependencies. Departmental reviews verify compliance,
                    operational continuity, and data safety before change execution.
                  </p>
                </div>
              </div>

              <div className="department-reviews-container">
                {Object.entries(reviews).map(([deptKey, dept]) => (
                  <div key={deptKey} className="passport-card dept-card">
                    <div className="dept-header">
                      <div className="dept-title-row">
                        <h3 className="dept-name">{dept.department}</h3>
                        <span className={`dept-status-tag status-${dept.status.toLowerCase()}`}>
                          {dept.status === 'PASSED' ? '✓ Verified' : '⚠ Action Required'}
                        </span>
                      </div>
                      <p className="dept-summary">{dept.summary}</p>
                    </div>

                    <div className="dept-checks-list">
                      {(dept.checks || []).map((check) => (
                        <div 
                          key={check.id} 
                          className={`check-item ${check.user_attested || check.status === 'PASSED' ? 'check-passed' : 'check-pending'}`}
                        >
                          <label className="check-checkbox-label">
                            <input
                              type="checkbox"
                              className="check-checkbox"
                              checked={check.user_attested || check.status === 'PASSED'}
                              onChange={() => handleAttestCheck(deptKey, check.id, check.user_attested)}
                            />
                            <div className="check-text-content">
                              <span className="check-title">{check.title}</span>
                              <p className="check-desc">{check.description}</p>
                              <div className="check-evidence-box">
                                <span className="evidence-badge">Requirement / Evidence:</span>
                                <span className="evidence-text">{check.evidence_or_requirement}</span>
                              </div>
                            </div>
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'checklist' && (
            <div className="passport-tab-content">
              <div className="passport-card">
                <h3 className="passport-card-title">Pre-Execution Validation Checklist</h3>
                <p className="checklist-subtext">
                  Follow these verified operational steps before terminating or modifying the resource.
                </p>

                <div className="steps-container">
                  {checklist.map((item) => (
                    <div key={item.id} className="step-card">
                      <div className="step-badge">{item.step_number}</div>
                      <div className="step-content">
                        <div className="step-title-row">
                          <h4 className="step-title">{item.title}</h4>
                          {item.is_mandatory && <span className="mandatory-pill">Mandatory</span>}
                        </div>
                        <p className="step-guidance">{item.guidance}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="passport-card rollback-card">
                <div className="rollback-header">
                  <div className="rollback-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="1 4 1 10 7 10" />
                      <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="passport-card-title">Rollback & Disaster Recovery Runbook</h3>
                    <p className="rollback-subtitle">Guaranteed recovery procedure in case of unintended application impact</p>
                  </div>
                </div>

                <div className="rollback-body">
                  <p className="rollback-text">{localPassport.rollback_recovery_plan}</p>
                  
                  <div className="cli-snippet-wrapper">
                    <pre className="cli-code font-mono">
                      {`# Immediate volume recovery from pre-deletion snapshot\naws ec2 create-volume \\\n  --snapshot-id snap-sim-0a7f82c9 \\\n  --volume-type gp3 \\\n  --availability-zone us-east-1a \\\n  --tag-specifications 'ResourceType=volume,Tags=[{Key=RestoredFrom,Value=snap-sim-0a7f82c9}]'`}
                    </pre>
                    <button
                      type="button"
                      className="btn-copy-code"
                      onClick={() => copyToClipboard('aws ec2 create-volume --snapshot-id snap-sim-0a7f82c9 --volume-type gp3 --availability-zone us-east-1a', 'rollback')}
                    >
                      {copyFeedback === 'rollback' ? 'Copied!' : 'Copy AWS CLI'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'simulation' && (
            <div className="passport-tab-content">
              <div className="passport-card">
                <h3 className="passport-card-title">Select Proposed Decommission Action</h3>
                <p className="action-selection-subtext">
                  Choose a change policy to simulate. Simulations calculate exact projected cost changes without modifying AWS infrastructure.
                </p>

                <div className="actions-grid">
                  {actions.map((act) => (
                    <div
                      key={act.id}
                      role="button"
                      tabIndex={0}
                      className={`action-card ${selectedActionId === act.id ? 'action-card-selected' : ''}`}
                      onClick={() => !isSimulated && setSelectedActionId(act.id)}
                      onKeyDown={(e) => {
                        if ((e.key === 'Enter' || e.key === ' ') && !isSimulated) {
                          setSelectedActionId(act.id);
                        }
                      }}
                    >
                      <div className="action-card-header">
                        <div className="action-radio-circle">
                          {selectedActionId === act.id && <div className="action-radio-dot" />}
                        </div>
                        <div>
                          <h4 className="action-title">{act.title}</h4>
                          {act.is_recommended && <span className="recommended-pill">Recommended</span>}
                        </div>
                      </div>

                      <p className="action-desc">{act.description}</p>

                      <div className="action-metrics-row">
                        <div className="act-metric">
                          <span className="act-lbl">Net Monthly Savings</span>
                          <span className="act-val font-mono">${act.net_monthly_savings.toFixed(2)}/mo</span>
                        </div>
                        <div className="act-metric">
                          <span className="act-lbl">Risk Level</span>
                          <span className={`act-risk risk-${act.risk_level.toLowerCase()}`}>{act.risk_level}</span>
                        </div>
                        <div className="act-metric">
                          <span className="act-lbl">Reversibility</span>
                          <span className="act-rev">{act.reversibility}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {isSimulated && localPassport.simulation_result ? (
                <div className="passport-card simulation-active-card">
                  <div className="simulation-header-banner">
                    <span className="sim-pulse-dot" />
                    <div>
                      <h4 className="sim-banner-title">What-If Simulation Active (Illustrative)</h4>
                      <p className="sim-banner-subtitle">
                        Simulated at {localPassport.simulation_result.simulation_timestamp}.
                        Scenario monthly billing has been updated dynamically across the dashboard.
                      </p>
                    </div>
                  </div>

                  <div className="sim-comparison-grid">
                    <div className="sim-comp-box">
                      <span className="comp-label">Baseline Scenario Spend</span>
                      <span className="comp-val font-mono">${localPassport.simulation_result.original_monthly_cost.toFixed(2)}/mo</span>
                    </div>

                    <div className="sim-delta-indicator">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                      <span className="delta-pill font-mono">-${localPassport.simulation_result.monthly_savings_delta.toFixed(2)}/mo</span>
                    </div>

                    <div className="sim-comp-box projected-spend">
                      <span className="comp-label">Projected Scenario Spend</span>
                      <span className="comp-val font-mono">${localPassport.simulation_result.projected_monthly_cost.toFixed(2)}/mo</span>
                      <span className="comp-subtext">-${localPassport.simulation_result.annual_savings_delta.toFixed(2)}/yr annualized</span>
                    </div>
                  </div>

                  <div className="sim-state-info">
                    <span className="state-label">Simulated Resource State:</span>
                    <span className="state-val font-mono">{localPassport.simulation_result.simulated_resource_state}</span>
                  </div>

                  <div className="sim-disclaimer-box">
                    <p>{localPassport.simulation_result.disclaimer}</p>
                  </div>

                  <div className="sim-actions-footer">
                    <button
                      type="button"
                      className="btn-undo-simulation"
                      onClick={handleUndoSimulation}
                      disabled={isSimulating}
                    >
                      {isSimulating ? 'Reverting...' : 'Undo Simulation (Revert to Baseline)'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="passport-card simulation-trigger-card">
                  <div className="trigger-content">
                    <div className="trigger-icon">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                    </div>
                    <div>
                      <h4 className="trigger-title">Execute Hypothetical Cost & State Simulation</h4>
                      <p className="trigger-desc">
                        Simulating this change models the decommission in-memory. It computes projected infrastructure spend,
                        updates the scenario KPI cards, and records a simulated safety snapshot without altering AWS resources.
                      </p>
                    </div>
                  </div>

                  <div className="trigger-btn-wrapper">
                    <button
                      type="button"
                      className="btn-run-simulation"
                      onClick={handleRunSimulation}
                      disabled={isSimulating}
                    >
                      {isSimulating ? 'Executing Simulation...' : 'Run What-If Simulation'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="passport-footer">
          <div className="passport-read-only-notice">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>Strict read-only safety: Change Passports and Simulations model impact without modifying live cloud infrastructure.</span>
          </div>

          <button
            type="button"
            className="btn-passport-dismiss"
            onClick={onClose}
          >
            Close Passport
          </button>
        </div>
      </div>
    </>
  );
}
