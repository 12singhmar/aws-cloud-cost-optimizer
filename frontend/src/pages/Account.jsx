import { useEffect, useState } from 'react'
import { api, money } from '../api.js'

function Finding({ f, open, onToggle }) {
  return (
    <div className={'step' + (open ? ' applied' : '')}>
      <button className="step-head" onClick={onToggle}>
        <span className="step-icon" aria-hidden="true">!</span>
        <span className="step-title">{f.title}<span className="muted"> · {f.rule}</span></span>
        <span className="saving">{money(f.monthly_cost)}/mo</span>
      </button>
      {open && (
        <div className="step-body">
          <p>{f.why}</p>
          <table className="table kv"><tbody>
            {Object.entries(f.evidence).map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td>{v}</td></tr>)}
          </tbody></table>
          <ul>{f.calculation.map((c) => <li key={c}>{c}</li>)}</ul>
          <p className="muted small">AWS price: {f.prices_used.join('; ')}</p>
          <h4>Fix</h4>
          {f.fix.map((c) => <pre key={c}>{c}</pre>)}
        </div>
      )}
    </div>
  )
}

export default function Account({ status, scans, onConnect, onScanned, go }) {
  const awsScans = scans.filter((s) => s.source === 'aws')
  const [scanId, setScanId] = useState(awsScans[0]?.id)
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null)

  useEffect(() => {
    if (scanId) api.report(scanId).then(setReport).catch((e) => setError(e.message))
  }, [scanId])

  async function scan() {
    setBusy(true); setError(null)
    try {
      const { id } = await api.scan()
      await onScanned()
      setScanId(id)
    } catch (e) { setError(e.message) }
    setBusy(false)
  }

  if (!status?.connected) {
    return (
      <div className="panel hero-panel">
        <h2>Connect your AWS account</h2>
        <p className="muted">The tool reads your account with read-only calls (describe / get). It never changes,
          stops or deletes anything. Your keys stay in the AWS CLI on this computer; they are never typed into this page.</p>
        <ul className="ticks">
          <li>Finds unattached disks, unused IPs, stopped servers, orphaned snapshots and idle servers</li>
          <li>Prices each problem with the real AWS price list</li>
          <li>Sends real CPU history to Usage Analysis and the Cost Planner</li>
        </ul>
        <button className="primary" onClick={onConnect}>Connect AWS</button>
      </div>
    )
  }

  return (
    <div className="stack">
      <div className="panel account-bar">
        <div>
          <span className="muted small">Connected account</span>
          <b>{status.account} · {status.region}</b>
          <span className="muted small">profile {status.profile || 'default'} · {status.arn_type}</span>
        </div>
        <div className="row">
          {awsScans.length > 0 && (
            <select value={scanId || ''} onChange={(e) => setScanId(e.target.value)} aria-label="Saved scans">
              {awsScans.map((s) => <option key={s.id} value={s.id}>{new Date(s.scanned_at).toLocaleString()}</option>)}
            </select>
          )}
          <button className="primary" onClick={scan} disabled={busy || !status.prices_available}>{busy ? 'Scanning…' : 'Scan now'}</button>
        </div>
      </div>
      {!status.prices_available && <div className="panel warning">No prices saved for {status.region}. Run: python scripts/fetch_prices.py --region {status.region}</div>}
      {error && <div className="panel error">{error}</div>}
      {!scanId && <div className="panel muted">No scan yet. Click “Scan now” — it takes a few seconds.</div>}

      {report && (
        <>
          <div className="summary">
            <div className="panel stat"><span>Monthly cost of scanned resources</span><b>{money(report.monthly_cost)}</b><small>list price, before credits</small></div>
            <div className="panel stat"><span>Wasted per month</span><b className="accent">{money(report.monthly_waste)}</b><small>{money(report.monthly_waste * 12, 0)} per year</small></div>
            <div className="panel stat"><span>Problems found</span><b>{report.findings.length}</b>
              <small>{report.counts.instances} servers · {report.counts.volumes} disks · {report.counts.elastic_ips} IPs · {report.counts.snapshots} snapshots</small></div>
          </div>
          <div className="panel">
            <div className="panel-head"><h2>Waste found</h2>
              <button className="link" onClick={() => go('usage')}>Analyze server usage →</button></div>
            {report.findings.length === 0 && <p className="muted">Nothing wasted. Nice.</p>}
            {report.findings.map((f) => (
              <Finding key={f.resource_id + f.rule} f={f} open={open === f.resource_id}
                onToggle={() => setOpen(open === f.resource_id ? null : f.resource_id)} />
            ))}
            {report.notes.length > 0 && <><h4>Not checked yet</h4><ul className="muted">{report.notes.map((n) => <li key={n}>{n}</li>)}</ul></>}
          </div>
        </>
      )}
    </div>
  )
}
