import { useEffect, useMemo, useState } from 'react'
import { api, money } from '../api.js'

const DEFAULT_WORKLOAD = {
  name: 'Office-hours dev server', region: 'ap-south-1', instance_type: 'm5.xlarge', count: 1,
  running_hours_per_week: 168, needed_hours_per_week: 50, peak_cpu: 30, avg_cpu: 10,
  memory_needed_gb: null, storage_gb: 100, storage_type: 'gp2',
  arm_ok: false, commit_years: 0, region_flexible: false,
}

const PRESETS = [
  DEFAULT_WORKLOAD,
  { ...DEFAULT_WORKLOAD, name: 'Always-on web app', instance_type: 'm5.large', needed_hours_per_week: 168,
    peak_cpu: 35, avg_cpu: 15, storage_gb: 30, commit_years: 1 },
  { ...DEFAULT_WORKLOAD, name: 'Oversized database server', instance_type: 'r5.xlarge', needed_hours_per_week: 168,
    peak_cpu: 20, avg_cpu: 8, storage_gb: 500, commit_years: 1 },
]

const HOUR_CHOICES = [
  { label: '24/7', hours: 168 },
  { label: 'Weekdays 8–8', hours: 60 },
  { label: 'Weekdays 9–6', hours: 45 },
]

function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

function NumberInput({ value, onChange, min = 0, max, step = 1, placeholder }) {
  return (
    <input type="number" value={value ?? ''} min={min} max={max} step={step} placeholder={placeholder}
      onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
  )
}

function Hours({ value, onChange }) {
  return (
    <div className="hours">
      <NumberInput value={value} min={1} max={168} onChange={(v) => onChange(v ?? 168)} />
      <span className="muted small">h/week</span>
      {HOUR_CHOICES.map((c) => (
        <button type="button" key={c.label} className={'chip' + (value === c.hours ? ' on' : '')} onClick={() => onChange(c.hours)}>{c.label}</button>
      ))}
    </div>
  )
}

const LEVER_ICON = { rightsize: '⇲', arm: '◆', pricing: '◷', storage: '▤', region: '◎' }

