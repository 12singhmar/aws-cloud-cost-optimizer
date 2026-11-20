import { useEffect, useState } from 'react'
import { api } from './api.js'
import ConnectDialog from './ConnectDialog.jsx'
import Account from './pages/Account.jsx'
import Home from './pages/Home.jsx'
import Planner from './pages/Planner.jsx'
import Usage from './pages/Usage.jsx'

const PAGES = [
  { id: 'home', label: 'Home' },
  { id: 'planner', label: 'Cost Planner' },
  { id: 'usage', label: 'Usage Analysis' },
  { id: 'account', label: 'My AWS Account' },
]

export default function App() {
  const [page, setPage] = useState('home')
  const [overview, setOverview] = useState(null)
  const [status, setStatus] = useState(null)
  const [showConnect, setShowConnect] = useState(false)
  const [plannerInput, setPlannerInput] = useState(null)   // workload sent from Usage Analysis
  const [error, setError] = useState(null)

  const loadOverview = () => api.overview().then(setOverview).catch(() => setError('Cannot reach the backend. Start it with: python -m uvicorn app.main:app'))

  useEffect(() => {
    loadOverview()
    api.status().then(setStatus).catch(() => setStatus({ connected: false }))
  }, [])

  function openPlanner(workload, note) {
    setPlannerInput({ workload: { ...plannerDefaults(), ...workload }, note })
    setPage('planner')
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">$</span>
          <div><b>Cloud Cost Optimizer</b><span>AWS · real prices</span></div>
        </div>
        <nav>
          {PAGES.map((p) => (
            <button key={p.id} className={page === p.id ? 'active' : ''} onClick={() => setPage(p.id)}>{p.label}</button>
          ))}
        </nav>
        <div className="connection">
          {status?.connected ? (
            <>
              <b><span className="dot on" /> Connected</b>
              <span className="muted small">{status.account} · {status.region}</span>
              <button className="small-btn" onClick={() => setShowConnect(true)}>Change</button>
            </>
          ) : (
            <>
              <b><span className="dot" /> Not connected</b>
              <span className="muted small">Planner and public data work without AWS</span>
              <button className="primary" onClick={() => setShowConnect(true)}>Connect AWS</button>
            </>
          )}
        </div>
      </aside>

      <main className="main">
        {error && <div className="panel error">{error}</div>}
        {overview && page === 'home' && <Home overview={overview} status={status} go={setPage} onConnect={() => setShowConnect(true)} />}
        {overview && page === 'planner' && (
          <Planner key={plannerInput ? JSON.stringify(plannerInput.workload) : 'default'}
            regions={overview.regions} initial={plannerInput?.workload} note={plannerInput?.note} />
        )}
        {overview && page === 'usage' && <Usage scans={overview.scans} onOptimize={openPlanner} />}
        {overview && page === 'account' && (
          <Account status={status} scans={overview.scans} onConnect={() => setShowConnect(true)} onScanned={loadOverview} go={setPage} />
        )}
      </main>

      {showConnect && overview && (
        <ConnectDialog regions={overview.regions} onClose={() => setShowConnect(false)} onConnected={setStatus} />
      )}
    </div>
  )
}

// fields the usage analysis does not know; the user can change them in the planner
function plannerDefaults() {
  return {
    count: 1, memory_needed_gb: null, storage_gb: 0, storage_type: 'gp3',
    arm_ok: false, commit_years: 0, region_flexible: false,
  }
}
