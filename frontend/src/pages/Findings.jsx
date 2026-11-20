import { Fragment, useMemo, useState } from 'react'
import { BacktestChart } from '../charts.jsx'
import { usd } from '../api.js'
import { Card, Empty, PageHead, Verdict } from '../ui.jsx'

function Detail({ f }) {
  return (
    <div className="detail">
      <Card>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          <span className="badge">{f.rule_name}</span>
          <span className={`badge p-${f.priority}`}>{f.priority} priority</span>
          {f.status === 'blocked' && <span className="badge bad">✕ Blocked by backtest</span>}
        </div>
        <h2 style={{ fontSize: '1.15rem' }}>{f.title}</h2>
        <p className="muted small" style={{ marginTop: 4 }}>{f.resource_type} · <span className="mono">{f.resource_id}</span></p>
        <p style={{ marginTop: 10 }}>{f.summary}</p>
        {f.blocked_reason && <p className="small" style={{ marginTop: 8, color: 'var(--critical-text)' }}>{f.blocked_reason}</p>}
        <div className="grid grid-3" style={{ marginTop: 14 }}>
          <div><div className="section-label">Saving / month</div><b>{f.monthly_savings === null ? 'not estimated' : usd(f.monthly_savings)}</b></div>
          <div><div className="section-label">Confidence</div><b>{f.confidence}</b><div className="muted small">{f.confidence_reason}</div></div>
          <div><div className="section-label">Risk</div><b>{f.risk}</b><div className="muted small">{f.risk_reason}</div></div>
        </div>
      </Card>

      <Card title="Evidence" sub="what we observed">
        <dl className="kv">{f.evidence.map((e) => <Fragment key={e.label}><dt>{e.label}</dt><dd>{e.value}</dd></Fragment>)}</dl>
      </Card>

      <Card title="How the saving is calculated" sub="real AWS prices">
        <ul className="calc">
          {f.calculation.map((c, k) => <li key={k}><span>{c.text}</span>{c.usd !== null && c.usd !== undefined && <span className="num">{usd(c.usd, 2)}</span>}</li>)}
        </ul>
        <div className="section-label" style={{ marginTop: 12 }}>Prices used (AWS SKU)</div>
        <ul className="steps small">
          {f.prices_used.map((p) => <li key={p.sku + p.key}><span className="mono">{p.sku}</span> — {p.description}</li>)}
        </ul>
      </Card>

      {f.backtest && (
        <Card title="Backtest" sub={`decided on ${f.backtest.train_hours} h, checked on ${f.backtest.test_hours} h`}>
          <p style={{ marginBottom: 10 }}><Verdict value={f.backtest.verdict} /> <span className="small">{f.backtest.detail}</span></p>
          {f.backtest.series && <BacktestChart series={f.backtest.series} />}
        </Card>
      )}

      <Card title="Check it yourself" sub="read-only commands">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {f.check_commands.map((c) => <div className="cmd" key={c}>{c}</div>)}
        </div>
      </Card>
      <Card title="How to fix" sub="the tool never changes anything itself">
        <ol className="steps">{f.fix_steps.map((s) => <li key={s}>{s.startsWith('aws ') ? <span className="mono">{s}</span> : s}</li>)}</ol>
      </Card>
    </div>
  )
}

export default function Findings({ analysis, selected, onSelect }) {
  const [filter, setFilter] = useState('All')
  const services = useMemo(() => ['All', ...new Set(analysis.findings.map((f) => f.resource_type))], [analysis])
  const list = analysis.findings.filter((f) => filter === 'All' || f.resource_type === filter)
  const current = analysis.findings.find((f) => f.id === selected) || list[0]

  if (!analysis.findings.length) {
    return (<><PageHead title="Findings" /><Empty title="No waste found">Every resource passed all rules. See Overview for anything we could not judge.</Empty></>)
  }
  return (
    <>
      <PageHead title="Findings">
        Each finding shows the evidence, the price maths with official AWS SKUs, commands to double-check it,
        and safe fix steps. Findings that failed their backtest stay visible but are not counted as savings.
      </PageHead>
      <div className="pill-row" role="group" aria-label="Filter by resource type">
        {services.map((s) => <button key={s} className="pill" aria-pressed={filter === s} onClick={() => setFilter(s)}>{s}</button>)}
      </div>
      <div className="findings-layout">
        <div className="finding-list">
          {list.map((f) => (
            <button key={f.id} className={`finding-row ${f.status === 'blocked' ? 'blocked' : ''}`}
              aria-pressed={current?.id === f.id} onClick={() => onSelect(f.id)}>
              <span className="t">{f.title}</span>
              <span className="usd">{f.status === 'blocked' ? '—' : f.monthly_savings === null ? 'n/a' : usd(f.monthly_savings)}</span>
              <span className="m">
                <span className={`badge p-${f.priority}`}>{f.priority}</span>
                <span>{f.rule_name}</span>
                {f.status === 'blocked' && <span className="badge bad">✕ blocked</span>}
                {f.backtest && f.status !== 'blocked' && <Verdict value={f.backtest.verdict} />}
              </span>
              <span className="m">/mo</span>
            </button>
          ))}
        </div>
        {current && <Detail f={current} />}
      </div>
    </>
  )
}
