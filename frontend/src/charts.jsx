// Small hand-written SVG charts (no chart library = nothing to explain away).
// Every chart has a hover tooltip; colours come from CSS tokens.
import { useRef, useState } from 'react'

function useTip() {
  const ref = useRef(null)
  const [tip, setTip] = useState(null)
  const show = (evt, content) => {
    const box = ref.current.getBoundingClientRect()
    setTip({ x: evt.clientX - box.left, y: evt.clientY - box.top, content })
  }
  return { ref, tip, show, hide: () => setTip(null) }
}

function Tip({ tip }) {
  return tip ? <div className="tooltip" style={{ left: tip.x, top: tip.y }}>{tip.content}</div> : null
}

/* Horizontal bars with direct value labels (one series). */
export function HBars({ rows, format }) {
  const max = Math.max(...rows.map((r) => r.value), 0) || 1
  return (
    <div className="hbar" role="list">
      {rows.map((r) => (
        <div className="hbar-row" role="listitem" key={r.label} title={`${r.label}: ${format(r.value)}`}>
          <span className="small">{r.label}</span>
          <div className="hbar-track"><div className="hbar-fill" style={{ width: `${(r.value / max) * 100}%` }} /></div>
          <span className="num small">{format(r.value)}</span>
        </div>
      ))}
    </div>
  )
}