function Step({ s, open, onToggle, region }) {
  return (
    <div className={'step' + (s.applied ? ' applied' : '')}>
      <button className="step-head" onClick={onToggle}>
        <span className="step-icon" aria-hidden="true">{LEVER_ICON[s.lever]}</span>
        <span className="step-title">{s.title}{s.to && <span className="muted"> · {s.from} → {s.to}</span>}</span>
        <span className={s.applied ? 'saving' : 'muted small'}>{s.applied ? `−${money(s.saving)}/mo` : 'no change'}</span>
      </button>
      {open && (
        <div className="step-body">
          <ul>{s.details.map((d) => <li key={d}>{d}</li>)}</ul>
          {s.options && (
            <table className="table">
              <thead><tr><th>Option</th><th className="num">Per month</th></tr></thead>
              <tbody>{s.options.map((o) => (
                <tr key={o.name} className={o.chosen ? 'chosen' : ''}><td>{o.name}{o.chosen && ' ✓'}</td><td className="num">{money(o.monthly)}</td></tr>
              ))}</tbody>
            </table>
          )}
          {s.comparison && (
            <table className="table">
              <thead><tr><th>Region</th><th className="num">Same plan per month</th></tr></thead>
              <tbody>{s.comparison.map((r) => (
                <tr key={r.region} className={r.region === region ? 'chosen' : ''}><td>{r.region}{r.region === region && ' (current)'}</td><td className="num">{money(r.monthly)}</td></tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default function Planner({ regions, initial, note }) {
  const [w, setW] = useState(initial || DEFAULT_WORKLOAD)
  const [catalog, setCatalog] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState('rightsize')
  const set = (key) => (value) => setW((old) => ({ ...old, [key]: value }))

  useEffect(() => { api.catalog(w.region).then(setCatalog).catch(() => setCatalog([])) }, [w.region])

  useEffect(() => {
    const t = setTimeout(() => {
      api.optimize(w).then((r) => { setResult(r); setError(null) }).catch((e) => setError(e.message))
    }, 250)
    return () => clearTimeout(t)
  }, [w])

  // group instance types by family (m5, t3, ...) for the dropdown
  const families = useMemo(() => {
    const groups = {}
    for (const c of catalog) {
      const family = c.type.split('.')[0]
      if (!groups[family]) groups[family] = []
      groups[family].push(c)
    }
    return groups
  }, [catalog])

  // cost after each applied step, for the plan table
  const rows = []
  if (result) {
    let cost = result.baseline_monthly
    for (const s of result.steps) {
      if (s.applied) {
        cost = cost - s.saving
        rows.push({ step: s, after: cost })
      }
    }
  }

  return (
    <div className="planner">
      <section className="panel form">
        <div className="panel-head">
          <h2>Your workload</h2>
          <div className="presets">
            {PRESETS.map((p) => <button key={p.name} className="chip" onClick={() => setW(p)}>{p.name}</button>)}
          </div>
        </div>
        {note && <p className="note">{note}</p>}

        <h3>Server</h3>
        <div className="grid2">
          <Field label="Region">
            <select value={w.region} onChange={(e) => set('region')(e.target.value)}>
              {regions.map((r) => <option key={r.code} value={r.code}>{r.name} ({r.code})</option>)}
            </select>
          </Field>
          <Field label="Number of servers">
            <NumberInput value={w.count} min={1} onChange={(v) => set('count')(v || 1)} />
          </Field>
        </div>
        <Field label="Instance type">
          <select value={w.instance_type} onChange={(e) => set('instance_type')(e.target.value)}>
            {Object.entries(families).map(([fam, items]) => (
              <optgroup key={fam} label={fam}>
                {items.map((c) => <option key={c.type} value={c.type}>{c.type} · {c.vcpu} vCPU · {c.memory_gib} GiB · {money(c.hourly, 4)}/h</option>)}
              </optgroup>
            ))}
          </select>
        </Field>

        <h3>Usage</h3>
        <Field label="Runs today"><Hours value={w.running_hours_per_week} onChange={set('running_hours_per_week')} /></Field>
        <Field label="Actually needed"><Hours value={w.needed_hours_per_week} onChange={set('needed_hours_per_week')} /></Field>
        <div className="grid2">
          <Field label="Busy-time CPU %" hint="95th percentile of hourly max. Empty = unknown">
            <NumberInput value={w.peak_cpu} max={100} onChange={set('peak_cpu')} placeholder="unknown" />
          </Field>
          <Field label="Average CPU %" hint="Needed to judge burstable (t3/t4g) types">
            <NumberInput value={w.avg_cpu} max={100} onChange={set('avg_cpu')} placeholder="unknown" />
          </Field>
        </div>
        <Field label="Memory needed (GiB)" hint="Empty = keep the current amount (CloudWatch does not measure memory)">
          <NumberInput value={w.memory_needed_gb} step={0.5} onChange={set('memory_needed_gb')} placeholder="same as now" />
        </Field>

        <h3>Disk</h3>
        <div className="grid2">
          <Field label="Size (GB)"><NumberInput value={w.storage_gb} onChange={(v) => set('storage_gb')(v ?? 0)} /></Field>
          <Field label="Type">
            <select value={w.storage_type} onChange={(e) => set('storage_type')(e.target.value)}>
              {['gp2', 'gp3', 'st1', 'sc1'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </Field>
        </div>

        <h3>What are you OK with?</h3>
        <label className="check"><input type="checkbox" checked={w.arm_ok} onChange={(e) => set('arm_ok')(e.target.checked)} /> Software can run on ARM (Graviton)</label>
        <label className="check"><input type="checkbox" checked={w.region_flexible} onChange={(e) => set('region_flexible')(e.target.checked)} /> Can move to another region</label>
        <div className="segmented" role="radiogroup" aria-label="Commitment">
          {[[0, 'No commitment'], [1, 'Up to 1 year'], [3, 'Up to 3 years']].map(([v, l]) => (
            <button key={v} role="radio" aria-checked={w.commit_years === v} className={w.commit_years === v ? 'on' : ''} onClick={() => set('commit_years')(v)}>{l}</button>
          ))}
        </div>
      </section>

      <section className="results">
        {error && <div className="panel error">{error}</div>}
        {result && (
          <>
            <div className="summary">
              <div className="panel stat"><span>Today</span><b>{money(result.baseline_monthly)}</b><small>per month</small></div>
              <div className="panel stat"><span>Optimized</span><b className="accent">{money(result.optimized_monthly)}</b><small>per month</small></div>
              <div className="panel stat good"><span>You save</span><b>{result.saving_percent}%</b><small>{money(result.saving_monthly * 12, 0)} per year</small></div>
            </div>

            {result.warnings.map((m) => <div key={m} className="panel warning">⚠ {m}</div>)}

            <div className="panel">
              <div className="panel-head"><h2>New plan</h2><span className="muted small">monthly cost, real AWS prices</span></div>
              <table className="table">
                <thead><tr><th>Step</th><th className="num">Cost after this step</th><th className="num">Saved</th></tr></thead>
                <tbody>
                  <tr><td>Today</td><td className="num">{money(result.baseline_monthly)}</td><td /></tr>
                  {rows.map((r) => (
                    <tr key={r.step.lever}><td>{r.step.title}</td><td className="num">{money(r.after)}</td><td className="num saving">−{money(r.step.saving)}</td></tr>
                  ))}
                  <tr className="total"><td>Optimized</td><td className="num">{money(result.optimized_monthly)}</td><td className="num saving">−{money(result.saving_monthly)}</td></tr>
                </tbody>
              </table>
              <div className="plan">
                <span>Plan:</span>
                <b>{w.count} × {result.plan.instance_type}</b>
                <b>{result.plan.pricing}</b>
                <b>{result.plan.hours_per_week} h/week</b>
                {w.storage_gb > 0 && <b>{w.storage_gb} GB {result.plan.storage_type}</b>}
                <b>{result.plan.region}</b>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head"><h2>How we got there</h2><span className="muted small">each step starts from the previous one</span></div>
              {result.steps.map((s) => <Step key={s.lever} s={s} region={w.region} open={open === s.lever} onToggle={() => setOpen(open === s.lever ? null : s.lever)} />)}
            </div>

            {result.candidates.length > 0 && (
              <div className="panel">
                <div className="panel-head"><h2>Cheapest types that fit</h2><span className="muted small">on-demand price per hour</span></div>
                <table className="table">
                  <thead><tr><th>Type</th><th>Kind</th><th className="num">vCPU</th><th className="num">Memory</th><th className="num">Per hour</th></tr></thead>
                  <tbody>{result.candidates.map((c) => (
                    <tr key={c.type} className={c.type === result.plan.instance_type ? 'chosen' : ''}>
                      <td>{c.type}{c.arm && <span className="tag">ARM</span>}</td>
                      <td className="muted">{c.category}</td>
                      <td className="num">{c.vcpu}</td><td className="num">{c.memory_gib} GiB</td>
                      <td className="num">{money(c.hourly, 4)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            <p className="muted small">AWS Price List version {result.price_list_version}. On-demand Linux prices; 730 hours per month.</p>
          </>
        )}
      </section>
    </div>
  )
}
