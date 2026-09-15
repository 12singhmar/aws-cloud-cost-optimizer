import React from 'react';

/**
 * ServiceSpend Component
 * Displays horizontal bar breakdown of spend across primary AWS services (EC2, RDS, S3, EBS).
 */
export default function ServiceSpend({ serviceSpend = [] }) {
  if (!serviceSpend || serviceSpend.length === 0) {
    return null;
  }

  const totalSpend = serviceSpend.reduce((acc, curr) => acc + curr.spend, 0);

  return (
    <div className="card dashboard-card service-spend-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Spend by service</h3>
          <span className="card-subtitle">Distribution across active AWS resources</span>
        </div>
        <div className="service-total-pill font-mono">
          Total: ${totalSpend.toLocaleString()}
        </div>
      </div>

      <div className="service-list">
        {serviceSpend.map((service) => (
          <div key={service.id} className="service-row">
            <div className="service-info-row">
              <div className="service-name-group">
                <span className="service-badge" style={{ backgroundColor: `${service.color}18`, color: service.color }}>
                  {service.name}
                </span>
                <span className="service-category">{service.category}</span>
              </div>
              <div className="service-metric-group">
                <span className="service-amount font-mono">{service.formattedSpend}</span>
                <span className="service-pct font-mono">{service.percentage}%</span>
              </div>
            </div>

            {/* Horizontal Proportion Bar */}
            <div className="service-progress-track">
              <div 
                className="service-progress-fill" 
                style={{ 
                  width: `${service.percentage}%`,
                  backgroundColor: service.color 
                }}
                role="progressbar"
                aria-valuenow={service.percentage}
                aria-valuemin="0"
                aria-valuemax="100"
                aria-label={`${service.name} represents ${service.percentage}% of cloud spend`}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="card-footer-note">
        <span>EC2 compute accounts for roughly half of total monthly expenditure.</span>
      </div>
    </div>
  );
}
