import React from 'react';

/**
 * FindingCard Component
 * Displays a single prioritised recommendation with metadata, savings, confidence, and risk.
 */
export default function FindingCard({ finding, onSelect, isSelected }) {
  const isHighPriority = finding.priority === 'HIGH';

  return (
    <div
      role="button"
      tabIndex={0}
      className={`finding-card ${isSelected ? 'finding-card-active' : ''} ${isHighPriority ? 'finding-high-priority' : ''}`}
      onClick={() => onSelect(finding)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(finding);
        }
      }}
      aria-label={`View details for ${finding.title}, estimated savings ${finding.estimatedSavingsFormatted}`}
    >
      <div className="finding-card-top">
        <div className="finding-priority-row">
          <span className={`priority-badge ${isHighPriority ? 'badge-high' : 'badge-medium'}`}>
            {finding.priority} PRIORITY
          </span>
          <span className="finding-service-tag">{finding.service}</span>
        </div>
        <div className="finding-savings-highlight">
          <span className="savings-label">Est. savings</span>
          <span className="savings-number font-mono">{finding.estimatedSavingsFormatted}</span>
        </div>
      </div>

      <div className="finding-body">
        <h4 className="finding-title">{finding.title}</h4>
        <p className="finding-desc">{finding.description}</p>
      </div>

      <div className="finding-meta-row">
        <div className="finding-meta-item">
          <span className="meta-label">Confidence</span>
          <span className="meta-value font-mono">{finding.confidence}%</span>
        </div>

        <div className="finding-meta-divider" />

        <div className="finding-meta-item">
          <span className="meta-label">Risk</span>
          <span className={`risk-value risk-${finding.risk.toLowerCase()}`}>
            {finding.risk}
          </span>
        </div>

        <div className="finding-meta-cta">
          <span>Investigate</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </div>
      </div>
    </div>
  );
}
