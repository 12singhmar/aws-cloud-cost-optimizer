import React from 'react';

/**
 * Sidebar Navigation Component
 * Provides product branding and desktop navigation items.
 */
export default function Sidebar({ activeNav, onSelectNav, isOpen, onClose }) {
  const primaryNavItems = [
    { id: 'overview', label: 'Overview', icon: 'grid', isAvailable: true },
    { id: 'recommendations', label: 'Recommendations', icon: 'zap', isAvailable: false, badge: '18' },
    { id: 'resources', label: 'Resources', icon: 'layers', isAvailable: false },
    { id: 'activity', label: 'Activity', icon: 'clock', isAvailable: false },
  ];

  const secondaryNavItems = [
    { id: 'settings', label: 'Settings', icon: 'settings', isAvailable: false },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div 
          className="sidebar-backdrop" 
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'open' : ''}`} aria-label="Main Navigation">
        {/* Logo & Product Identity */}
        <div className="sidebar-brand">
          <div className="brand-logo-mark" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-title">AWS Cost Optimiser</span>
            <span className="brand-subtitle">Cloud FinOps Platform</span>
          </div>
        </div>

        {/* Navigation Sections */}
        <nav className="sidebar-nav">
          <div className="nav-group">
            <span className="nav-group-label">Platform</span>
            <ul className="nav-list">
              {primaryNavItems.map((item) => {
                const isActive = activeNav === item.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`nav-item-btn ${isActive ? 'active' : ''}`}
                      onClick={() => {
                        onSelectNav(item.id, item.isAvailable);
                        if (onClose) onClose();
                      }}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      <span className="nav-icon" aria-hidden="true">
                        {item.icon === 'grid' && (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="3" width="7" height="7" />
                            <rect x="14" y="3" width="7" height="7" />
                            <rect x="14" y="14" width="7" height="7" />
                            <rect x="3" y="14" width="7" height="7" />
                          </svg>
                        )}
                        {item.icon === 'zap' && (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                          </svg>
                        )}
                        {item.icon === 'layers' && (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polygon points="12 2 2 7 12 12 22 7 12 2" />
                            <polyline points="2 17 12 22 22 17" />
                            <polyline points="2 12 12 17 22 12" />
                          </svg>
                        )}
                        {item.icon === 'clock' && (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10" />
                            <polyline points="12 6 12 12 16 14" />
                          </svg>
                        )}
                      </span>
                      <span className="nav-label">{item.label}</span>
                      {item.badge && (
                        <span className="nav-badge">{item.badge}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="nav-divider" />

          <div className="nav-group">
            <span className="nav-group-label">Configuration</span>
            <ul className="nav-list">
              {secondaryNavItems.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`nav-item-btn ${activeNav === item.id ? 'active' : ''}`}
                    onClick={() => {
                      onSelectNav(item.id, item.isAvailable);
                      if (onClose) onClose();
                    }}
                  >
                    <span className="nav-icon" aria-hidden="true">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="3" />
                        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                      </svg>
                    </span>
                    <span className="nav-label">{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </nav>

        {/* Sidebar Footer info */}
        <div className="sidebar-footer">
          <div className="account-pill">
            <span className="account-dot" />
            <div className="account-details">
              <span className="account-name">Production (AWS)</span>
              <span className="account-id font-mono">1248-9920-4103</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
