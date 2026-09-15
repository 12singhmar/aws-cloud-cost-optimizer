import React from 'react';

/**
 * FutureSectionNotice Component
 * Provides clear feedback when clicking sections designated for future milestones.
 */
export default function FutureSectionNotice({ sectionName, onClose }) {
  if (!sectionName) return null;

  return (
    <div className="future-notice-toast" role="status" aria-live="polite">
      <div className="future-notice-content">
        <span className="future-notice-icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </span>
        <div className="future-notice-text">
          <strong>{sectionName}</strong> is scheduled for an upcoming milestone. The <strong>Cloud cost overview</strong> dashboard contains the active command center.
        </div>
      </div>
      <button 
        type="button" 
        className="future-notice-close" 
        onClick={onClose}
        aria-label="Dismiss notice"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
