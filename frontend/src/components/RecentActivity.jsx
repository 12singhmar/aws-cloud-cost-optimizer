import React from 'react';

/**
 * RecentActivity Component
 * Displays recent cloud analysis, metric scans, and evaluation events.
 */
export default function RecentActivity({ 
  activities = [],
  lastAnalysis = "4 minutes ago",
  statusText = "Analysis data available"
}) {
  return (
    <div className="card dashboard-card activity-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Recent activity</h3>
          <span className="card-subtitle">Automated telemetry and rule evaluations</span>
        </div>
        <div className="activity-live-badge">
          <span className="activity-live-dot" />
          <span>Live feed</span>
        </div>
      </div>

      <div className="activity-timeline">
        {activities.map((item, idx) => (
          <div key={item.id || idx} className="activity-item">
            <div className="activity-indicator">
              <span className={`activity-dot ${item.type === 'complete' ? 'activity-dot-success' : 'activity-dot-service'}`} />
              {idx < activities.length - 1 && <span className="activity-line" />}
            </div>

            <div className="activity-content">
              <div className="activity-header-row">
                <span className="activity-title">{item.title}</span>
                <span className="activity-time font-mono">{item.timeAgo}</span>
              </div>
              <p className="activity-detail">{item.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="activity-footer-bar">
        <div className="analysis-status-group">
          <span className="status-dot green" />
          <span className="status-text font-mono">{statusText}</span>
        </div>
        <span className="last-run-text">Last analysis: {lastAnalysis}</span>
      </div>
    </div>
  );
}
