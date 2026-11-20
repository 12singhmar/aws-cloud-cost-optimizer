import { useEffect, useState } from 'react'
import { api, money } from '../api.js'

const DEFAULT_WORKLOAD = {
  name: 'My server', region: 'ap-south-1', instance_type: 'm5.xlarge', count: 1,
  running_hours_per_week: 168, needed_hours_per_week: 50, peak_cpu: 30, avg_cpu: 10,
  memory_needed_gb: null, storage_gb: 100, storage_type: 'gp2',
  arm_ok: false, commit_years: 0, region_flexible: false,
}

// number input that allows an empty value (null)
function NumberBox({ value, onChange, min = 0, max }) {
  return (
    <input type="number" value={value ?? ''} min={min} max={max}
      onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
  )
}

function Step({ s, open, onToggle, region }) {
  return (
    <div className={'step' + (s.applied ? ' applied' : '')}>
      <button className="step-head" onClick={onToggle}>
        <span className="step-title">{s.title}{s.to && <span className="muted"> ({s.from} to {s.to})</span>}</span>
        <span className={s.applied ? 'saving' : 'muted small'}>{s.applied ? `−${money(s.saving)}/mo` : 'no change'}</span>
      </button>
      {open && (
        <div className="step-body">
          <ul>{s.details.map((d) => <li key={d}>{d}</li>)}</ul>
          {s.options && (
            <table className="table">
              <thead><tr><th>Option</th><th className="num">Per month</th></tr></thead>
              <tbody>{s.options.map((o) => (
                <tr key={o.name} className={o.chosen ? 'chosen' : ''}><td>{o.name}{o.chosen && ' (chosen)'}</td><td className="num">{money(o.monthly)}</td></tr>
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
  const [open, setOpen] = useState(null)
  const [showMore, setShowMore] = useState(false)

  function set(key, value) {
    setW({ ...w, [key]: value })
  }

  useEffect(() => {
    api.catalog(w.region).then(setCatalog).catch(() => setCatalog([]))
  }, [w.region])

  const knownType = catalog.some((c) => c.type === w.instance_type)

  // run the optimizer a moment after the user stops typing
  useEffect(() => {
    if (catalog.length > 0 && !knownType) return
    const timer = setTimeout(() => {
      api.optimize(w)
        .then((r) => { setResult(r); setError(null) })
        .catch((e) => setError(e.message))
    }, 300)
    return () => clearTimeout(timer)
  }, [w, knownType, catalog.length])

  // cost after each applied step
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
        <h2>Your server</h2>
        {note && <p className="note">{note}</p>}

        <label className="field">
          <span>Instance type</span>
          <input list="types" value={w.instance_type} onChange={(e) => set('instance_type', e.target.value.trim())} />
          <datalist id="types">
            {catalog.map((c) => <option key={c.type} value={c.type}>{c.vcpu} vCPU, {c.memory_gib} GiB</option>)}
          </datalist>
          {catalog.length > 0 && !knownType && <small className="error-text">Unknown type for this region</small>}
        </label>

        <label className="field">
          <span>Hours needed per week <small className="muted">(168 = always on)</small></span>
          <NumberBox value={w.needed_hours_per_week} min={1} max={168} onChange={(v) => set('needed_hours_per_week', v ?? 168)} />
        </label>

        <div className="grid2">
          <label className="field">
            <span>Busy-time CPU %</span>
            <NumberBox value={w.peak_cpu} max={100} onChange={(v) => set('peak_cpu', v)} />
          </label>
          <label className="field">
            <span>Average CPU %</span>
            <NumberBox value={w.avg_cpu} max={100} onChange={(v) => set('avg_cpu', v)} />
          </label>
        </div>
        <p className="muted small">Leave CPU empty if you don't know it. Usage Analysis can measure it for you.</p>

        <button className="link" onClick={() => setShowMore(!showMore)}>
          {showMore ? 'Fewer options' : 'More options'}
        </button>

        {showMore && (
          <div className="more">
            <label className="field">
              <span>Region</span>
              <select value={w.region} onChange={(e) => set('region', e.target.value)}>
                {regions.map((r) => <option key={r.code} value={r.code}>{r.name} ({r.code})</option>)}
              </select>
            </label>
            <div className="grid2">
              <label className="field">
                <span>Hours it runs now</span>
                <NumberBox value={w.running_hours_per_week} min={1} max={168} onChange={(v) => set('running_hours_per_week', v ?? 168)} />
              </label>
              <label className="field">
                <span>Number of servers</span>
                <NumberBox value={w.count} min={1} onChange={(v) => set('count', v || 1)} />
              </label>
            </div>
            <label className="field">
              <span>Memory needed (GiB) <small className="muted">empty = same as now</small></span>
              <NumberBox value={w.memory_needed_gb} onChange={(v) => set('memory_needed_gb', v)} />
            </label>
            <div className="grid2">
              <label className="field">
                <span>Disk size (GB)</span>
                <NumberBox value={w.storage_gb} onChange={(v) => set('storage_gb', v ?? 0)} />
              </label>
              <label className="field">
                <span>Disk type</span>
                <select value={w.storage_type} onChange={(e) => set('storage_type', e.target.value)}>
                  <option>gp2</option><option>gp3</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>Can you commit for a year or more?</span>
              <select value={w.commit_years} onChange={(e) => set('commit_years', Number(e.target.value))}>
                <option value={0}>No</option>
                <option value={1}>Yes, 1 year</option>
                <option value={3}>Yes, 3 years</option>
              </select>
            </label>
            <label className="check"><input type="checkbox" checked={w.arm_ok} onChange={(e) => set('arm_ok', e.target.checked)} /> Software can run on ARM (Graviton)</label>
            <label className="check"><input type="checkbox" checked={w.region_flexible} onChange={(e) => set('region_flexible', e.target.checked)} /> Can move to another region</label>
          </div>
        )}
      </section>

      <section className="results">
        {error && <div className="panel error">{error}</div>}
        {result && (
          <>
            <div className="summary">
              <div className="stat"><span>Now</span><b>{money(result.baseline_monthly)}</b><small>per month</small></div>
              <div className="stat"><span>After</span><b>{money(result.optimized_monthly)}</b><small>per month</small></div>
              <div className="stat highlight"><span>Saved</span><b>{result.saving_percent}%</b><small>{money(result.saving_monthly * 12, 0)} a year</small></div>
            </div>

            {result.warnings.map((m) => <div key={m} className="panel warning">{m}</div>)}

            <div className="panel">
              <h2>New plan</h2>
              <p className="plan">
                {w.count} × <b>{result.plan.instance_type}</b>, {result.plan.pricing.toLowerCase()},{' '}
                {result.plan.hours_per_week} h/week{w.storage_gb > 0 && `, ${w.storage_gb} GB ${result.plan.storage_type}`}, {result.plan.region}
              </p>
              <table className="table">
                <thead><tr><th>Step</th><th className="num">Monthly cost</th><th className="num">Saved</th></tr></thead>
                <tbody>
                  <tr><td>Now</td><td className="num">{money(result.baseline_monthly)}</td><td /></tr>
                  {rows.map((r) => (
                    <tr key={r.step.lever}><td>{r.step.title}</td><td className="num">{money(r.after)}</td><td className="num saving">−{money(r.step.saving)}</td></tr>
                  ))}
                  <tr className="total"><td>After</td><td className="num">{money(result.optimized_monthly)}</td><td className="num saving">−{money(result.saving_monthly)}</td></tr>
                </tbody>
              </table>
            </div>

            <div className="panel">
              <h2>Details of each step</h2>
              {result.steps.map((s) => (
                <Step key={s.lever} s={s} region={w.region} open={open === s.lever}
                  onToggle={() => setOpen(open === s.lever ? null : s.lever)} />
              ))}
            </div>

            {result.candidates.some((c) => w.arm_ok || !c.arm) && (
              <div className="panel">
                <h2>Cheapest types that fit</h2>
                <table className="table">
                  <thead><tr><th>Type</th><th className="num">vCPU</th><th className="num">Memory</th><th className="num">Per hour</th></tr></thead>
                  <tbody>{result.candidates.filter((c) => w.arm_ok || !c.arm).map((c) => (
                    <tr key={c.type} className={c.type === result.plan.instance_type ? 'chosen' : ''}>
                      <td>{c.type}{c.arm && ' (ARM)'}</td>
                      <td className="num">{c.vcpu}</td><td className="num">{c.memory_gib} GiB</td>
                      <td className="num">{money(c.hourly, 4)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            <p className="muted small">AWS Price List version {result.price_list_version}, Linux on-demand prices, 730 hours a month.</p>
          </>
        )}
      </section>
    </div>
  )
}
