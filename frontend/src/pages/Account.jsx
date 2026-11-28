import { useEffect, useState } from 'react'
import { api, KIND_NAMES, money } from '../api.js'

// Asks "are you sure?" before changing anything in the AWS account
function ConfirmFix({ finding, scanId, onCancel, onDone }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function go() {
    setBusy(true)
    setError(null)
    try {
      const result = await api.fix(scanId, finding.resource_id, finding.fix_action)
      onDone(result.message)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="overlay">
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Confirm">
        <h3>{finding.fix_label}?</h3>
        <p>{finding.title} ({finding.region})</p>
        <p>{finding.fix_warning}</p>
        <p>Saves about {money(finding.monthly_cost)} a month.</p>
        {error && <p className="error">{error}</p>}
        <div className="buttons">
          <button onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="delete" onClick={go} disabled={busy}>{busy ? 'Working...' : 'Yes, do it'}</button>
        </div>
      </div>
    </div>
  )
}

function Results({ report, onFix }) {
  const [open, setOpen] = useState(null)

  return (
    <>
      {report.scan.fake_aws && <p className="notice">This scan was made in test mode (fake AWS), not on a real account.</p>}

      <table className="summary">
        <tbody>
          <tr><td>Scanned</td><td>{new Date(report.scan.scanned_at).toLocaleString()}, {report.scan.regions} regions</td></tr>
          <tr><td>Total cost per month</td><td>{money(report.monthly_total)}</td></tr>
          <tr><td>Wasted per month</td><td className="red"><b>{money(report.monthly_waste)}</b> ({report.findings.length} problems)</td></tr>
        </tbody>
      </table>

      <h2>Problems found</h2>
      {report.findings.length === 0 ? <p>No waste found.</p> : (
        <table>
          <thead><tr><th>Problem</th><th>Region</th><th className="num">Per month</th><th /></tr></thead>
          <tbody>
            {report.findings.map((f) => (
              <FindingRows key={f.resource_id} f={f} open={open === f.resource_id}
                onToggle={() => setOpen(open === f.resource_id ? null : f.resource_id)} onFix={onFix} />
            ))}
          </tbody>
        </table>
      )}
      {report.notes.length > 0 && <ul className="muted small">{report.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      {report.buckets_without_lifecycle.length > 0 && (
        <p className="small">
          Tip: these S3 buckets have no lifecycle rule, so old files never move to cheaper storage:{' '}
          {report.buckets_without_lifecycle.join(', ')}.
        </p>
      )}

      <h2>Cost by region</h2>
      <table>
        <tbody>
          {Object.entries(report.by_region).map(([region, cost]) => (
            <tr key={region}><td>{region}</td><td className="num">{money(cost)}</td></tr>
          ))}
        </tbody>
      </table>

      <h2>Everything that costs money</h2>
      <div className="scroll">
        <table>
          <thead><tr><th>Region</th><th>Type</th><th>Name / ID</th><th>Details</th><th className="num">Per month</th></tr></thead>
          <tbody>
            {report.inventory.map((r) => (
              <tr key={r.id}>
                <td>{r.region}</td>
                <td>{KIND_NAMES[r.kind]}</td>
                <td className="id">{r.name || r.id}</td>
                <td>{r.detail}</td>
                <td className="num">{money(r.monthly_cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.scan.errors.length > 0 && <p className="error small">Could not read: {report.scan.errors.join('; ')}</p>}
    </>
  )
}

function FindingRows({ f, open, onToggle, onFix }) {
  return (
    <>
      <tr>
        <td><button className="link-like" onClick={onToggle}>{open ? '-' : '+'}</button> {f.title}<br /><span className="muted small">{f.rule}</span></td>
        <td>{f.region}</td>
        <td className="num">{money(f.monthly_cost)}</td>
        <td>
          {f.fix_action && onFix && <button className="delete" onClick={() => onFix(f)}>{f.fix_label}</button>}
          {!f.fix_action && <span className="small">{f.fix_label}</span>}
        </td>
      </tr>
      {open && (
        <tr className="details">
          <td colSpan="4">
            <p>{f.why}</p>
            <ul>
              {Object.entries(f.evidence).map(([k, v]) => <li key={k}>{k}: {v}</li>)}
              {f.calculation.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </td>
        </tr>
      )}
    </>
  )
}

export default function Account({ status, scans, onConnect, onScanned }) {
  const [scanId, setScanId] = useState(scans[0]?.id)
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [confirming, setConfirming] = useState(null)

  useEffect(() => {
    if (scanId) api.report(scanId).then(setReport).catch((e) => setError(e.message))
  }, [scanId])

  async function scan() {
    setBusy(true)
    setError(null)
    try {
      const { id } = await api.scan()
      await onScanned()
      setScanId(id)
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }

  async function fixed(text) {
    setConfirming(null)
    setMessage(text + ' Scanning again...')
    await scan()
    setMessage(text)
  }

  return (
    <>
      <h1>My AWS account</h1>
      <p className="muted">
        Scans every region of the account, lists everything that costs money, and finds things that are not
        being used. The AWS console only shows one region at a time.
      </p>

      {status?.connected ? (
        <p>
          <button onClick={scan} disabled={busy}>{busy ? 'Scanning all regions...' : 'Scan all regions'}</button>
          {scans.length > 1 && (
            <> {' '}Saved scans:{' '}
              <select value={scanId || ''} onChange={(e) => setScanId(e.target.value)}>
                {scans.map((s) => <option key={s.id} value={s.id}>{new Date(s.scanned_at).toLocaleString()}</option>)}
              </select>
            </>
          )}
        </p>
      ) : (
        <p>Not connected. <button onClick={onConnect}>Connect AWS</button></p>
      )}

      {error && <p className="error">{error}</p>}
      {message && <p className="ok">{message}</p>}
      {!report && !busy && <p className="muted">No scan yet.</p>}
      {report && <Results report={report} onFix={status?.connected ? setConfirming : null} />}

      {confirming && <ConfirmFix finding={confirming} scanId={scanId} onCancel={() => setConfirming(null)} onDone={fixed} />}
    </>
  )
}