/* Line chart for the backtest: week 1 (decide) + later hours (check), shaded. */
export function BacktestChart({ series }) {
  const { ref, tip, show, hide } = useTip()
  const all = [...series.train, ...series.test]
  const W = 640, H = 190, L = 34, R = 8, T = 10, B = 24
  // Projected demand can exceed 100% of the smaller server; extend the axis in steps of 50.
  const ymax = Math.ceil(Math.max(100, ...all) / 50) * 50
  const ticks = Array.from({ length: ymax / 25 + 1 }, (_, k) => k * 25).filter((v) => ymax <= 100 || v % 50 === 0)
  const x = (k) => L + (k / Math.max(1, all.length - 1)) * (W - L - R)
  const y = (v) => T + (1 - v / ymax) * (H - T - B)
  const path = all.map((v, k) => `${k ? 'L' : 'M'}${x(k).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const split = x(series.train.length - 0.5)
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * W
    const k = Math.max(0, Math.min(all.length - 1, Math.round(((px - L) / (W - L - R)) * (all.length - 1))))
    const phase = k < series.train.length ? 'Week 1 (decide)' : 'Later (check)'
    show(e, <span>{phase}: <b>{all[k]}%</b> CPU</span>)
  }
  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={series.label} onMouseMove={onMove} onMouseLeave={hide}>
        <rect x={split} y={T} width={W - R - split} height={H - T - B} fill="var(--shade)" />
        {ticks.map((v) => (
          <g key={v}>
            <line className="grid-line" x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
            <text x={L - 6} y={y(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {series.limit && (
          <g>
            <line x1={L} x2={W - R} y1={y(series.limit)} y2={y(series.limit)} stroke="var(--critical)" strokeDasharray="4 4" />
            <text x={W - R} y={y(series.limit) - 5} textAnchor="end" style={{ fill: 'var(--critical-text)' }}>{series.limit}% = struggling</text>
          </g>
        )}
        <path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" strokeLinejoin="round" />
        <text x={L + 4} y={H - 6}>week 1: decide</text>
        <text x={split + 6} y={H - 6}>after: check what happened</text>
      </svg>
      <Tip tip={tip} />
    </div>
  )
}

/* Stacked bars: safe vs harmful, per avg-CPU bucket. */
export function StackedBars({ rows }) {
  const { ref, tip, show, hide } = useTip()
  const W = 640, H = 260, L = 46, R = 8, T = 10, B = 40
  const max = Math.max(...rows.map((r) => r.flagged))
  const bw = (W - L - R) / rows.length
  const y = (v) => T + (1 - v / max) * (H - T - B)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round((max * f) / 1000) * 1000)
  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="VMs flagged by the naive rule, split by harm">
        {ticks.map((v) => (
          <g key={v}>
            <line className="grid-line" x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
            <text x={L - 6} y={y(v) + 4} textAnchor="end">{v >= 1000 ? `${v / 1000}k` : v}</text>
          </g>
        ))}
        {rows.map((r, k) => {
          const x0 = L + k * bw + 5, w = bw - 10
          const safe = r.flagged - r.harmful
          const yH = y(r.harmful), ySafeTop = y(r.flagged)
          const tip = (e) => show(e, <span>avg CPU {r.bucket}: <b>{r.harmful.toLocaleString()}</b> of {r.flagged.toLocaleString()} harmed ({Math.round((r.harmful / r.flagged) * 100)}%)</span>)
          return (
            <g key={r.bucket} onMouseMove={tip} onMouseLeave={hide}>
              <rect x={L + k * bw} y={T} width={bw} height={H - T - B} fill="transparent" />
              <rect x={x0} y={yH} width={w} height={Math.max(0, H - B - yH)} fill="var(--series-2)" />
              {safe > 0 && <rect x={x0} y={ySafeTop} width={w} height={Math.max(0, yH - ySafeTop - 2)} fill="var(--series-1)" rx="3" />}
              <text x={x0 + w / 2} y={H - 24} textAnchor="middle">{r.bucket.replace('%', '')}</text>
            </g>
          )
        })}
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle">average CPU over 30 days (%)</text>
      </svg>
      <div className="legend">
        <span><i style={{ background: 'var(--series-1)' }} />Safe to downsize</span>
        <span><i style={{ background: 'var(--series-2)' }} />Would be harmed (busy-time CPU &gt; 100% after halving)</span>
      </div>
      <Tip tip={tip} />
    </div>
  )
}

/* Scatter: avg CPU vs p95 of max CPU, with the two rule lines. */
export function FleetScatter({ points }) {
  const { ref, tip, show, hide } = useTip()
  const W = 640, H = 260, L = 34, R = 8, T = 10, B = 40
  const x = (v) => L + (v / 10) * (W - L - R)
  const y = (v) => T + (1 - v / 100) * (H - T - B)
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * W, py = ((e.clientY - box.top) / box.height) * H
    let best = null, bd = 1e9
    for (const p of points) {
      const d = (x(p[0]) - px) ** 2 + (y(p[1]) - py) ** 2
      if (d < bd) { bd = d; best = p }
    }
    if (best && bd < 200) show(e, <span>avg <b>{best[0]}%</b>, busy-time <b>{best[1]}%</b> → after halving ≈ <b>{Math.min(200, best[1] * 2).toFixed(0)}%</b></span>)
    else hide()
  }
  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Sample of flagged VMs: average CPU vs busy-time CPU" onMouseMove={onMove} onMouseLeave={hide}>
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}><line className="grid-line" x1={L} x2={W - R} y1={y(v)} y2={y(v)} /><text x={L - 6} y={y(v) + 4} textAnchor="end">{v}</text></g>
        ))}
        {[0, 2, 4, 6, 8, 10].map((v) => <text key={v} x={x(v)} y={H - 24} textAnchor="middle">{v}</text>)}
        {points.map((p, k) => (
          <circle key={k} cx={x(p[0])} cy={y(p[1])} r="2.4" fill={p[1] > 50 ? 'var(--series-2)' : 'var(--series-1)'} opacity="0.55" />
        ))}
        <line x1={L} x2={W - R} y1={y(50)} y2={y(50)} stroke="var(--critical)" strokeDasharray="4 4" />
        <text x={W - R} y={y(50) - 5} textAnchor="end" style={{ fill: 'var(--critical-text)' }}>above 50%: harmed after halving</text>
        <line x1={L} x2={W - R} y1={y(40)} y2={y(40)} stroke="var(--text-2)" strokeDasharray="2 3" />
        <text x={W - R} y={y(40) + 14} textAnchor="end">our rule: below 40%</text>
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle">average CPU (%)</text>
      </svg>
      <div className="legend">
        <span><i style={{ background: 'var(--series-1)' }} />Busy-time CPU ≤ 50%</span>
        <span><i style={{ background: 'var(--series-2)' }} />Busy-time CPU &gt; 50%</span>
        <span className="muted">Vertical axis: 95th percentile of 5-minute max CPU</span>
      </div>
      <Tip tip={tip} />
    </div>
  )
}
