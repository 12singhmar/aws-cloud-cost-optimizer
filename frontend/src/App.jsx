import { useEffect, useState } from 'react'
import { api, date, usd } from './api.js'
import Backtest from './pages/Backtest.jsx'
import BillCheck from './pages/BillCheck.jsx'
import Findings from './pages/Findings.jsx'
import Fleet from './pages/Fleet.jsx'
import Lab from './pages/Lab.jsx'
import Method from './pages/Method.jsx'
import Overview from './pages/Overview.jsx'

const PAGES = [
  { id: 'overview', label: 'Overview', group: 'Account' },
  { id: 'findings', label: 'Findings', group: 'Account' },
  { id: 'backtest', label: 'Backtest', group: 'Proof' },
  { id: 'lab', label: 'Waste Lab', group: 'Proof' },
  { id: 'bill', label: 'Bill Check', group: 'Proof' },
  { id: 'fleet', label: 'Fleet Study', group: 'Research' },
  { id: 'method', label: 'How it works', group: 'Research' },
]

const pageFromHash = () => {
  const id = window.location.hash.replace('#/', '')
  return PAGES.some((p) => p.id === id) ? id : 'overview'
}

function readTheme() {
  try { return localStorage.getItem('theme') } catch { return null }
}

export default function App() {
  const [page, setPage] = useState(pageFromHash)
  const [snapshots, setSnapshots] = useState([])
  const [snapId, setSnapId] = useState(null)
  const [data, setData] = useState(null)        // { analysis, lab, bill }
  const [shared, setShared] = useState({})      // fleet, rules, prices (not per snapshot)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(readTheme)

  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('popstate', onHash)
    window.addEventListener('hashchange', onHash)
    return () => {
      window.removeEventListener('popstate', onHash)
      window.removeEventListener('hashchange', onHash)
    }
  }, [])

  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme
    else delete document.documentElement.dataset.theme
    try { theme ? localStorage.setItem('theme', theme) : localStorage.removeItem('theme') } catch { /* private mode */ }
  }, [theme])

  useEffect(() => {
    Promise.all([api.snapshots(), api.fleet(), api.rules()])
      .then(([snaps, fleet, rules]) => {
        setSnapshots(snaps)
        setShared((s) => ({ ...s, fleet, rules }))
        setSnapId(snaps[0]?.id ?? null)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!snapId) return
    let live = true
    Promise.all([api.analysis(snapId), api.lab(snapId), api.bill(snapId)])
      .then(([analysis, lab, bill]) => {
        if (!live) return
        setData({ analysis, lab, bill })
        setSelected(null)
        api.prices(analysis.snapshot.region).then((prices) => live && setShared((s) => ({ ...s, prices })))
      })
      .catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [snapId])

  const go = (id, findingId) => {
    if (findingId) setSelected(findingId)
    window.history.pushState(null, '', `#/${id}`)   // keeps Back button working
    setPage(id)
    window.scrollTo(0, 0)
  }

  const snap = snapshots.find((s) => s.id === snapId)
  const isDark = theme === 'dark' || (!theme && window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  const counts = data && {
    findings: data.analysis.summary.findings,
    backtest: data.analysis.backtests.length || null,
  }

  let body
  if (error) {
    body = (
      <div className="error-box">
        <b>Cannot reach the backend.</b> {error}
        <p className="small" style={{ marginTop: 6 }}>Start it with: <span className="mono">cd backend &amp;&amp; uvicorn app.main:app --reload</span></p>
      </div>
    )
  } else if (!data) {
    body = <div className="loading">Loading analysis…</div>
  } else {
    const props = { ...data, ...shared, go }
    body = {
      overview: <Overview {...props} />,
      findings: <Findings {...props} selected={selected} onSelect={setSelected} />,
      backtest: <Backtest {...props} />,
      lab: <Lab {...props} />,
      bill: <BillCheck {...props} />,
      fleet: <Fleet {...props} />,
      method: <Method rules={shared.rules || []} prices={shared.prices} />,
    }[page]
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">$</div>
          <div>
            <div className="brand-name">Cloud Cost Optimizer</div>
            <div className="brand-sub">recommendations you can check</div>
          </div>
        </div>
        <nav className="nav" aria-label="Pages">
          {PAGES.map((p, k) => {
            const header = k === 0 || PAGES[k - 1].group !== p.group
              ? <div className="nav-group" key={p.group}>{p.group}</div> : null
            return [header, (
              <button key={p.id} aria-current={page === p.id ? 'page' : undefined} onClick={() => go(p.id)}>
                {p.label}
                {counts?.[p.id] ? <span className="count">{counts[p.id]}</span> : null}
              </button>
            )]
          })}
        </nav>
        <div className="sidebar-foot">Read-only · never changes your AWS account</div>
      </aside>

      <div className="main">
        <div className="topbar">
          <label className="small muted" htmlFor="snap">Snapshot</label>
          <select id="snap" value={snapId ?? ''} onChange={(e) => setSnapId(e.target.value)}>
            {snapshots.map((s) => (
              <option key={s.id} value={s.id}>{s.source === 'demo' ? 'Demo account (synthetic)' : `${s.account} · ${s.id}`}</option>
            ))}
          </select>
          {snap && (snap.source === 'demo'
            ? <span className="badge demo">● Demo data</span>
            : <span className="badge real">● Real AWS account</span>)}
          {snap && <span className="small muted">{snap.region} · collected {date(snap.collected_at)}</span>}
          <span className="spacer" />
          {data && <span className="small muted">Savings found: <b style={{ color: 'var(--text)' }}>{usd(data.analysis.summary.potential_savings)}/mo</b></span>}
          <button className="btn" onClick={() => setTheme(isDark ? 'light' : 'dark')} aria-label="Toggle dark mode">
            {isDark ? '☀ Light' : '☾ Dark'}
          </button>
        </div>
        <main className="content">{body}</main>
      </div>
    </div>
  )
}
