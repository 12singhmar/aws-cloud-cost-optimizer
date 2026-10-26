import React, { useState } from 'react';

/**
 * CostTrend Component
 * Renders a clean, responsive SVG line/area chart for historical monthly spend.
 * Dynamically scales to arbitrary scenario expenditure levels.
 */
export default function CostTrend({ costTrend = [] }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (!costTrend || costTrend.length === 0) {
    return null;
  }

  // Chart dimensions and bounds
  const svgWidth = 600;
  const svgHeight = 220;
  const padding = { top: 24, right: 30, bottom: 36, left: 56 };

  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  // Dynamic scale calculations based on current scenario data
  const costs = costTrend.map((item) => item.cost);
  const rawMin = Math.min(...costs);
  const rawMax = Math.max(...costs);

  // Buffer range with rounding to clean steps
  const costSpread = rawMax - rawMin;
  const buffer = costSpread > 0 ? costSpread * 0.15 : Math.max(100, rawMax * 0.15);

  const minCost = Math.max(0, Math.floor((rawMin - buffer) / 50) * 50);
  const maxCost = Math.ceil((rawMax + buffer) / 50) * 50;
  const costRange = maxCost - minCost > 0 ? maxCost - minCost : 100;

  const points = costTrend.map((item, index) => {
    const divisor = costTrend.length > 1 ? costTrend.length - 1 : 1;
    const x = padding.left + (index / divisor) * chartWidth;
    const y = padding.top + chartHeight - ((item.cost - minCost) / costRange) * chartHeight;
    return { ...item, x, y };
  });

  // Construct SVG Path
  const linePath = points.reduce((acc, point, index) => {
    return index === 0 ? `M ${point.x} ${point.y}` : `${acc} L ${point.x} ${point.y}`;
  }, "");

  const areaPath = `${linePath} L ${points[points.length - 1].x} ${padding.top + chartHeight} L ${points[0].x} ${padding.top + chartHeight} Z`;

  // Compute 4 evenly spaced Y-Axis tick values
  const yTicks = [
    minCost,
    Math.round(minCost + costRange * 0.33),
    Math.round(minCost + costRange * 0.66),
    maxCost,
  ];

  // Dynamic trend calculation between first and last data point
  const firstPoint = costTrend[0];
  const lastPoint = costTrend[costTrend.length - 1];
  const totalChange = lastPoint.cost - firstPoint.cost;
  const totalChangePct = firstPoint.cost > 0 ? (totalChange / firstPoint.cost) * 100 : 0;
  const isIncrease = totalChange > 0;
  const isDecrease = totalChange < 0;

  const trendText = isIncrease
    ? `Total increase: +$${Math.round(totalChange).toLocaleString()} (+${totalChangePct.toFixed(1)}%)`
    : isDecrease
    ? `Total decrease: -$${Math.round(Math.abs(totalChange)).toLocaleString()} (${totalChangePct.toFixed(1)}%)`
    : `Spend steady ($${Math.round(lastPoint.cost).toLocaleString()})`;

  return (
    <div className="card dashboard-card cost-trend-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">Cost trend</h3>
          <span className="card-subtitle">Last {costTrend.length} months</span>
        </div>
        <div className="trend-summary-pill">
          <span className={`trend-dot ${isDecrease ? 'green' : ''}`} />
          <span>{trendText}</span>
        </div>
      </div>

      <div className="chart-container">
        <svg 
          viewBox={`0 0 ${svgWidth} ${svgHeight}`} 
          className="cost-chart-svg"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="costAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.16" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0.01" />
            </linearGradient>
          </defs>

          {/* Horizontal Gridlines & Y-Axis Labels */}
          {yTicks.map((tickValue) => {
            const y = padding.top + chartHeight - ((tickValue - minCost) / costRange) * chartHeight;
            return (
              <g key={tickValue} className="grid-group">
                <line
                  x1={padding.left}
                  y1={y}
                  x2={svgWidth - padding.right}
                  y2={y}
                  stroke="#e2e8f0"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                />
                <text
                  x={padding.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  className="axis-text font-mono"
                  fill="#94a3b8"
                  fontSize="11"
                >
                  ${tickValue.toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#costAreaGradient)" />

          {/* Line Stroke */}
          <path
            d={linePath}
            fill="none"
            stroke="#2563eb"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data Points & X-Axis Labels */}
          {points.map((point, index) => {
            const isHovered = hoveredIndex === index;
            const isLatest = index === points.length - 1;

            return (
              <g key={point.month} className="data-point-group">
                {/* Vertical hover guide line */}
                {isHovered && (
                  <line
                    x1={point.x}
                    y1={padding.top}
                    x2={point.x}
                    y2={padding.top + chartHeight}
                    stroke="#94a3b8"
                    strokeDasharray="2 2"
                    strokeWidth="1"
                  />
                )}

                {/* X-Axis Label */}
                <text
                  x={point.x}
                  y={svgHeight - 12}
                  textAnchor="middle"
                  className={`axis-text ${isLatest ? 'axis-text-current' : ''}`}
                  fill={isLatest ? "#0f172a" : "#64748b"}
                  fontSize="11"
                  fontWeight={isLatest ? "600" : "400"}
                >
                  {point.month}
                </text>

                {/* Visible Data Point Node */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={isHovered ? 6 : (isLatest ? 5 : 4)}
                  fill="#ffffff"
                  stroke="#2563eb"
                  strokeWidth={isHovered ? 3 : 2}
                  className="chart-dot"
                />

                {/* Invisible larger hit area for hover */}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={18}
                  fill="transparent"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />
              </g>
            );
          })}
        </svg>

        {/* Dynamic Tooltip */}
        {hoveredIndex !== null && points[hoveredIndex] && (
          <div 
            className="chart-tooltip"
            style={{
              left: `${(points[hoveredIndex].x / svgWidth) * 100}%`,
              top: `${(points[hoveredIndex].y / svgHeight) * 100}%`,
            }}
          >
            <div className="tooltip-month">{points[hoveredIndex].month} 2026</div>
            <div className="tooltip-cost font-mono">{points[hoveredIndex].label}</div>
          </div>
        )}
      </div>

      <div className="card-footer-note">
        <span>Deterministic scenario trend: historical monthly expenditure across compute and storage.</span>
      </div>
    </div>
  );
}
