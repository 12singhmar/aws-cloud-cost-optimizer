import React, { useEffect, useRef } from 'react';

/**
 * RecommendationDrawer Component
 * A right-side slide-out panel that displays full explainable evidence,
 * metrics, risk assessment, and safe human verification guidance for a selected finding.
 */
export default function RecommendationDrawer({ finding, isOpen, onClose }) {
  const drawerRef = useRef(null);
  const closeButtonRef = useRef(null);

  // Close on Escape key and trap focus when open
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    }

    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
      // Focus close button on open
      setTimeout(() => {
        if (closeButtonRef.current) {
          closeButtonRef.current.focus();
        }
      }, 50);
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!finding) return null;

  const isHighPriority = finding.priority === 'HIGH';

  return (
    <>
      {/* Backdrop */}
      <div 
        className={`drawer-backdrop ${isOpen ? 'active' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Drawer */}
      <aside
        ref={drawerRef}
        className={`recommendation-drawer ${isOpen ? 'open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-heading"
      >
        {/* Drawer Header */}
        <div className="drawer-header">
          <div className="drawer-title-group">
            <div className="drawer-badge-row">
              <span className={`priority-badge ${isHighPriority ? 'badge-high' : 'badge-medium'}`}>
                {finding.priority} PRIORITY
              </span>
              <span className="finding-service-tag">{finding.service}</span>
            </div>
            <h2 id="drawer-heading" className="drawer-title">{finding.title}</h2>
          </div>

          <button
            ref={closeButtonRef}
            type="button"
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close recommendation details"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Drawer Body */}
        <div className="drawer-body">
          {/* Key Metrics Highlight Banner */}
          <div className="drawer-metrics-grid">
            <div className="drawer-metric-card savings-metric">
              <span className="drawer-metric-label">Estimated Monthly Savings</span>
              <span className="drawer-metric-value font-mono">{finding.estimatedSavingsFormatted}</span>
            </div>

            <div className="drawer-metric-card">
              <span className="drawer-metric-label">Confidence Score</span>
              <div className="confidence-display">
                <span className="drawer-metric-value font-mono">{finding.confidence}%</span>
                <div className="confidence-bar-track">
                  <div className="confidence-bar-fill" style={{ width: `${finding.confidence}%` }} />
                </div>
              </div>
            </div>

            <div className="drawer-metric-card">
              <span className="drawer-metric-label">Implementation Risk</span>
              <span className={`risk-tag risk-${finding.risk.toLowerCase()}`}>
                {finding.risk} Risk
              </span>
            </div>
          </div>

          {/* Section: Why this was flagged */}
          <section className="drawer-section">
            <h3 className="drawer-section-title">
              <span className="section-title-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </span>
              Why this was flagged
            </h3>
            <div className="drawer-reasoning-box">
              <p>{finding.reasoning}</p>
            </div>
          </section>

          {/* Section: Evidence Table */}
          <section className="drawer-section">
            <h3 className="drawer-section-title">
              <span className="section-title-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </span>
              Evidence & Telemetry
            </h3>
            <div className="evidence-table-wrapper">
              <table className="evidence-table">
                <tbody>
                  {finding.evidence.map((row, idx) => (
                    <tr key={idx}>
                      <td className="evidence-label">{row.label}</td>
                      <td className="evidence-value font-mono">{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Section: Human Verification Guidance */}
          <section className="drawer-section verification-section">
            <h3 className="drawer-section-title verification-title">
              <span className="section-title-icon guidance-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </span>
              Human verification guidance
            </h3>
            <div className="verification-box">
              <p className="verification-text">
                {finding.verificationGuidance}
              </p>
            </div>
          </section>
        </div>

        {/* Drawer Footer (Read-Only Actions) */}
        <div className="drawer-footer">
          <div className="drawer-footer-actions">
            <a
              href={finding.awsConsoleUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-aws-console"
            >
              <span>Review in AWS Console</span>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>

            <button
              type="button"
              className="btn-drawer-dismiss"
              onClick={onClose}
            >
              Close
            </button>
          </div>

          <div className="drawer-read-only-disclaimer">
            <span>🛡️ Read-only mode: This action will open AWS Console in a new tab for manual verification.</span>
          </div>
        </div>
      </aside>
    </>
  );
}
