import { useEffect, useState } from 'react'
import { getReport, getScans, getStatus, money, runScan } from './api.js'

function Connection({ status, scanning, onScan }) {
  if (!status) return <span className="pill">Checking AWS…</span>
  if (!status.connected) return <span className="pill bad">Not connected to AWS</span>
  return (
    <div className="row">
      <span className="pill good">Connected · {status.account} · {status.region}</span>
      <button onClick={onScan} disabled={scanning || !status.prices_available}>
        {scanning ? 'Scanning…' : 'Scan now'}
      </button>
    </div>
  )
}

function ConnectHelp({ status }) {
  return (
    <div className="box">
      <h3>Connect your AWS account</h3>
      <ol>
        <li>Install the AWS CLI (version 2.32 or newer).</li>
        <li>Sign in from a terminal: <code>aws login --profile ccx</code></li>
        <li>Start the backend with that profile: <code>set AWS_PROFILE=ccx</code> then <code>uvicorn app.main:app</code></li>
      </ol>
      {status?.error && <p className="muted small">AWS said: {status.error}</p>}
    </div>
  )
}

function Finding({ f, open, onToggle }) {
  return (
    <div className={'finding' + (open ? ' open' : '')}>
      <button className="finding-head" onClick={onToggle}>
        <span>
          <b>{f.title}</b>
          <span className="muted small"> · {f.rule}</span>
        </span>
        <span className="cost">{money(f.monthly_cost)}/mo</span>
      </button>
      {open && (
        <div className="finding-body">
          <p>{f.why}</p>
          <h4>What we saw</h4>
          <table>
            <tbody>
              {Object.entries(f.evidence).map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td>{v}</td></tr>)}
            </tbody>
          </table>
          <h4>How the cost is calculated</h4>
          <ul>{f.calculation.map((c) => <li key={c}>{c}</li>)}</ul>
          <p className="muted small">AWS price used: {f.prices_used.join('; ')}</p>
          <h4>How to fix it</h4>
          {f.fix.map((c) => <pre key={c}>{c}</pre>)}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [status, setStatus] = useState(null)
  const [scans, setScans] = useState([])
  const [scanId, setScanId] = useState(null)
  const [report, setReport] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState(null)

  const loadScans = (select) =>
    getScans().then((list) => {
      setScans(list)
      setScanId(select || list[0]?.id || null)
    })

  useEffect(() => {
    getStatus().then(setStatus).catch(() => setStatus({ connected: false, error: 'Backend is not running.' }))
    loadScans().catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!scanId) return
    getReport(scanId).then((r) => { setReport(r); setError(null) }).catch((e) => setError(e.message))
  }, [scanId])

  async function scan() {
    setScanning(true)
    setError(null)
    try {
      const { id } = await runScan()
      await loadScans(id)
    } catch (e) {
      setError(e.message)
    }
    setScanning(false)
  }

  const current = scans.find((s) => s.id === scanId)

  return (
    <div className="page">
      <header>
        <div>
          <h1>Cloud Cost Optimizer</h1>
          <p className="muted">Finds AWS resources you are paying for but not using.</p>
        </div>
        <Connection status={status} scanning={scanning} onScan={scan} />
      </header>

      {status && !status.connected && <ConnectHelp status={status} />}
      {status?.connected && !status.prices_available && (
        <div className="box bad">No prices saved for {status.region}. Run <code>python scripts/fetch_prices.py --region {status.region}</code></div>
      )}
      {error && <div className="box bad">{error}</div>}

      {scans.length > 0 && (
        <div className="row">
          <label className="muted" htmlFor="scan">Showing</label>
          <select id="scan" value={scanId || ''} onChange={(e) => { setScanId(e.target.value); setOpenId(null) }}>
            {scans.map((s) => (
              <option key={s.id} value={s.id}>
                {s.source === 'sample' ? 'Sample data (not a real account)' : `${s.account} · ${new Date(s.scanned_at).toLocaleString()}`}
              </option>
            ))}
          </select>
          {current && <span className={'pill ' + (current.source === 'aws' ? 'good' : 'warn')}>{current.source === 'aws' ? 'Real AWS data' : 'Sample data'}</span>}
        </div>
      )}

      {report && (
        <>
          <div className="cards">
            <div className="card"><span className="muted">Monthly cost of scanned resources</span><b>{money(report.monthly_cost)}</b></div>
            <div className="card"><span className="muted">Wasted per month</span><b className="accent">{money(report.monthly_waste)}</b></div>
            <div className="card"><span className="muted">Problems found</span><b>{report.findings.length}</b></div>
          </div>
          <p className="muted small">
            Scanned {report.counts.instances} servers, {report.counts.volumes} disks, {report.counts.elastic_ips} IPs
            and {report.counts.snapshots} snapshots in {report.scan.region}. Prices from the AWS Price List
            (version {report.price_list_version}), before free-tier credits.
          </p>

          <h2>Findings</h2>
          {report.findings.length === 0 && <div className="box">No waste found.</div>}
          {report.findings.map((f) => (
            <Finding key={f.resource_id + f.rule} f={f} open={openId === f.resource_id}
              onToggle={() => setOpenId(openId === f.resource_id ? null : f.resource_id)} />
          ))}

          {report.notes.length > 0 && (
            <>
              <h2>Not checked yet</h2>
              <ul className="muted">{report.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </>
          )}
        </>
      )}
    </div>
  )
}
