import { useEffect, useState } from 'react'
import { api } from './api.js'
import ConnectDialog from './ConnectDialog.jsx'
import Account from './pages/Account.jsx'
import Checker from './pages/Checker.jsx'

export default function App() {
  const [page, setPage] = useState('account')
  const [info, setInfo] = useState(null)
  const [status, setStatus] = useState(null)
  const [showConnect, setShowConnect] = useState(false)
  const [error, setError] = useState(null)

  function loadInfo() {
    return api.info().then(setInfo).catch(() => setError('Cannot reach the backend. Start it with: python -m uvicorn app.main:app'))
  }

  useEffect(() => {
    loadInfo()
    api.status().then(setStatus).catch(() => setStatus({ connected: false }))
  }, [])

  return (
    <>
      <header>
        <span className="title">AWS Cost Cleaner</span>
        <nav>
          <button className={page === 'account' ? 'active' : ''} onClick={() => setPage('account')}>My AWS account</button>
          <button className={page === 'checker' ? 'active' : ''} onClick={() => setPage('checker')}>Cost checker</button>
        </nav>
        <span className="status">
          {status?.connected ? `Connected: ${status.account}` : 'Not connected'}
          <button onClick={() => setShowConnect(true)}>{status?.connected ? 'Change' : 'Connect AWS'}</button>
        </span>
      </header>

      <main>
        {info?.test_mode && <p className="notice">Test mode: connected to a fake AWS on this computer, not a real account.</p>}
        {error && <p className="error">{error}</p>}
        {info && page === 'account' && (
          <Account status={status} scans={info.scans} onConnect={() => setShowConnect(true)} onScanned={loadInfo} />
        )}
        {info && page === 'checker' && <Checker regions={info.regions} />}
      </main>

      {showConnect && <ConnectDialog onClose={() => setShowConnect(false)} onConnected={setStatus} />}
    </>
  )
}
