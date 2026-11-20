import { useEffect, useState } from 'react'
import { api } from '../api.js'

const VERDICT_CLASS = {
  Idle: 'bad',
  'Can follow a schedule': 'warn',
  Oversized: 'warn',
  'Well used': 'good',
}

export function Verdict({ value }) {
  return <span className={'badge ' + (VERDICT_CLASS[value] || 'muted')}>{value}</span>
}

function Detail({ s, source, onOptimize }) {
  const note = `From usage analysis of ${s.name || s.id}: busy-time CPU ${s.busy_cpu}%, average ${s.avg_cpu}%.` +
    (source === 'public' ? ' The dataset does not say which instance type it was, so m5.large is assumed. Change it below.' : '')

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>{s.name || s.id}</h2>
          <span className="muted small">{s.type}{source === 'public' && ' (assumed)'} · {s.hours} hours of data</span>
        </div>
        <Verdict value={s.verdict} />
      </div>

      {s.by_day && (
        <>
          <div className="mini-stats">
            <div><span>Average CPU</span><b>{s.avg_cpu}%</b></div>
            <div><span>Busy-time CPU</span><b>{s.busy_cpu}%</b><small>95th percentile of hourly max</small></div>
            <div><span>Highest</span><b>{s.max_cpu}%</b></div>
            <div><span>Quiet hours</span><b>{s.quiet_hours_per_week}</b><small>per week</small></div>
          </div>

          <h3>Average CPU by day</h3>
          <div className="day-bars">
            {s.by_day.map((d) => (
              <div className="day-row" key={d.day}>
                <span>{d.day}</span>
                <div className="track"><div className="fill" style={{ width: `${Math.min(100, d.avg_cpu ?? 0)}%` }} /></div>
                <span className="num">{d.avg_cpu ?? '–'}%</span>
              </div>
            ))}
          </div>
        </>
      )}

      <h3>What this means</h3>
      <ul>{s.reasons.map((r) => <li key={r}>{r}</li>)}</ul>

      {s.quiet_windows?.length > 0 && s.verdict !== 'Idle' && (
        <>
          <h3>Quiet in every week we saw</h3>
          <ul>{s.quiet_windows.map((q) => <li key={q.from}>{q.from} to {q.to} ({q.hours} hours)</li>)}</ul>
        </>
      )}

      {s.workload && <button className="primary" onClick={() => onOptimize(s.workload, note)}>Optimize this server →</button>}
    </div>
  )
}

export default function Usage({ scans, onOptimize }) {
  const [scanId, setScanId] = useState(scans[0]?.id)
  const [data, setData] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!scanId) return
    api.usage(scanId)
      .then((d) => { setData(d); setSelected(d.servers[0]?.id) })
      .catch((e) => setError(e.message))
  }, [scanId])

  if (scans.length === 0) {
    return <div className="panel">No usage data yet. Connect AWS, or run scripts/import_public_data.py.</div>
  }
  const current = data?.servers.find((s) => s.id === selected)

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-head">
          <h2>Servers</h2>
          <select value={scanId} onChange={(e) => setScanId(e.target.value)} aria-label="Data source">
            {scans.map((s) => (
              <option key={s.id} value={s.id}>
                {s.source === 'public' ? 'Public AWS dataset (8 servers)' : `Your account, ${new Date(s.scanned_at).toLocaleString()}`}
              </option>
            ))}
          </select>
        </div>
        {data?.scan.description && <p className="muted small">{data.scan.description}</p>}
        {error && <p className="error-text">{error}</p>}
        {data && (
          <table className="table clickable">
            <thead>
              <tr><th>Server</th><th>Type</th><th>Verdict</th><th className="num">Avg CPU</th><th className="num">Busy-time CPU</th><th className="num">Quiet h/week</th></tr>
            </thead>
            <tbody>
              {data.servers.map((s) => (
                <tr key={s.id} className={s.id === selected ? 'chosen' : ''} onClick={() => setSelected(s.id)}>
                  <td>{s.name || s.id}</td>
                  <td className="muted">{s.type}</td>
                  <td><Verdict value={s.verdict} /></td>
                  <td className="num">{s.avg_cpu ?? '–'}%</td>
                  <td className="num">{s.busy_cpu ?? '–'}%</td>
                  <td className="num">{s.quiet_hours_per_week ?? '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {current && <Detail s={current} source={data.scan.source} onOptimize={onOptimize} />}
    </div>
  )
}
