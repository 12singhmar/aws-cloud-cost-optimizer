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

      {findings.length > 0 ? (
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
      ) : (
        <div className="findings-empty-state">
          <div className="empty-state-icon-wrapper" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h4 className="empty-state-title">No priority findings detected</h4>
          <p className="empty-state-desc">
            All monitored resources currently meet utilisation, attachment, and storage efficiency thresholds.
          </p>
        </div>
      )}

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
