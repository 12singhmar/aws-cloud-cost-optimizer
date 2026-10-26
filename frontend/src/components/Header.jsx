import React from 'react';

/**
 * Top Header Component
 * Displays page title, date context, scenario selector, simulation badge,
 * system status, dark/light theme toggle, and backend connectivity.
 */
export default function Header({ 
  month = "September 2026", 
  statusText = "Analysis data available",
  backendStatus = "checking",
  scenarios = [],
  selectedScenario = "high-cost-waste",
  onSelectScenario,
  isLoading = false,
  onToggleMobileMenu,
  theme = 'light',
  onToggleTheme,
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

        {/* Scenario Selector */}
        {scenarios.length > 0 && (
          <div className="header-scenario-wrapper">
            <label htmlFor="scenario-select" className="header-scenario-label">
              Scenario:
            </label>
            <div className="header-scenario-select-box">
              <select
                id="scenario-select"
                className="header-scenario-select"
                value={selectedScenario}
                onChange={(e) => onSelectScenario?.(e.target.value)}
                disabled={isLoading}
                aria-label="Select Cloud Scenario"
              >
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <svg 
                className="header-scenario-arrow" 
                width="14" 
                height="14" 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                aria-hidden="true"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>
            {isLoading && <span className="scenario-refresh-spinner" aria-label="Refreshing scenario..." />}
          </div>
        )}
      </div>

      <div className="header-right">
        {/* Simulation Environment Badge */}
        <div 
          className="simulation-badge" 
          title="Telemetry and resource inventory are simulated deterministically. No actual AWS account is connected."
        >
          <span className="simulation-dot" aria-hidden="true" />
          <span>Simulated Environment</span>
        </div>

        {/* Backend Connection Indicator */}
        <div 
          className={`status-pill ${isBackendOk ? 'backend-online' : 'backend-offline'}`}
          title={isBackendOk ? "Connected to FastAPI backend" : "Backend unreachable (mock fallback active)"}
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

        {/* Dark/Light Theme Toggle */}
        <button
          type="button"
          className="theme-toggle-btn"
          onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? (
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>

        {/* Read-Only Badge */}
        <div className="readonly-badge" title="This platform evaluates read-only telemetry and does not modify AWS infrastructure.">
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
