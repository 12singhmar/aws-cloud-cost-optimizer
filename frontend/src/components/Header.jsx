import React from 'react';

/**
 * Top Header Component
 * Displays page title, date context, system status, read-only indicator, and backend connection.
 */
export default function Header({ 
  month = "September 2026", 
  statusText = "Analysis data available",
  backendStatus = "checking",
  onToggleMobileMenu 
}) {
  const isBackendOk = backendStatus === 'ok';

  return (
    <header className="app-header">
      <div className="header-left">
        <button 
          type="button" 
          className="mobile-menu-toggle" 
          onClick={onToggleMobileMenu}
          aria-label="Toggle navigation menu"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        <div className="header-title-wrapper">
          <h1 className="header-title">Cloud cost overview</h1>
          <span className="header-badge-period">{month}</span>
        </div>
      </div>

      <div className="header-right">
        {/* Backend Connection Indicator */}
        <div 
          className={`status-pill ${isBackendOk ? 'backend-online' : 'backend-offline'}`}
          title={isBackendOk ? "Connected to FastAPI backend" : "Backend unreachable (mock data active)"}
        >
          <span className="status-dot" aria-hidden="true" />
          <span className="status-label">
            {isBackendOk ? 'Backend connected' : 'Backend unavailable'}
          </span>
        </div>

        {/* System Analysis Status */}
        <div className="status-pill analysis-available">
          <span className="status-dot green" aria-hidden="true" />
          <span className="status-label">{statusText}</span>
        </div>

        {/* Read-Only Badge */}
        <div className="readonly-badge" title="This system only monitors and does not modify AWS infrastructure">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>Read-only</span>
        </div>
      </div>
    </header>
  );
}
