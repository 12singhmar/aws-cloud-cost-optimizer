import React from 'react';
import FindingCard from './FindingCard';

/**
 * PriorityFindings Component
 * Core container for top cost-optimisation opportunities.
 */
export default function PriorityFindings({ 
  findings = [], 
  onSelectFinding, 
  selectedFindingId 
}) {
  return (
    <section className="card dashboard-card priority-findings-card" aria-label="Priority Findings Section">
      <div className="card-header findings-header">
        <div>
          <div className="findings-title-row">
            <h3 className="card-title">Priority findings</h3>
            <span className="findings-count-badge font-mono">{findings.length} total</span>
          </div>
          <p className="card-subtitle">Opportunities worth investigating first</p>
        </div>
        <div className="findings-legend">
          <span className="legend-item"><span className="legend-dot high" /> High</span>
          <span className="legend-item"><span className="legend-dot medium" /> Medium</span>
        </div>
      </div>

      <div className="findings-grid">
        {findings.map((finding) => (
          <FindingCard
            key={finding.id}
            finding={finding}
            onSelect={onSelectFinding}
            isSelected={selectedFindingId === finding.id}
          />
        ))}
      </div>

      <div className="findings-footer-info">
        <div className="info-icon" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </div>
        <span>
          Recommendations provide explainable rationale and verification steps without modifying AWS infrastructure. Click any card to inspect evidence.
        </span>
      </div>
    </section>
  );
}
