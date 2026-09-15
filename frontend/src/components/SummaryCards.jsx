import React from 'react';

/**
 * SummaryCards Component
 * Renders the 3 main KPI metric cards:
 * 1. Monthly Cost ($4,286.40, ↑ 8.4% vs last month)
 * 2. Potential Monthly Savings ($812.60, 19.0% of current spend) - Highest visual emphasis
 * 3. Findings to Review (18, 4 high priority)
 */
export default function SummaryCards({ summary }) {
  const { monthlyCost, potentialSavings, findingsCount } = summary;

  return (
    <section className="summary-section" aria-label="Executive Cost & Savings Summary">
      <div className="section-intro">
        <h2 className="section-title">Cloud cost overview</h2>
        <p className="section-subtitle">
          Understand your AWS spend and identify the opportunities worth investigating.
        </p>
      </div>

      <div className="kpi-grid">
        {/* Card 1: Monthly Cost */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">{monthlyCost.label}</span>
            <span className="kpi-icon-wrapper" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="1" x2="12" y2="23" />
                <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value">{monthlyCost.formatted}</span>
          </div>
          <div className="kpi-footer">
            <span className="kpi-badge badge-warning">
              {monthlyCost.supportingText}
            </span>
          </div>
        </div>

        {/* Card 2: Potential Monthly Savings (Primary Highlight) */}
        <div className="kpi-card kpi-card-highlight">
          <div className="kpi-header">
            <div className="kpi-label-with-tag">
              <span className="kpi-label">{potentialSavings.label}</span>
              <span className="kpi-highlight-tag">Key Opportunity</span>
            </div>
            <span className="kpi-icon-wrapper savings-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m7 15 5-5 5 5" />
                <path d="m7 9 5-5 5 5" />
              </svg>
            </span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value savings-value">{potentialSavings.formatted}</span>
          </div>
          <div className="kpi-footer">
            <span className="kpi-badge badge-savings">
              {potentialSavings.supportingText}
            </span>
          </div>
        </div>

        {/* Card 3: Findings to Review */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">{findingsCount.label}</span>
            <span className="kpi-icon-wrapper" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value">{findingsCount.value}</span>
          </div>
          <div className="kpi-footer">
            <span className="kpi-badge badge-danger">
              {findingsCount.supportingText}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
